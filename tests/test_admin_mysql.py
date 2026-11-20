"""Role migration and admin totals against an isolated disposable MySQL DB."""
import hashlib
import os
import unittest
import uuid

import MySQLdb
import MySQLdb.cursors

import app as lakbay
from administration import admin_overview, setup_admin_account
from missions import import_mission_cards
from rewards import redeem_reward


@unittest.skipUnless(os.environ.get('LAKBAYPASS_TEST_MYSQL') == '1', 'Set LAKBAYPASS_TEST_MYSQL=1 for isolated MySQL tests')
class MySQLAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db = lakbay.app.config['MYSQL_DB']
        cls.name = 'lp_admin_test_' + uuid.uuid4().hex
        cls.options = dict(host=lakbay.app.config['MYSQL_HOST'], user=lakbay.app.config['MYSQL_USER'],
                           passwd=lakbay.app.config['MYSQL_PASSWORD'], port=lakbay.app.config['MYSQL_PORT'],
                           connect_timeout=10, charset='utf8mb4')
        cls.root = MySQLdb.connect(**cls.options)
        with cls.root.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{cls.name}` CHARACTER SET utf8mb4')
        cls.connection = MySQLdb.connect(db=cls.name, **cls.options)
        # Exercise the existing installations whose users predate the role column.
        with cls.connection.cursor() as cursor:
            cursor.execute('CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) NOT NULL, '
                           'email VARCHAR(100) NOT NULL UNIQUE, password VARCHAR(255) NOT NULL) ENGINE=InnoDB')
            cursor.executemany('INSERT INTO users (username,email,password) VALUES (%s,%s,%s)', [
                ('Existing traveler', 'existing@example.test', hashlib.sha256(b'test-password').hexdigest()),
                ('New traveler', 'empty@example.test', hashlib.sha256(b'test-password').hexdigest()),
            ])
        cls.connection.commit()
        import_mission_cards(cls.connection)
        with cls.connection.cursor() as cursor:
            cursor.execute('INSERT INTO point_claims (user_id,mission_card_id,points_awarded) SELECT 1,id,points FROM mission_cards')
        cls.connection.commit()
        setup_admin_account(cls.connection, 'admin@lakbay.pass', 'admin@lakbay.pass')
        redeem_reward(cls.connection, 1, 'ecert', uuid.uuid4().hex)
        redeem_reward(cls.connection, 1, 'ecert', uuid.uuid4().hex)
        lakbay.app.config.update(MYSQL_DB=cls.name, TESTING=True)

    @classmethod
    def tearDownClass(cls):
        lakbay.app.config['MYSQL_DB'] = cls.original_db
        cls.connection.close()
        with cls.root.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{cls.name}`')
        cls.root.close()

    def test_migration_preserves_existing_users_and_claims(self):
        with self.connection.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute('SELECT * FROM users WHERE id = 1')
            user = cursor.fetchone()
            self.assertEqual(user['username'], 'Existing traveler')
            self.assertEqual(user['role'], 'user')
            self.assertEqual(user['password'], hashlib.sha256(b'test-password').hexdigest())
            cursor.execute('SELECT COUNT(*) AS total FROM point_claims WHERE user_id=1')
            self.assertEqual(cursor.fetchone()['total'], 18)

    def test_rerunning_admin_setup_is_idempotent(self):
        setup_admin_account(self.connection, 'admin@lakbay.pass', 'admin@lakbay.pass')
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM users')
            self.assertEqual(cursor.fetchone()[0], 3)
            cursor.execute("SELECT password,role FROM users WHERE email='admin@lakbay.pass'")
            self.assertEqual(cursor.fetchone(), (hashlib.sha256(b'admin@lakbay.pass').hexdigest(), 'admin'))

    def test_aggregates_do_not_multiply_awards_by_redemption_count(self):
        self.connection.rollback()
        overview = admin_overview(self.connection)
        self.assertEqual(overview['total_users'], 3)
        users = {user['id']: user for user in overview['users']}
        self.assertEqual(users[1]['earned_points'], 270)
        self.assertEqual(users[1]['available_points'], 90)
        self.assertEqual(users[2]['earned_points'], 0)
        self.assertEqual(users[2]['available_points'], 0)
        self.assertEqual(len(overview['redemptions']), 2)
        for redemption in overview['redemptions']:
            self.assertEqual(redemption['username'], 'Existing traveler')
            self.assertEqual(redemption['email'], 'existing@example.test')
            self.assertTrue(redemption['reference'].startswith('LP-'))
            self.assertEqual(redemption['points_spent'], 90)

    def test_real_login_and_database_role_authorization(self):
        client = lakbay.app.test_client()
        response = client.post('/login', data=dict(email='admin@lakbay.pass', password='admin@lakbay.pass'))
        self.assertEqual(response.location, '/admin')
        self.assertIn(b'Existing traveler', client.get('/admin').data)
        response = client.post('/login', data=dict(email='existing@example.test', password='test-password'))
        self.assertEqual(response.location, '/dashboard')
        self.assertEqual(client.get('/admin').status_code, 403)


if __name__ == '__main__':
    unittest.main()
