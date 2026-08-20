"""
test_strike_selector.py
Unit tests for BSE Sensex Strike Selector.
"""

import unittest
from strike_selector import SensexStrikeSelector, BankNiftyStrikeSelector

class TestSensexStrikeSelector(unittest.TestCase):
    def setUp(self):
        self.selector = SensexStrikeSelector(strike_distance=200, strike_interval=100)

    def test_sample_case_81350(self):
        """Test LTP = 81350: ~200 pts OTM strikes."""
        res = self.selector.get_strikes(81350)
        # 81350 - 200 = 81150 -> rounded to 81200 (strictly < 81350)
        # 81350 + 200 = 81550 -> rounded to 81600 (strictly > 81350)
        self.assertLess(res["call_strike"], 81350)
        self.assertGreater(res["put_strike"], 81350)
        self.assertEqual(res["call_strike"] % 100, 0)
        self.assertEqual(res["put_strike"] % 100, 0)
        self.assertEqual(res["call_strike"], 81200)
        self.assertEqual(res["put_strike"], 81600)
        self.assertEqual(res["call_symbol"], "SENSEX_81200_CE")
        self.assertEqual(res["put_symbol"], "SENSEX_81600_PE")

    def test_exact_100_point_strike_boundary_80000(self):
        """Test LTP exactly on 100-point strike boundary: 80000."""
        res = self.selector.get_strikes(80000)
        # 80000 - 200 = 79800
        # 80000 + 200 = 80200
        self.assertEqual(res["call_strike"], 79800)
        self.assertEqual(res["put_strike"], 80200)
        self.assertLess(res["call_strike"], 80000)
        self.assertGreater(res["put_strike"], 80000)

    def test_exact_100_point_strike_boundary_81500(self):
        """Test LTP exactly on 81500."""
        res = self.selector.get_strikes(81500)
        self.assertEqual(res["call_strike"], 81300)
        self.assertEqual(res["put_strike"], 81700)

    def test_fractional_ltp(self):
        """Test fractional LTP values."""
        res = self.selector.get_strikes(81523.75)
        self.assertEqual(res["call_strike"], 81300)
        self.assertEqual(res["put_strike"], 81700)

    def test_invalid_ltp_raises(self):
        """Test that negative or 0 LTP raises ValueError."""
        with self.assertRaises(ValueError):
            self.selector.get_strikes(0)
        with self.assertRaises(ValueError):
            self.selector.get_strikes(-100)

if __name__ == "__main__":
    unittest.main()
