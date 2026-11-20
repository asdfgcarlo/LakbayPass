"""Real InnoDB claims and migration tests, confined to a temporary database.

Run with LAKBAYPASS_TEST_MYSQL=1. The configured MySQL account needs CREATE
DATABASE permission. No rows in the application's database are modified.
"""
import hashlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import MySQLdb
import MySQLdb.cursors

import app as lakbay
from missions import AssignmentConflict, import_mission_cards


# Independent copy of the user's required mapping (not derived from app data).
MAPPING = {
    'palawan': ('LP-T5V5BWZM', 'LP-BALJDMK4', 'LP-KT2QEJGK'),
    'vigan': ('LP-KE9WGKU6', 'LP-LNZSEHEX', 'LP-T93EPVGV'),
    'cebu': ('LP-LQ8XBEJA', 'LP-QG99QBYR', 'LP-2KK9Y69H'),
    'siquijor': ('LP-DEZHUVQJ', 'LP-EXSBZNRP', 'LP-NW2SAZUN'),
    'siargao': ('LP-WQS7FMFF', 'LP-ARX3WG6V', 'LP-HCH32HR3'),
    'camiguin': ('LP-F5ZZ2HX8', 'LP-5Q9BRMSM', 'LP-4GS6E5ZE'),
}


@unittest.skipUnless(os.environ.get('LAKBAYPASS_TEST_MYSQL') == '1', 'Set LAKBAYPASS_TEST_MYSQL=1 for isolated MySQL tests')
class MySQLClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db = lakbay.app.config['MYSQL_DB']
        cls.test_db = 'lakbaypass_test_' + uuid.uuid4().hex
        cls.options = dict(host=lakbay.app.config['MYSQL_HOST'], user=lakbay.app.config['MYSQL_USER'],
                           passwd=lakbay.app.config['MYSQL_PASSWORD'], charset='utf8mb4')
        cls.admin = MySQLdb.connect(**cls.options)
        with cls.admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{cls.test_db}` CHARACTER SET utf8mb4')
        cls.database = MySQLdb.connect(db=cls.test_db, **cls.options)
        import_mission_cards(cls.database)
        with cls.database.cursor() as cursor:
            for number in (1, 2):
                cursor.execute('INSERT INTO users (username,email,password) VALUES (%s,%s,%s)', (
                    f'Test traveler {number}', f'claims-{number}@example.test',
                    hashlib.sha256(b'test-password').hexdigest(),
                ))
        cls.database.commit()
        lakbay.app.config.update(MYSQL_DB=cls.test_db, TESTING=True)

    @classmethod
    def tearDownClass(cls):
        lakbay.app.config['MYSQL_DB'] = cls.original_db
        cls.database.close()
        # Only this explicitly created, UUID-scoped test database is removed.
        with cls.admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{cls.test_db}`')
        cls.admin.close()

    def setUp(self):
        self.database.rollback()
        with self.database.cursor() as cursor:
            cursor.execute('DELETE FROM point_claims')
        self.database.commit()

    def client_for(self, account=1, slug='cebu'):
        client = lakbay.app.test_client()
        response = client.post('/login', data={
            'email': f'claims-{account}@example.test', 'password': 'test-password',
        })
        self.assertEqual(response.location, '/dashboard')
        self.assertEqual(client.get(f'/destinations/{slug}').status_code, 200)
        return client

    def scan(self, client, qr='LP-QG99QBYR', slug='cebu', **extra):
        with client.session_transaction() as session:
            csrf = session['claim_csrf']
        return client.post('/api/claims', json={'qr_code': qr, 'destination_slug': slug, **extra},
                           headers={'X-CSRF-Token': csrf})

    def saved_claims(self):
        self.database.rollback()  # Start a fresh read snapshot after API writes.
        with self.database.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute('SELECT * FROM point_claims ORDER BY id')
            return cursor.fetchall()

    def test_all_18_codes_map_and_award_the_exact_mission_points(self):
        with self.database.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute('SELECT destination_slug,mission_type,qr_code,points FROM mission_cards')
            actual = {(r['destination_slug'], r['mission_type']): (r['qr_code'], r['points']) for r in cursor.fetchall()}
        expected = {(slug, kind): (qr, points)
                    for slug, codes in MAPPING.items()
                    for kind, points, qr in zip(('itinerary', 'local_foods', 'activities'), (10, 15, 20), codes)}
        self.assertEqual(actual, expected)
        client = self.client_for()
        total = 0
        for (slug, kind), (qr, points) in expected.items():
            result = self.scan(client, qr, slug)
            self.assertEqual(result.status_code, 201, result.json)
            self.assertEqual(result.json['mission_type'], kind)
            self.assertEqual(result.json['points_awarded'], points)
            total += points
            self.assertEqual(result.json['total_points'], total)
        self.assertEqual(len(self.saved_claims()), 18)
        self.assertEqual(total, 270)

    def test_cebu_food_claim_repeat_other_account_and_saved_render(self):
        first, second = self.client_for(1), self.client_for(2)
        result = self.scan(first, points=999, user_id=2, mission_card_id=1)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['points_awarded'], 15)
        self.assertEqual(result.json['total_points'], 15)
        food = next(m for m in result.json['missions'] if m['mission_type'] == 'local_foods')
        self.assertTrue(food['claimed'])
        self.assertEqual(food['points_awarded'], 15)
        self.assertIsNotNone(food['claimed_at'])
        repeat = self.scan(first)
        self.assertEqual(repeat.status_code, 409)
        self.assertEqual(repeat.json['status'], 'already_claimed')
        self.assertEqual(repeat.json['points_awarded'], 0)
        self.assertEqual(repeat.json['total_points'], 15)
        other = self.scan(second)
        self.assertEqual(other.status_code, 201)
        self.assertEqual(other.json['total_points'], 15)
        claims = self.saved_claims()
        self.assertEqual([(r['user_id'], r['points_awarded']) for r in claims], [(1, 15), (2, 15)])
        self.assertTrue(all(r['claimed_at'] for r in claims))
        self.assertIn('data-mission-type="local_foods" class="is-claimed"', first.get('/destinations/cebu').text)
        self.assertEqual(first.get('/api/destinations/cebu/missions').json['total_points'], 15)

    def test_simultaneous_scans_award_once(self):
        clients = [self.client_for() for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(self.scan, clients))
        self.assertEqual(sorted(r.status_code for r in results), [201] + [409] * 7)
        self.assertEqual(sum(r.json['points_awarded'] for r in results), 15)
        self.assertEqual(len(self.saved_claims()), 1)

    def test_unknown_wrong_destination_and_invalid_requests_award_nothing(self):
        client = self.client_for()
        for qr in ('LP-00000000', 'https://example.test', 'LP-QG99QBYR ', '\U0001f30d'):
            with self.subTest(qr=qr):
                result = self.scan(client, qr)
                self.assertEqual(result.status_code, 404)
                self.assertEqual(result.json['status'], 'unknown_qr')
        wrong = self.scan(client, MAPPING['palawan'][1])
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(wrong.json['status'], 'wrong_destination')
        self.assertIn('Palawan', wrong.json['message'])
        self.assertEqual(self.scan(client, slug='unknown').status_code, 400)
        self.assertEqual(self.scan(client, qr=42).status_code, 400)
        self.assertEqual(self.scan(client, qr='x' * 513).status_code, 400)
        self.assertEqual(client.post('/api/claims', json={}).status_code, 403)
        with client.session_transaction() as session:
            csrf = session['claim_csrf']
        self.assertEqual(client.post('/api/claims', json=[], headers={'X-CSRF-Token': csrf}).status_code, 400)
        self.assertEqual(len(self.saved_claims()), 0)

    def test_login_and_csrf_are_required(self):
        anonymous = lakbay.app.test_client()
        self.assertEqual(anonymous.post('/api/claims', json={}).status_code, 401)
        self.assertEqual(anonymous.get('/api/destinations/cebu/missions').status_code, 401)
        client = self.client_for()
        self.assertEqual(client.post('/api/claims', json={}, headers={'X-CSRF-Token': 'wrong'}).status_code, 403)
        self.assertEqual(client.post('/api/claims', json={}, headers={'X-CSRF-Token': '\u00e9'}).status_code, 403)
        with client.session_transaction() as session:
            session['id'] = 999999
        self.assertEqual(self.scan(client).status_code, 401)
        self.assertEqual(len(self.saved_claims()), 0)

    def test_import_rerun_preserves_ids_and_claims_and_conflicts_stop_import(self):
        self.scan(self.client_for())
        before = self.saved_claims()
        with self.database.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute('SELECT * FROM mission_cards ORDER BY id')
            cards_before = cursor.fetchall()
        self.assertEqual(import_mission_cards(self.database), 0)
        self.assertEqual(self.saved_claims(), before)
        with self.database.cursor(MySQLdb.cursors.DictCursor) as cursor:
            cursor.execute('SELECT * FROM mission_cards ORDER BY id')
            self.assertEqual(cursor.fetchall(), cards_before)
            cursor.execute("UPDATE mission_cards SET points=99 WHERE qr_code='LP-QG99QBYR'")
        self.database.commit()
        try:
            with self.assertRaisesRegex(AssignmentConflict, 'LP-QG99QBYR.*99 pts'):
                import_mission_cards(self.database)
            self.assertEqual(self.saved_claims(), before)
        finally:
            with self.database.cursor() as cursor:
                cursor.execute("UPDATE mission_cards SET points=15 WHERE qr_code='LP-QG99QBYR'")
            self.database.commit()

    def test_database_unique_constraints_reject_duplicates(self):
        self.scan(self.client_for())
        with self.database.cursor() as cursor:
            with self.assertRaises(MySQLdb.IntegrityError):
                cursor.execute('INSERT INTO point_claims (user_id,mission_card_id,points_awarded) '
                               'SELECT user_id,mission_card_id,points_awarded FROM point_claims LIMIT 1')
            self.database.rollback()
            with self.assertRaises(MySQLdb.IntegrityError):
                cursor.execute("INSERT INTO mission_cards (destination_slug,mission_type,qr_code,points) "
                               "VALUES ('other','itinerary','LP-QG99QBYR',15)")
            self.database.rollback()
        self.assertEqual(len(self.saved_claims()), 1)


if __name__ == '__main__':
    unittest.main()
