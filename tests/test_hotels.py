"""Hotel catalog, destination rendering and missing-asset regressions; no database."""
import copy
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from PIL import Image

import app as lakbay
from hotels import HOTEL_CATALOG, get_hotels
from missions import MISSION_TYPES


EXPECTED = {
    'palawan': ('Hue Hotels and Resorts Puerto Princesa',
                'San Manuel, Puerto Princesa, Palawan',
                'https://www.thehuehotel.com/hue-puerto-princesa'),
    'vigan': ('Hotel Luna', 'Vigan City, Ilocos Sur',
              'https://www.hotelluna.ph/public/home'),
    'cebu': ('Fantasy Lodge Cebu', 'Dalahikan, Samboan, Cebu',
             'https://fantasy-lodge.com/'),
    'siquijor': ('Coco Grove Beach Resort', 'Tubod, San Juan, Siquijor',
                 'https://www.cocogrovebeachresort.com/'),
    'siargao': ('Mariden Resort & Homestay Siargao',
                'Brgy. Lobogon, Del Carmen, Siargao, Surigao del Norte',
                'https://www.maridenresort.com/'),
    'camiguin': ('Camiguin Blue Lagoon Cottages',
                 'Taguines Lagoon, Benoni, Mahinog, Camiguin',
                 'https://camiguinbluelagoon.com/'),
}
FALLBACK_DESTINATIONS = {'cebu', 'siargao', 'camiguin'}
SUBTITLE = 'Find a comfortable place to stay during your adventure.'


