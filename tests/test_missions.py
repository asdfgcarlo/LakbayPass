"""Import validation can be checked without a database."""
import unittest

from missions import assignment_conflicts, expected_cards


class MissionAssignmentTests(unittest.TestCase):
    def test_all_eighteen_assignments_are_unique(self):
        cards = expected_cards()
        self.assertEqual(len(cards), 18)
        self.assertEqual(len({card['qr_code'] for card in cards}), 18)
        self.assertEqual(sum(card['points'] for card in cards), 270)
        self.assertEqual(assignment_conflicts([dict(id=i, **card) for i, card in enumerate(cards, 1)]), [])

    def test_wrong_destination_mission_points_and_code_are_reported(self):
        original = expected_cards()[7]  # Cebu / Local Foods
        for field, wrong in (('destination_slug', 'palawan'), ('mission_type', 'itinerary'),
                             ('points', 999), ('qr_code', 'LP-WRONG123')):
            with self.subTest(field=field):
                row = dict(id=41, **original)
                row[field] = wrong
                conflicts = assignment_conflicts([row])
                self.assertTrue(conflicts)
                self.assertIn('Card 41', conflicts[0])

    def test_duplicate_rows_are_reported_without_mutation(self):
        original = dict(id=1, **expected_cards()[0])
        duplicate = dict(original, id=2)
        self.assertEqual(len(assignment_conflicts([original, duplicate])), 2)
        self.assertEqual(original['id'], 1)


if __name__ == '__main__':
    unittest.main()
