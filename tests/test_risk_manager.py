"""
test_risk_manager.py
Unit tests for RiskManager SL/TP levels, noise suppression, and zero-clamping safety.
"""

import unittest
from risk_manager import RiskManager

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager(
            stop_loss_points=50.0,
            target_points=100.0,
            min_holding_updates=3,
            min_holding_seconds=30.0
        )

    def test_level_calculations(self):
        entry = 250.0
        levels = self.rm.calculate_levels(entry)
        self.assertEqual(levels["entry_price"], 250.0)
        self.assertEqual(levels["stop_loss_price"], 200.0) # 250 - 50
        self.assertEqual(levels["target_price"], 350.0)    # 250 + 100

    def test_target_profit_immediate_hit(self):
        """Target profit should trigger immediately even on update #1 / 1 second."""
        status, reason = self.rm.check_exit(
            entry_price=200.0,
            current_price=300.0, # exact +100 target
            elapsed_seconds=1.0,
            update_count=1
        )
        self.assertEqual(status, "EXIT_TARGET")
        self.assertIn("TARGET HIT", reason)

    def test_stop_loss_suppression_during_holding_period(self):
        """Fix #5: Stop-loss must be suppressed if holding threshold is not met."""
        # Entry 200, SL at 150. Price drops to 140 (SL breach), but updates=1 (< 3) and seconds=5 (< 30)
        status, reason = self.rm.check_exit(
            entry_price=200.0,
            current_price=140.0,
            elapsed_seconds=5.0,
            update_count=1
        )
        self.assertEqual(status, "HOLD")
        self.assertIn("SL suppressed", reason)

    def test_stop_loss_triggers_after_holding_period(self):
        """Stop-loss triggers once update count or seconds threshold is met."""
        # Updates = 3 (>= min_holding_updates)
        status, reason = self.rm.check_exit(
            entry_price=200.0,
            current_price=148.0,
            elapsed_seconds=10.0,
            update_count=3
        )
        self.assertEqual(status, "EXIT_STOPLOSS")
        self.assertIn("STOP LOSS HIT", reason)

    def test_exact_boundary_hits(self):
        # Exact SL boundary (200 - 50 = 150)
        status_sl, _ = self.rm.check_exit(200.0, 150.0, elapsed_seconds=35.0, update_count=4)
        self.assertEqual(status_sl, "EXIT_STOPLOSS")

        # Exact TP boundary (200 + 100 = 300)
        status_tp, _ = self.rm.check_exit(200.0, 300.0, elapsed_seconds=2.0, update_count=1)
        self.assertEqual(status_tp, "EXIT_TARGET")

    def test_negative_price_clamping(self):
        """Fix #8: Negative price is clamped to 0.0 without throwing exceptions."""
        status, _ = self.rm.check_exit(200.0, -15.0, elapsed_seconds=40.0, update_count=5)
        self.assertEqual(status, "EXIT_STOPLOSS")

if __name__ == "__main__":
    unittest.main()