class HotelHTML(HTMLParser):
    """Small semantic HTML collector, including descendant text and ancestors."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = dict(tag=tag, attrs=dict(attrs), text='',
                       ancestors=tuple(self.stack), index=len(self.elements))
        self.elements.append(element)
        if tag not in self.VOID:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for element in self.stack:
            element['text'] += data

    def find(self, tag=None, class_name=None, within=None):
        return [element for element in self.elements
                if (tag is None or element['tag'] == tag)
                and (class_name is None or class_name in
                     element['attrs'].get('class', '').split())
                and (within is None or any(parent is within
                                           for parent in element['ancestors']))]


def text(element):
    return ' '.join(element['text'].split())


class HotelCatalogTests(unittest.TestCase):
    def assert_https(self, url):
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, 'https', url)
        self.assertTrue(parsed.netloc, url)
        self.assertIsNone(parsed.username, url)

    def test_six_destinations_have_source_checked_local_properties(self):
        self.assertEqual(set(HOTEL_CATALOG['destinations']), set(EXPECTED))
        self.assertRegex(HOTEL_CATALOG['verified_on'], r'^\d{4}-\d{2}-\d{2}$')
        for slug, (name, location, url) in EXPECTED.items():
            with self.subTest(slug=slug):
                hotels = HOTEL_CATALOG['destinations'][slug]
                self.assertGreaterEqual(len(hotels), 1)
                self.assertLessEqual(len(hotels), 3)
                matches = [hotel for hotel in hotels if hotel['name'] == name]
                self.assertEqual(len(matches), 1)
                hotel = matches[0]
                self.assertEqual(hotel['location'], location)
                self.assertEqual(hotel['url'], url)
                self.assert_https(hotel['url'])
                # Initials and Gen. in street names do not end a sentence.
                prose = re.sub(r'\b(?:[A-Z]|Gen)\.(?=\s+[A-Z])', '',
                               hotel['description'].strip())
                self.assertEqual(len(re.split(r'(?<=[.!?])\s+', prose)), 2)
                self.assertTrue(hotel['description'].endswith('.'))
                self.assertGreaterEqual(len(hotel['sources']), 1)
                for source in hotel['sources']:
                    self.assert_https(source['url'])
                    self.assertTrue(source['supports'].strip())
                if slug in FALLBACK_DESTINATIONS:
                    self.assertIsNone(hotel['photo'])
                    self.assertIn('approved', hotel['photo_status'].lower())

    def test_licensed_photos_are_real_local_webp_variants_with_provenance(self):
        for slug in set(EXPECTED) - FALLBACK_DESTINATIONS:
            with self.subTest(slug=slug):
                hotel = get_hotels(slug, lakbay.app.static_folder)[0]
                photo = hotel['photo']
                self.assertIn(photo['license'], {'CC BY 2.0', 'CC BY-SA 4.0'})
                for field in ('author', 'alt', 'changes'):
                    self.assertTrue(photo[field].strip(), field)
                for field in ('source_url', 'original_url', 'license_url', 'author_url'):
                    self.assert_https(photo[field])
                self.assertIn('commons.wikimedia.org', photo['source_url'])
                self.assertIn('creativecommons.org/licenses/', photo['license_url'])
                for field, width in (('image', 640), ('image_large', 960)):
                    self.assertIsNotNone(hotel[field])
                    asset = Path(lakbay.app.static_folder) / hotel[field]
                    with Image.open(asset) as image:
                        self.assertEqual(image.format, 'WEBP')
                        self.assertEqual(image.width, width)
                        self.assertGreater(image.height, 0)
                    provenance = json.loads(Path(str(asset) + '.json').read_text(encoding='utf-8'))
                    self.assertIn(photo['source_url'], provenance['prompt'])
                    self.assertIn(photo['author'], provenance['prompt'])
                    self.assertIn(photo['license'], provenance['prompt'])

    def test_absent_static_folder_preserves_content_without_photo_references(self):
        before = copy.deepcopy(HOTEL_CATALOG)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'static-not-present'
            for slug, (name, *_rest) in EXPECTED.items():
                with self.subTest(slug=slug):
                    hotel = get_hotels(slug, missing)[0]
                    self.assertEqual(hotel['name'], name)
                    self.assertIsNone(hotel['image'])
                    self.assertIsNone(hotel['image_large'])
        self.assertEqual(HOTEL_CATALOG, before)
        self.assertEqual(get_hotels('unknown', lakbay.app.static_folder), [])

    def test_missing_large_variant_still_uses_base_and_missing_base_never_uses_large(self):
        photo = HOTEL_CATALOG['destinations']['vigan'][0]['photo']
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'hotels'
            folder.mkdir()
            base = folder / f"{photo['asset_base']}-640.webp"
            large = folder / f"{photo['asset_base']}-960.webp"
            base.write_bytes(b'asset presence fixture')
            hotel = get_hotels('vigan', directory)[0]
            self.assertEqual(hotel['image'], 'hotels/hotel-luna-640.webp')
            self.assertIsNone(hotel['image_large'])
            base.unlink()
            large.write_bytes(b'asset presence fixture')
            hotel = get_hotels('vigan', directory)[0]
            self.assertIsNone(hotel['image'])
            self.assertIsNone(hotel['image_large'])


class HotelRouteTests(unittest.TestCase):
    def setUp(self):
        lakbay.app.config['TESTING'] = True
        self.client = lakbay.app.test_client()
        progress = dict(total_points=45, missions=[
            dict(mission_type=kind, name=name, description=description, points=points,
                 claimed=False, points_awarded=0, claimed_at=None)
            for kind, (name, points, description) in MISSION_TYPES.items()
        ])
        for patcher in (patch.object(lakbay, 'mysql', SimpleNamespace(connection=object())),
                        patch.object(lakbay, 'player_progress', return_value=progress)):
            patcher.start()
            self.addCleanup(patcher.stop)
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=42, username='Hotel tester')

    def page(self, slug):
        response = self.client.get(f'/destinations/{slug}')
        self.assertEqual(response.status_code, 200)
        return HotelHTML(response.get_data(as_text=True))

    def test_matching_hotel_section_is_between_overview_and_original_missions(self):
        for slug, (name, location, url) in EXPECTED.items():
            with self.subTest(slug=slug):
                page = self.page(slug)
                sections = page.find('section', 'hotel-recommendations')
                self.assertEqual(len(sections), 1)
                section = sections[0]
                self.assertEqual(section['attrs']['aria-labelledby'], 'hotels-title')
                self.assertEqual([text(h) for h in page.find('h2', within=section)], ['Where to Stay'])
                self.assertEqual([text(p) for p in page.find('p', within=page.find(class_name='hotels-heading')[0])],
                                 [SUBTITLE])
                self.assertLess(page.find('article', 'destination-overview')[0]['index'], section['index'])
                self.assertLess(section['index'], page.find('section', 'missions')[0]['index'])
                cards = page.find('li', 'hotel-card', within=section)
                self.assertGreaterEqual(len(cards), 1)
                self.assertLessEqual(len(cards), 3)
                self.assertIn(name, [text(h) for h in page.find('h3', within=section)])
                self.assertIn(location, [text(p) for p in page.find(class_name='hotel-location', within=section)])
                link = next(link for link in page.find('a', 'hotel-link', within=section)
                            if link['attrs']['href'] == url)
                self.assertEqual(text(link), 'View Hotel')
                self.assertEqual(link['attrs']['target'], '_blank')
                self.assertTrue({'noopener', 'noreferrer'} <= set(link['attrs']['rel'].split()))
                self.assertIn('opens in a new tab', link['attrs']['aria-label'])
                self.assertEqual(page.find('form', within=section), [])
                self.assertEqual(len(page.find('li', within=page.find('ul', 'mission-list')[0])), 3)
                self.assertEqual([text(h) for h in page.find('h3', within=page.find('ul', 'mission-list')[0])],
                                 [value[0] for value in MISSION_TYPES.values()])
                scanner = next(button for button in page.find('button')
                               if button['attrs'].get('id') == 'open-scanner')
                self.assertEqual(text(scanner), 'Scan a QR')
                self.assertEqual(scanner['attrs']['aria-controls'], 'mission-scanner')
                self.assertEqual(page.find('a', 'back-to-gallery')[0]['attrs']['href'], '/dashboard')
                scripts = {script['attrs'].get('src'): script for script in page.find('script')}
                self.assertIn('/static/scanner.js', scripts)
                self.assertIn('defer', scripts['/static/hotels.js']['attrs'])

    def test_visible_photo_has_attribution_and_no_unlicensed_substitutions(self):
        for slug in EXPECTED:
            with self.subTest(slug=slug):
                page = self.page(slug)
                card = page.find('li', 'hotel-card')[0]
                images = page.find('img', 'hotel-image', within=card)
                credits = page.find('figcaption', 'hotel-photo-credit', within=card)
                fallback = page.find(class_name='hotel-photo-fallback', within=card)[0]
                self.assertIn('Property photo unavailable', text(fallback))
                if slug in FALLBACK_DESTINATIONS:
                    self.assertEqual(images, [])
                    self.assertEqual(credits, [])
                    self.assertNotIn('hidden', fallback['attrs'])
                    continue
                hotel = get_hotels(slug, lakbay.app.static_folder)[0]
                photo = hotel['photo']
                self.assertEqual(len(images), 1)
                self.assertEqual(images[0]['attrs']['src'], '/static/' + hotel['image'])
                self.assertIn('/static/' + hotel['image_large'], images[0]['attrs']['srcset'])
                self.assertEqual(images[0]['attrs']['alt'], photo['alt'])
                self.assertEqual(images[0]['attrs']['loading'], 'lazy')
                self.assertEqual(len(credits), 1)
                self.assertIn(photo['author'], text(credits[0]))
                self.assertIn(photo['license'], text(credits[0]))
                self.assertIn('resized / cropped', text(credits[0]))
                links = {link['attrs']['href'] for link in page.find('a', within=credits[0])}
                self.assertEqual(links, {photo['source_url'], photo['license_url']})
                self.assertIn('hidden', fallback['attrs'])

    def test_all_cards_render_honest_fallback_when_static_assets_are_absent(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(lakbay.app, '_static_folder', directory):
            for slug, (name, _location, url) in EXPECTED.items():
                with self.subTest(slug=slug):
                    page = self.page(slug)
                    section = page.find('section', 'hotel-recommendations')[0]
                    self.assertEqual(page.find('img', within=section), [])
                    self.assertEqual(page.find('figcaption', within=section), [])
                    fallback = page.find(class_name='hotel-photo-fallback', within=section)[0]
                    self.assertNotIn('hidden', fallback['attrs'])
                    self.assertIn('Property photo unavailable', text(fallback))
                    self.assertIn(name, text(section))
                    self.assertEqual(page.find('a', 'hotel-link', within=section)[0]['attrs']['href'], url)


if __name__ == '__main__':
    unittest.main()
