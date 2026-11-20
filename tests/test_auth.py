"""Route regressions; run: venv/Scripts/python -m unittest discover -s tests."""
import hashlib
import unittest
from unittest.mock import MagicMock, patch

import MySQLdb

import app as auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        auth.app.config['TESTING'] = True
        self.client = auth.app.test_client()
        self.database = MagicMock()
        self.cursor = self.database.connection.cursor.return_value
        self.cursor.fetchone.return_value = None
        self.patcher = patch.object(auth, 'mysql', self.database)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        points_patcher = patch.object(auth, 'player_total_points', return_value=0)
        points_patcher.start()
        self.addCleanup(points_patcher.stop)

    def test_screens_and_navigation(self):
        for path in ('/', '/login', '/register'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'auth.css', response.data)
            self.assertIn(b'aria-controls="password"', response.data)
        self.assertIn(b'href="/register"', self.client.get('/login').data)
        self.assertIn(b'href="/login"', self.client.get('/register').data)
        self.assertNotIn(b'Forgot password', self.client.get('/login').data)

    def test_missing_fields_do_not_query_database(self):
        response = self.client.post('/register', data={})
        for name in ('username', 'email', 'password'):
            self.assertIn(f'id="{name}-error"'.encode(), response.data)
        self.assertIn(b'Enter your username.', response.data)
        self.assertIn(b'Enter your email address.', response.data)
        self.assertIn(b'Enter your password.', response.data)
        self.database.connection.cursor.assert_not_called()
        self.assertIn(b'Enter your password.', self.client.post('/login', data={}).data)

    def test_bad_email_preserves_other_values(self):
        response = self.client.post('/register', data={
            'username': 'A traveler', 'email': 'invalid-address', 'password': 'keep-private',
        })
        self.assertIn(b'Enter an email address like', response.data)
        self.assertIn(b'value="A traveler"', response.data)
        self.assertIn(b'value="invalid-address"', response.data)
        self.assertNotIn(b'keep-private', response.data)
        self.database.connection.cursor.assert_not_called()

    def test_database_field_limits_are_validated(self):
        response = self.client.post('/register', data={
            'username': 'a' * 101, 'email': 'a' * 100 + '@example.com', 'password': 'test',
        })
        self.assertIn(b'100 characters or fewer for your username', response.data)
        self.assertIn(b'100 characters or fewer for your email address', response.data)
        self.database.connection.cursor.assert_not_called()

    def test_duplicate_email_is_reported_beside_email(self):
        self.cursor.fetchone.return_value = {'id': 1}
        response = self.client.post('/register', data={
            'username': 'Traveler', 'email': 'existing@example.com', 'password': 'test',
        })
        self.assertIn(b'An account with this email already exists.', response.data)
        self.assertIn(b'value="existing@example.com"', response.data)
        self.database.connection.commit.assert_not_called()
        self.cursor.close.assert_called_once()

    def test_register_preserves_hash_format_and_password_whitespace(self):
        password = ' password with spaces '
        response = self.client.post('/register', data={
            'username': '  Traveler  ', 'email': '  new@example.com  ', 'password': password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')
        self.assertEqual(self.cursor.execute.call_args.args[1], (
            'Traveler', 'new@example.com', hashlib.sha256(password.encode()).hexdigest(),
        ))
        self.database.connection.commit.assert_called_once()
        self.assertIn(b'Your account is ready.', self.client.get('/login').data)

    def test_concurrent_duplicate_registration_is_handled(self):
        self.cursor.execute.side_effect = [None, MySQLdb.IntegrityError(1062, 'Duplicate email')]
        response = self.client.post('/register', data={
            'username': 'Traveler', 'email': 'existing@example.com', 'password': 'test',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'An account with this email already exists.', response.data)
        self.database.connection.rollback.assert_called_once()

    def test_failed_login_is_generic_and_does_not_authenticate(self):
        response = self.client.post('/login', data={'email': 'missing@example.com', 'password': 'wrong'})
        self.assertIn('Check your email and password.'.encode(), response.data)
        self.assertIn(b'value="missing@example.com"', response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn('loggedin', session)

    def test_login_dashboard_and_logout(self):
        self.cursor.fetchone.return_value = {'id': 42, 'username': 'Traveler'}
        response = self.client.post('/login', data={'email': 'traveler@example.com', 'password': 'test'})
        self.assertEqual(response.location, '/dashboard')
        with self.client.session_transaction() as session:
            self.assertTrue(session['loggedin'])
            self.assertEqual(session['id'], 42)
            self.assertEqual(session['username'], 'Traveler')
        self.assertIn(b'Welcome, Traveler!', self.client.get('/dashboard').data)
        self.assertEqual(self.client.get('/logout').location, '/login')
        self.assertEqual(self.client.get('/dashboard').location, '/login')

    def test_root_login_alias(self):
        self.cursor.fetchone.return_value = {'id': 42, 'username': 'Traveler'}
        self.assertEqual(self.client.post('/', data={
            'email': 'traveler@example.com', 'password': 'test',
        }).location, '/dashboard')


if __name__ == '__main__':
    unittest.main()
