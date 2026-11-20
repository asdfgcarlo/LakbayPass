import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import MySQLdb

from app import app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        patcher = patch('app.mysql')
        self.database = patcher.start()
        self.addCleanup(patcher.stop)
        self.cursor = self.database.connection.cursor.return_value
        self.cursor.fetchone.return_value = {'total': 0}

    def sign_in(self):
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=1, username='Traveler')

    def test_gallery_requires_login(self):
        self.assertEqual(self.client.get('/dashboard').location, '/login')
        self.database.connection.cursor.assert_not_called()

    def test_total_uses_the_signed_in_account_and_refreshes_on_each_visit(self):
        self.sign_in()
        self.cursor.fetchone.side_effect = [{'total': 35}, {'total': 50}]
        for total in (35, 50):
            response = self.client.get('/dashboard')
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'<strong>{total}</strong>'.encode(), response.data)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(self.cursor.execute.call_args.args[1], (1, 1))
        self.assertEqual(self.cursor.close.call_count, 2)

    def test_account_without_claims_shows_zero(self):
        self.sign_in()
        response = self.client.get('/dashboard')
        self.assertIn(b'<strong>0</strong>', response.data)
        self.assertNotIn(b'Points unavailable', response.data)

    def test_database_failure_keeps_gallery_available_without_a_false_zero(self):
        self.sign_in()
        self.cursor.execute.side_effect = MySQLdb.OperationalError(2003, 'Connection unavailable')
        with self.assertLogs(app.logger, level='ERROR'):
            response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Points unavailable', response.data)
        self.assertNotIn(b'<strong>0</strong>', response.data)
        self.assertIn(b'href="/logout"', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.cursor.close.assert_called_once()

    def test_six_destinations_and_missing_photo_fallback(self):
        self.sign_in()
        with tempfile.TemporaryDirectory() as directory, patch.object(app, '_static_folder', directory):
            response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for caption in ('Mitra’s Ranch', 'Calle Crisologo', 'Binalayan Hidden Falls',
                        'Paliton Beach', 'Sugba Lagoon', 'Mantigue Island'):
            self.assertIn(caption, html)
        self.assertEqual(html.count('class="photo-tile"'), 6)
        self.assertEqual(html.count('src="/static/destinations/photo-placeholder.svg"'), 6)
        self.assertIn('href="/logout"', html)
        self.assertIn('href="/profile"', html)

    def test_existing_photo_replaces_only_its_placeholder(self):
        self.sign_in()
        with tempfile.TemporaryDirectory() as directory, patch.object(app, '_static_folder', directory):
            photo = Path(directory) / 'destinations/palawan-mitras-ranch.jpg'
            photo.parent.mkdir()
            photo.write_bytes(b'photo fixture; route only checks asset existence')
            html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('src="/static/destinations/palawan-mitras-ranch.jpg"', html)
        self.assertEqual(html.count('src="/static/destinations/photo-placeholder.svg"'), 5)


if __name__ == '__main__':
    unittest.main()
