import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def sign_in(self):
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=1, username='Traveler')

    def test_gallery_requires_login(self):
        self.assertEqual(self.client.get('/dashboard').location, '/login')

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
