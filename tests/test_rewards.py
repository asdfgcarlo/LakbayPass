"""Reward page authentication, CSRF, catalog, and repeat submission handling."""
import unittest
from unittest.mock import patch

import MySQLdb

import app as lakbay
from rewards import RedemptionError


class RewardRouteTests(unittest.TestCase):
    def setUp(self):
        lakbay.app.config['TESTING'] = True
        self.client = lakbay.app.test_client()
        self.overview = dict(balance=270, earned=270, history=[])
        for name, options in (
            ('mysql', {}), ('reward_overview', dict(return_value=self.overview)),
            ('redeem_reward', dict(return_value=dict(reward_name='eCert', points_spent=90,
                                                   reference='LP-TEST', already_redeemed=False))),
        ):
            patcher = patch.object(lakbay, name, **options)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def sign_in(self):
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=42, username='Traveler')

    def form(self):
        self.sign_in()
        self.client.get('/redeem')
        with self.client.session_transaction() as session:
            return dict(csrf_token=session['redeem_csrf'], reward='ecert',
                        request_key=session['redeem_requests']['ecert'])

    def test_login_required_for_reading_and_spending(self):
        for method in (self.client.get, self.client.post):
            self.assertEqual(method('/redeem').location, '/login')
        self.redeem_reward.assert_not_called()

    def test_three_offers_and_prices_and_saved_balance(self):
        self.sign_in()
        response = self.client.get('/redeem')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'20% Discount for the New Card Game', response.data)
        self.assertIn(b'Physical Keychain', response.data)
        for cost in (90, 180, 270):
            self.assertIn(f'Redeem for {cost} pts'.encode(), response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.reward_overview.assert_called_once_with(self.mysql.connection, 42)

    def test_insufficient_balance_disables_purchase(self):
        self.sign_in()
        self.overview['balance'] = 89
        response = self.client.get('/redeem')
        self.assertIn(b'Need 1 more pt', response.data)
        self.assertEqual(response.data.count(b'disabled'), 3)

    def test_missing_or_wrong_csrf_never_calls_redemption(self):
        data = self.form()
        for csrf in ('', 'incorrect'):
            response = self.client.post('/redeem', data=dict(data, csrf_token=csrf))
            self.assertEqual(response.status_code, 403)
        self.redeem_reward.assert_not_called()

    def test_post_uses_session_identity_and_server_catalog(self):
        data = self.form()
        response = self.client.post('/redeem', data=dict(data, user_id=99, cost=1))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, '/redeem')
        self.redeem_reward.assert_called_once_with(self.mysql.connection, 42, 'ecert', data['request_key'])
        with self.client.session_transaction() as session:
            self.assertNotIn('ecert', session['redeem_requests'])

    def test_request_key_survives_page_refresh_until_a_confirmed_redemption(self):
        first = self.form()['request_key']
        self.client.get('/redeem')
        with self.client.session_transaction() as session:
            self.assertEqual(session['redeem_requests']['ecert'], first)

    def test_insufficient_points_is_reported_without_success(self):
        data = self.form()
        self.redeem_reward.side_effect = RedemptionError('insufficient_points', 'You need 1 more point.')
        response = self.client.post('/redeem', data=data, follow_redirects=True)
        self.assertIn(b'You need 1 more point.', response.data)
        self.assertNotIn(b'points deducted', response.data)

    def test_repeat_submission_explains_that_no_more_points_were_deducted(self):
        data = self.form()
        self.redeem_reward.return_value['already_redeemed'] = True
        response = self.client.post('/redeem', data=data, follow_redirects=True)
        self.assertIn(b'No additional points were deducted', response.data)

    def test_database_error_has_retry_and_no_false_confirmation(self):
        data = self.form()
        self.redeem_reward.side_effect = MySQLdb.OperationalError(2003, 'Connection unavailable')
        with self.assertLogs(lakbay.app.logger, level='ERROR'):
            response = self.client.post('/redeem', data=data)
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'could not be confirmed', response.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session['redeem_requests']['ecert'], data['request_key'])

    def test_missing_account_clears_session(self):
        self.sign_in()
        self.reward_overview.return_value = None
        self.assertEqual(self.client.get('/redeem').location, '/login')
        with self.client.session_transaction() as session:
            self.assertNotIn('loggedin', session)


if __name__ == '__main__':
    unittest.main()
