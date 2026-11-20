"""Destination page and access regressions; run with unittest discovery."""
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from flask import render_template

import app as lakbay


PLACES = (
    ('palawan', 'Palawan', 'Mitra’s Ranch', 'palawan-mitras-ranch.jpg'),
    ('vigan', 'Vigan', 'Calle Crisologo', 'vigan-calle-crisologo.jpg'),
    ('cebu', 'Cebu', 'Binalayan Hidden Falls', 'cebu-binalayan-hidden-falls.jpg'),
    ('siquijor', 'Siquijor', 'Paliton Beach', 'siquijor-paliton-beach.jpg'),
    ('siargao', 'Siargao', 'Sugba Lagoon', 'siargao-sugba-lagoon.jpg'),
    ('camiguin', 'Camiguin', 'Mantigue Island', 'camiguin-mantigue-island.jpg'),
)


class DestinationHTML(HTMLParser):
    """Collect visible labels and attributes without depending on nested markup."""

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.open_elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ('a', 'button', 'h1', 'img', 'li'):
            element = {'tag': tag, 'attrs': dict(attrs), 'text': ''}
            self.elements.append(element)
            if tag != 'img':
                self.open_elements.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.open_elements) - 1, -1, -1):
            if self.open_elements[index]['tag'] == tag:
                self.open_elements.pop(index)
                break

    def handle_data(self, data):
        for element in self.open_elements:
            element['text'] += data

    def of_type(self, tag):
        return [element for element in self.elements if element['tag'] == tag]


class DestinationTests(unittest.TestCase):
    def setUp(self):
        lakbay.app.config['TESTING'] = True
        self.client = lakbay.app.test_client()
        # Rendering tests stay independent of MySQL; real claim persistence is
        # exercised against an isolated database in test_claims_mysql.py.
        from missions import MISSION_TYPES
        progress = {'total_points': 0, 'missions': [
            dict(mission_type=kind, name=name, description=description, points=points,
                 claimed=False, points_awarded=0, claimed_at=None)
            for kind, (name, points, description) in MISSION_TYPES.items()
        ]}
        patcher = patch.object(lakbay, 'player_progress', return_value=progress)
        patcher.start()
        self.addCleanup(patcher.stop)
        db_patcher = patch.object(lakbay, 'mysql')
        db_patcher.start()
        self.addCleanup(db_patcher.stop)

    def sign_in(self, loggedin=True):
        with self.client.session_transaction() as session:
            session.update(loggedin=loggedin, id=1, username='Traveler')

    def test_all_destination_pages_require_login(self):
        for slug, *_ in PLACES:
            with self.subTest(slug=slug):
                response = self.client.get(f'/destinations/{slug}')
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, '/login')

    def test_each_page_renders_its_photo_missions_and_gallery_link(self):
        self.sign_in()
        for slug, destination, attraction, filename in PLACES:
            with self.subTest(slug=slug), patch.object(lakbay, 'render_template', wraps=render_template) as render:
                response = self.client.get(f'/destinations/{slug}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(render.call_args.args, (f'destinations/{slug}.html',))
                place = render.call_args.kwargs['place']
                self.assertEqual(place, {
                    'slug': slug, 'destination': destination, 'attraction': attraction,
                    'image': f'destinations/{filename}', 'has_photo': True,
                })
                self.assertEqual(render.call_args.kwargs['username'], 'Traveler')

                html = response.get_data(as_text=True)
                page = DestinationHTML(html)
                self.assertIn(destination, html)
                self.assertIn(attraction, html)
                self.assertTrue(any(
                    image['attrs'].get('src') == f'/static/destinations/{filename}'
                    for image in page.of_type('img')
                ))
                rows = [' '.join(row['text'].split()) for row in page.of_type('li')]
                for mission, score in (('Itinerary', 10), ('Local Foods', 15), ('Activities', 20)):
                    self.assertTrue(any(mission in row and f'{score} pts' in row for row in rows), rows)
                self.assertTrue(any(
                    ' '.join(button['text'].split()) == 'Scan a QR'
                    and button['attrs'].get('aria-controls') == 'mission-scanner'
                    for button in page.of_type('button')
                ))
                self.assertIn('scanner.js', html)
                self.assertIn('data-destination="' + slug + '"', html)
                self.assertTrue(any(
                    ' '.join(link['text'].split()).casefold() == 'back to gallery'
                    and link['attrs'].get('href') == '/dashboard'
                    for link in page.of_type('a')
                ))

    def test_unknown_destination_is_404_after_login(self):
        self.sign_in()
        for slug in ('unknown', 'Palawan', 'palawan.html'):
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(f'/destinations/{slug}').status_code, 404)

    def test_unknown_destination_also_requires_login(self):
        response = self.client.get('/destinations/unknown')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')

    def test_destination_uses_dashboard_session_membership_check(self):
        self.sign_in(loggedin=False)
        self.assertEqual(self.client.get('/destinations/palawan').status_code, 200)

    def test_missing_photo_uses_the_same_gallery_fallback(self):
        self.sign_in()
        with tempfile.TemporaryDirectory() as directory, patch.object(lakbay.app, '_static_folder', directory):
            photo = Path(directory) / 'destinations/vigan-calle-crisologo.jpg'
            photo.parent.mkdir()
            photo.write_bytes(b'photo fixture; route checks asset existence')
            gallery = self.client.get('/dashboard').get_data(as_text=True)
            palawan = self.client.get('/destinations/palawan').get_data(as_text=True)
            vigan = self.client.get('/destinations/vigan').get_data(as_text=True)
        self.assertIn('src="/static/destinations/photo-placeholder.svg"', palawan)
        self.assertIn('src="/static/destinations/vigan-calle-crisologo.jpg"', vigan)
        self.assertIn('src="/static/destinations/vigan-calle-crisologo.jpg"', gallery)


if __name__ == '__main__':
    unittest.main()
