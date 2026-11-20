"""Profile identity, earned points, tier boundaries, and mission completion."""
import copy
import unittest
from unittest.mock import MagicMock, patch

import MySQLdb

import app as lakbay
from missions import player_profile, player_tier


def profile_fixture(total=25, claims=None, username='Traveler', balance=None):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [{'username': username}, {'total': total},
                                 {'total': total if balance is None else balance}]
    cursor.fetchall.return_value = claims if claims is not None else [
        {'destination_slug': 'palawan', 'mission_type': 'itinerary', 'claim_id': 1},
        {'destination_slug': 'palawan', 'mission_type': 'local_foods', 'claim_id': 2},
        {'destination_slug': 'palawan', 'mission_type': 'activities', 'claim_id': None},
    ]
    return player_profile(connection, 42), cursor


class ProfileDataTests(unittest.TestCase):
    def test_tier_boundaries(self):
        for total, expected in ((0, 'Bronze'), (90, 'Bronze'), (91, 'Silver'),
                                (180, 'Silver'), (181, 'Gold'), (270, 'Gold')):
            with self.subTest(total=total):
                self.assertEqual(player_tier(total), expected)

    def test_two_claims_leave_activities_unclaimed_and_other_places_unvisited(self):
        profile, cursor = profile_fixture()
        self.assertEqual(profile['username'], 'Traveler')
        self.assertEqual(profile['total_points'], 25)
        self.assertEqual(profile['max_points'], 270)
        self.assertEqual(profile['visited_count'], 1)
        self.assertEqual(profile['claimed_count'], 2)
        self.assertEqual(len(profile['destinations']), 6)
        palawan = profile['destinations']['palawan']
        self.assertEqual(palawan['claimed_count'], 2)
        self.assertEqual([mission['claimed'] for mission in palawan['missions']], [True, True, False])
        self.assertEqual(profile['destinations']['cebu']['claimed_count'], 0)
        for call in cursor.execute.call_args_list:
            self.assertIn(call.args[1], ((42,), (42, 42)))

    def test_spending_preserves_lifetime_points_and_tier(self):
        profile, _ = profile_fixture(total=270, balance=0)
        self.assertEqual(profile['total_points'], 270)
        self.assertEqual(profile['available_points'], 0)
        self.assertEqual(profile['tier'], 'Gold')

    def test_no_claims_is_a_valid_bronze_profile(self):
        profile, _ = profile_fixture(total=0, claims=[])
        self.assertEqual(profile['tier'], 'Bronze')
        self.assertEqual(profile['visited_count'], 0)
        self.assertEqual(profile['claimed_count'], 0)
        self.assertTrue(all(place['claimed_count'] == 0 for place in profile['destinations'].values()))

    def test_duplicate_rows_do_not_inflate_mission_completion(self):
        claim = {'destination_slug': 'palawan', 'mission_type': 'itinerary', 'claim_id': 1}
        profile, _ = profile_fixture(total=10, claims=[claim, dict(claim)])
        self.assertEqual(profile['claimed_count'], 1)
        self.assertEqual(profile['destinations']['palawan']['claimed_count'], 1)

    def test_all_missions_complete(self):
        # Keep this mapping independent of the production QR assignments.
        claims = [dict(destination_slug=slug, mission_type=kind, claim_id=number)
                  for number, (slug, kind) in enumerate(
                      ((slug, kind) for slug in ('palawan', 'vigan', 'cebu', 'siquijor', 'siargao', 'camiguin')
                       for kind in ('itinerary', 'local_foods', 'activities')), 1)]
        profile, _ = profile_fixture(total=270, claims=claims)
        self.assertEqual(profile['tier'], 'Gold')
        self.assertEqual(profile['visited_count'], 6)
        self.assertEqual(profile['claimed_count'], 18)
        self.assertTrue(all(place['claimed_count'] == 3 for place in profile['destinations'].values()))

    def test_missing_account_is_not_an_empty_profile(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        self.assertIsNone(player_profile(connection, 42))
        connection.cursor.return_value.close.assert_called_once()


class ProfileRouteTests(unittest.TestCase):
    def setUp(self):
        lakbay.app.config['TESTING'] = True
        self.client = lakbay.app.test_client()
        self.fixture, _ = profile_fixture()
        self.database_patch = patch.object(lakbay, 'mysql')
        self.database = self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.profile_patch = patch.object(lakbay, 'player_profile', return_value=self.fixture)
        self.profile_reader = self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    def sign_in(self):
        with self.client.session_transaction() as session:
            session.update(loggedin=True, id=42, username='Session name')

    def test_login_is_required(self):
        self.assertEqual(self.client.get('/profile').location, '/login')
        self.profile_reader.assert_not_called()

    def test_invalid_session_identity_is_rejected(self):
        for player_id in (0, '42', None):
            with self.subTest(player_id=player_id):
                with self.client.session_transaction() as session:
                    session.update(loggedin=True, id=player_id)
                self.assertEqual(self.client.get('/profile').location, '/login')
        self.profile_reader.assert_not_called()

    def test_profile_uses_session_account_and_shows_the_unclaimed_mission(self):
        self.sign_in()
        response = self.client.get('/profile?user_id=99')
        self.assertEqual(response.status_code, 200)
        self.profile_reader.assert_called_once_with(self.database.connection, 42)
        self.assertIn(b'Traveler', response.data)
        self.assertIn(b'Bronze tier', response.data)
        self.assertIn(b'id="profile-points">25</strong>', response.data)
        self.assertIn(b' / 270', response.data)
        self.assertIn(b'2/3', response.data)
        self.assertIn(b'Activities', response.data)
        self.assertIn(b'Not claimed', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.data.count(b'class="destination-progress"'), 6)

    def test_username_is_escaped(self):
        self.sign_in()
        self.fixture['username'] = '<script>alert(1)</script>'
        response = self.client.get('/profile')
        self.assertIn(b'&lt;script&gt;', response.data)
        self.assertNotIn(b'<script>alert(1)</script>', response.data)

    def test_new_user_has_clear_first_claim_instructions(self):
        self.sign_in()
        self.profile_reader.return_value, _ = profile_fixture(total=0, claims=[])
        response = self.client.get('/profile')
        self.assertIn(b'No places visited yet.', response.data)
        self.assertEqual(response.data.count(b'<strong>0/3</strong>'), 6)

    def test_revisit_recomputes_the_tier(self):
        self.sign_in()
        silver = copy.deepcopy(self.fixture)
        silver.update(total_points=91, tier='Silver')
        self.profile_reader.side_effect = [self.fixture, silver]
        self.assertIn(b'Bronze tier', self.client.get('/profile').data)
        self.assertIn(b'Silver tier', self.client.get('/profile').data)

    def test_missing_user_clears_the_expired_session(self):
        self.sign_in()
        self.profile_reader.return_value = None
        self.assertEqual(self.client.get('/profile').location, '/login')
        with self.client.session_transaction() as session:
            self.assertNotIn('loggedin', session)

    def test_database_failure_displays_retry_without_invented_progress(self):
        self.sign_in()
        self.profile_reader.side_effect = MySQLdb.OperationalError(2003, 'Connection unavailable')
        with self.assertLogs(lakbay.app.logger, level='ERROR'):
            response = self.client.get('/profile')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'Your progress could not be loaded.', response.data)
        self.assertIn(b'Try again', response.data)
        self.assertNotIn(b'Bronze tier', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
