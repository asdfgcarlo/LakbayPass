"""Admin authorization and account-role route regressions."""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import MySQLdb

import app as lakbay


class AdminRouteTests(unittest.TestCase):
    def setUp(self):
        lakbay.app.config['TESTING'] = True
        self.client = lakbay.app.test_client()
        self.account = dict(id=5, username='Admin', role='admin')
        self.overview = dict(total_users=2, users=[
            dict(id=1, username='<Traveler>', email='traveler@example.test', role='user',
                 earned_points=270, available_points=90),
            dict(id=5, username='Admin', email='admin@lakbay.pass', role='admin',
                 earned_points=0, available_points=0),
        ], redemptions=[dict(username='<Traveler>', email='traveler@example.test',
                            reference='LP-EXAMPLE', reward_name='eCert', points_spent=90,
                            status='requested', redeemed_at=datetime(2026, 11, 20, 12, 30))])
        self.database = MagicMock()
        for name, value in [('mysql', self.database), ('admin_account', self.account),
                            ('admin_overview', self.overview)]:
            patcher = patch.object(lakbay, name, value) if name == 'mysql' else patch.object(lakbay, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def sign_in(self, role='admin'):
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=5, username='Admin', role=role)

    def test_logged_out_cannot_read_accounts(self):
        self.assertEqual(self.client.get('/admin').location, '/login')
        self.admin_account.assert_not_called()
        self.admin_overview.assert_not_called()

    def test_session_role_cannot_grant_access(self):
        self.sign_in('admin')
        self.admin_account.return_value = dict(id=5, username='Traveler', role='user')
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'only available to administrators', response.data)
        self.assertNotIn(b'traveler@example.test', response.data)
        self.admin_overview.assert_not_called()

    def test_database_role_can_grant_access_to_an_older_session(self):
        self.sign_in('user')
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.admin_account.assert_called_once_with(self.database.connection, 5)
        self.assertIn(b'id="total-users">2', response.data)
        for text in (b'Available points', b'Earned points', b'LP-EXAMPLE', b'traveler@example.test'):
            self.assertIn(text, response.data)
        self.assertIn(b'&lt;Traveler&gt;', response.data)
        self.assertNotIn(b'<Traveler>', response.data)

    def test_deleted_account_is_logged_out(self):
        self.sign_in()
        self.admin_account.return_value = None
        self.assertEqual(self.client.get('/admin').location, '/login')
        self.admin_overview.assert_not_called()
        with self.client.session_transaction() as session:
            self.assertNotIn('loggedin', session)

    def test_failure_has_retry_without_account_data(self):
        self.sign_in()
        self.admin_overview.side_effect = MySQLdb.OperationalError(2003, 'Unavailable')
        with self.assertLogs(lakbay.app.logger, level='ERROR'):
            response = self.client.get('/admin')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'Try again', response.data)
        self.assertNotIn(b'traveler@example.test', response.data)

    def test_empty_redemptions_have_an_explicit_state(self):
        self.sign_in()
        self.overview['redemptions'] = []
        self.assertIn(b'No rewards have been redeemed yet', self.client.get('/admin').data)

    def test_admin_login_redirects_and_replaces_old_session(self):
        self.database.connection.cursor.return_value.fetchone.return_value = self.account
        with self.client.session_transaction() as session:
            session.update(redeem_requests={'ecert': 'old-user-request'}, claim_csrf='old-token')
        response = self.client.post('/login', data={'email': 'admin@lakbay.pass', 'password': 'admin@lakbay.pass'})
        self.assertEqual(response.location, '/admin')
        with self.client.session_transaction() as session:
            self.assertEqual(session['role'], 'admin')
            self.assertNotIn('redeem_requests', session)
            self.assertNotIn('claim_csrf', session)

    def test_registration_does_not_accept_a_posted_admin_role(self):
        cursor = self.database.connection.cursor.return_value
        cursor.fetchone.return_value = None
        response = self.client.post('/register', data=dict(
            username='New user', email='new@example.test', password='test-password', role='admin'))
        self.assertEqual(response.location, '/login')
        sql, parameters = cursor.execute.call_args.args
        self.assertIn("'user'", sql)
        self.assertNotIn('admin', parameters)


if __name__ == '__main__':
    unittest.main()
