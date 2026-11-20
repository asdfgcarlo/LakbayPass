"""Provider-version regression using uniquely named, disposable test tables.

Run with LAKBAYPASS_TEST_LEGACY_MYSQL=1 against the configured database.
Needs CREATE TABLE permission, not CREATE DATABASE or TEMPORARY TABLES.
Application users, claims, and redemptions are never written.
"""
import os
import re
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import MySQLdb

import app as lakbay
from missions import player_earned_points, player_total_points
from rewards import RedemptionError, redeem_reward


class IsolatedConnection:
    """Use the real server/driver with SQL confined to this test's table names."""
    def __init__(self, connection, names):
        self.connection = connection
        self.names = names

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def cursor(self, *args, **kwargs):
        cursor = self.connection.cursor(*args, **kwargs)
        names = self.names

        class Cursor:
            def __getattr__(self, name):
                return getattr(cursor, name)

            def execute(self, sql, parameters=None):
                isolated = re.sub(r'\b(users|point_claims|reward_redemptions)\b',
                                  lambda match: '`' + names[match[0]] + '`', sql)
                return cursor.execute(isolated, parameters)

        return Cursor()


@unittest.skipUnless(os.environ.get('LAKBAYPASS_TEST_LEGACY_MYSQL') == '1',
                     'Set LAKBAYPASS_TEST_LEGACY_MYSQL=1 for provider compatibility checks')
class HostedBalanceCompatibilityTests(unittest.TestCase):
    def test_unsigned_claims_are_reduced_and_repeated_redemptions_stop_at_zero(self):
        config = lakbay.app.config
        options = dict(
            host=config['MYSQL_HOST'], user=config['MYSQL_USER'], passwd=config['MYSQL_PASSWORD'],
            db=config['MYSQL_DB'], port=config['MYSQL_PORT'], connect_timeout=10, charset='utf8mb4',
        )
        connection = MySQLdb.connect(**options)
        names = {name: 'lp_redemption_test_' + uuid.uuid4().hex[:16] + '_' + name
                 for name in ('users', 'point_claims', 'reward_redemptions')}
        isolated = IsolatedConnection(connection, names)
        created = []
        try:
            with connection.cursor() as cursor:
                baseline = {}
                for name in names:
                    cursor.execute(f'SELECT COUNT(*) FROM `{name}`')
                    baseline[name] = cursor.fetchone()[0]
                cursor.execute(f'CREATE TABLE `{names["users"]}` (id INT PRIMARY KEY) ENGINE=InnoDB')
                created.append(names['users'])
                cursor.execute(f'CREATE TABLE `{names["point_claims"]}` (user_id INT, points_awarded SMALLINT UNSIGNED) ENGINE=InnoDB')
                created.append(names['point_claims'])
                cursor.execute(
                    f'CREATE TABLE `{names["reward_redemptions"]}` ('
                    'id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, '
                    'reward_code VARCHAR(32), reward_name VARCHAR(140), '
                    'points_spent SMALLINT UNSIGNED, request_key CHAR(32), '
                    'reference VARCHAR(32), UNIQUE KEY uq_request (user_id,request_key), '
                    'UNIQUE KEY uq_reference (reference)) ENGINE=InnoDB'
                )
                created.append(names['reward_redemptions'])
                cursor.execute(f'INSERT INTO `{names["users"]}` (id) VALUES (1)')
                cursor.execute(f'INSERT INTO `{names["point_claims"]}` (user_id,points_awarded) VALUES (1,270)')
            connection.commit()
            self.assertEqual(player_total_points(isolated, 1), 270)
            first_key = uuid.uuid4().hex
            for key, expected in ((first_key, 180), (uuid.uuid4().hex, 90), (uuid.uuid4().hex, 0)):
                result = redeem_reward(isolated, 1, 'ecert', key)
                self.assertFalse(result['already_redeemed'])
                self.assertEqual(player_total_points(isolated, 1), expected)
            with self.assertRaises(RedemptionError) as caught:
                redeem_reward(isolated, 1, 'ecert', uuid.uuid4().hex)
            self.assertEqual(caught.exception.status, 'insufficient_points')
            self.assertTrue(redeem_reward(isolated, 1, 'ecert', first_key)['already_redeemed'])
            self.assertEqual(player_total_points(isolated, 1), 0)
            self.assertEqual(player_earned_points(isolated, 1), 270)
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT COUNT(*) FROM `{names["reward_redemptions"]}`')
                self.assertEqual(cursor.fetchone()[0], 3)

            # Verify the same server's locking with both rapid distinct orders
            # and duplicate submissions when only one reward is affordable.
            for repeated in (False, True):
                with connection.cursor() as cursor:
                    cursor.execute(f'DELETE FROM `{names["reward_redemptions"]}`')
                    cursor.execute(f'UPDATE `{names["point_claims"]}` SET points_awarded=90')
                connection.commit()
                barrier = threading.Barrier(2)
                key = uuid.uuid4().hex

                def spend(request_key):
                    worker = MySQLdb.connect(**options)
                    try:
                        barrier.wait(timeout=15)
                        try:
                            result = redeem_reward(IsolatedConnection(worker, names), 1, 'ecert', request_key)
                            return 'repeat' if result['already_redeemed'] else 'redeemed'
                        except RedemptionError as error:
                            return error.status
                    finally:
                        worker.close()

                keys = [key, key if repeated else uuid.uuid4().hex]
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = list(executor.map(spend, keys))
                self.assertCountEqual(outcomes, ['redeemed', 'repeat' if repeated else 'insufficient_points'])
                connection.rollback()
                self.assertEqual(player_total_points(isolated, 1), 0)
                with connection.cursor() as cursor:
                    cursor.execute(f'SELECT COUNT(*) FROM `{names["reward_redemptions"]}`')
                    self.assertEqual(cursor.fetchone()[0], 1)

            with connection.cursor() as cursor:
                for name in names:
                    cursor.execute(f'SELECT COUNT(*) FROM `{name}`')
                    self.assertEqual(cursor.fetchone()[0], baseline[name])
        finally:
            try:
                connection.rollback()
                with connection.cursor() as cursor:
                    for name in reversed(created):
                        # Never clean up an existing application table, even on failure.
                        if not re.fullmatch(r'lp_redemption_test_[a-f0-9]{16}_(users|point_claims|reward_redemptions)', name):
                            raise AssertionError('Unsafe test-table cleanup target')
                        cursor.execute(f'DROP TABLE `{name}`')
            finally:
                connection.close()


if __name__ == '__main__':
    unittest.main()
