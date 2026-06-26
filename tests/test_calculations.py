import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.verification.calculations import (
    calculate_change,
    calculate_percentage_change,
    direction,
)


class CalculationsTest(unittest.TestCase):
    def test_calculate_absolute_change_preserves_precision(self):
        self.assertAlmostEqual(calculate_change(19.944, 21.919), 1.975, places=6)
        self.assertAlmostEqual(calculate_change(40.4, 38.9), -1.5, places=6)

    def test_calculate_percentage_change_rounds_to_two_decimals(self):
        self.assertEqual(calculate_percentage_change(19.944, 21.919), 9.9)
        self.assertEqual(calculate_percentage_change(40.4, 38.9), -3.71)

    def test_calculate_percentage_change_returns_none_for_zero_base(self):
        self.assertIsNone(calculate_percentage_change(0.0, 5.55))

    def test_direction(self):
        self.assertEqual(direction(19.944, 21.919), "increase")
        self.assertEqual(direction(40.4, 38.9), "decrease")
        self.assertEqual(direction(5.55, 5.55), "no_change")


if __name__ == "__main__":
    unittest.main()
