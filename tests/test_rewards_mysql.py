"""Real redemption transactions; all writes stay in a UUID-scoped test DB."""
import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import MySQLdb

import app as lakbay
from missions import import_mission_cards, player_earned_points, player_profile, player_total_points
from rewards import REWARDS, RedemptionError, redeem_reward, reward_overview


@unittest.skipUnless(os.environ.get('LAKBAYPASS_TEST_MYSQL') == '1', 'Set LAKBAYPASS_TEST_MYSQL=1 for isolated MySQL tests')
class MySQLRewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db = lakbay.app.config['MYSQL_DB']
        cls.name = 'lp_rewards_test_' + uuid.uuid4().hex
        cls.options = dict(host=lakbay.app.config['MYSQL_HOST'], user=lakbay.app.config['MYSQL_USER'],
                           passwd=lakbay.app.config['MYSQL_PASSWORD'], port=lakbay.app.config['MYSQL_PORT'],
                           connect_timeout=10, charset='utf8mb4')
        cls.admin = MySQLdb.connect(**cls.options)
        with cls.admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{cls.name}` CHARACTER SET utf8mb4')
        cls.connection = MySQLdb.connect(db=cls.name, **cls.options)
        import_mission_cards(cls.connection)
        with cls.connection.cursor() as cursor:
            cursor.executemany('INSERT INTO users (username,email,password) VALUES (%s,%s,%s)',
                               [('Rewards A', 'rewards-a@example.test', 'test-only'),
                                ('Rewards B', 'rewards-b@example.test', 'test-only')])
        cls.connection.commit()
        lakbay.app.config.update(MYSQL_DB=cls.name, TESTING=True)

    @classmethod
    def tearDownClass(cls):
        lakbay.app.config['MYSQL_DB'] = cls.original_db
        cls.connection.close()
        with cls.admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{cls.name}`')
        cls.admin.close()

    def setUp(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute('DELETE FROM reward_redemptions')
            cursor.execute('DELETE FROM point_claims')
            for user_id in (1, 2):
                cursor.execute('INSERT INTO point_claims (user_id,mission_card_id,points_awarded) SELECT %s,id,points FROM mission_cards', (user_id,))
        self.connection.commit()

    def count(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM reward_redemptions')
            return cursor.fetchone()[0]

    def test_each_offer_deducts_exact_cost_but_keeps_tier_and_claims(self):
        for reward in REWARDS:
            with self.subTest(reward=reward['code']):
                with self.connection.cursor() as cursor:
                    cursor.execute('DELETE FROM reward_redemptions')
                self.connection.commit()
                redeem_reward(self.connection, 1, reward['code'], uuid.uuid4().hex)
                self.assertEqual(player_total_points(self.connection, 1), 270 - reward['cost'])
                self.assertEqual(player_earned_points(self.connection, 1), 270)
                profile = player_profile(self.connection, 1)
                self.assertEqual(profile['tier'], 'Gold')
                self.assertEqual(profile['claimed_count'], 18)

    def test_replayed_request_deducts_only_once(self):
        key = uuid.uuid4().hex
        self.assertFalse(redeem_reward(self.connection, 1, 'ecert', key)['already_redeemed'])
        self.assertTrue(redeem_reward(self.connection, 1, 'ecert', key)['already_redeemed'])
        self.assertEqual(player_total_points(self.connection, 1), 180)
        self.assertEqual(self.count(), 1)

    def test_same_request_cannot_be_changed_to_a_different_reward(self):
        key = uuid.uuid4().hex
        redeem_reward(self.connection, 1, 'ecert', key)
        with self.assertRaises(RedemptionError):
            redeem_reward(self.connection, 1, 'keychain', key)
        self.assertEqual(player_total_points(self.connection, 1), 180)

    def test_three_small_rewards_spend_exactly_270_and_fourth_is_rejected(self):
        for _ in range(3):
            redeem_reward(self.connection, 1, 'ecert', uuid.uuid4().hex)
        with self.assertRaises(RedemptionError) as caught:
            redeem_reward(self.connection, 1, 'ecert', uuid.uuid4().hex)
        self.assertEqual(caught.exception.status, 'insufficient_points')
        self.assertEqual(player_total_points(self.connection, 1), 0)
        self.assertEqual(self.count(), 3)

    def concurrent(self, keys):
        barrier = threading.Barrier(len(keys))
        def spend(key):
            connection = MySQLdb.connect(db=self.name, **self.options)
            try:
                barrier.wait(timeout=15)
                try:
                    result = redeem_reward(connection, 1, 'ecert', key)
                    return 'repeat' if result['already_redeemed'] else 'redeemed'
                except RedemptionError as error:
                    return error.status
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=len(keys)) as executor:
            return list(executor.map(spend, keys))

    def test_concurrent_distinct_requests_cannot_overspend(self):
        results = self.concurrent([uuid.uuid4().hex for _ in range(6)])
        self.assertEqual(results.count('redeemed'), 3)
        self.assertEqual(results.count('insufficient_points'), 3)
        self.assertEqual(self.count(), 3)
        self.assertEqual(player_total_points(self.connection, 1), 0)

    def test_concurrent_retries_charge_once(self):
        results = self.concurrent([uuid.uuid4().hex] * 6)
        self.assertEqual(results.count('redeemed'), 1)
        self.assertEqual(results.count('repeat'), 5)
        self.assertEqual(self.count(), 1)
        self.assertEqual(player_total_points(self.connection, 1), 180)

    def test_history_and_balance_are_scoped_to_the_current_account(self):
        key = uuid.uuid4().hex
        saved = redeem_reward(self.connection, 1, 'ecert', key)
        redeem_reward(self.connection, 2, 'card_game_discount', key)
        first = reward_overview(self.connection, 1)
        second = reward_overview(self.connection, 2)
        self.assertEqual((first['balance'], second['balance']), (180, 90))
        self.assertEqual([item['reward_name'] for item in first['history']], [saved['reward_name']])
        self.assertEqual([item['reference'] for item in first['history']], [saved['reference']])

    def test_failed_insert_rolls_back_without_spending_points(self):
        saved = redeem_reward(self.connection, 2, 'ecert', uuid.uuid4().hex)
        with patch('rewards.secrets.token_hex', return_value=saved['reference'][3:].lower()):
            with self.assertRaises(MySQLdb.IntegrityError):
                redeem_reward(self.connection, 1, 'ecert', uuid.uuid4().hex)
        self.assertEqual(player_total_points(self.connection, 1), 270)
        self.assertEqual(self.count(), 1)

    def test_http_tampering_and_retry_never_change_the_price_or_account(self):
        client = lakbay.app.test_client()
        with client.session_transaction() as session:
            session.update(loggedin=True, id=1, username='Rewards A')
        self.assertEqual(client.get('/redeem').status_code, 200)
        with client.session_transaction() as session:
            data = dict(csrf_token=session['redeem_csrf'], reward='ecert',
                        request_key=session['redeem_requests']['ecert'], cost=1, user_id=2)
        self.assertEqual(client.post('/redeem', data=data).status_code, 303)
        repeated = client.post('/redeem', data=data, follow_redirects=True)
        self.assertIn(b'No additional points were deducted', repeated.data)
        self.connection.rollback()
        self.assertEqual(player_total_points(self.connection, 1), 180)
        self.assertEqual(player_total_points(self.connection, 2), 270)
        self.assertEqual(self.count(), 1)
        self.assertIn(b'<strong>180</strong>', client.get('/dashboard').data)


if __name__ == '__main__':
    unittest.main()
