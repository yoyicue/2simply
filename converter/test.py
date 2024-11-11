import unittest
from src.duration import DurationManager

class TestDurationManager(unittest.TestCase):
    def test_create_music21_duration(self):
        test_cases = [
            (4.0, 'whole', 0),
            (3.0, 'half', 1),
            (2.0, 'half', 0),
            (1.5, 'quarter', 1),
            (1.0, 'quarter', 0),
            (0.75, 'eighth', 1),
            (0.5, 'eighth', 0),
            (0.25, '16th', 0)
        ]
        
        for quarter_length, expected_type, expected_dots in test_cases:
            with self.subTest(quarter_length=quarter_length):
                duration = DurationManager.create_music21_duration(quarter_length)
                self.assertEqual(duration.type, expected_type)
                self.assertEqual(duration.dots, expected_dots)
                self.assertAlmostEqual(duration.quarterLength, quarter_length, places=2)

if __name__ == '__main__':
    unittest.main()