"""
test_trailing_sl.py
Unit tests for dynamic Trailing Stop Loss (TSL) calculation,
continuous gap trailing, and exit reason categorization.
"""

import unittest
from risk_manager import RiskManager
from simulation_engine import SimulationEngine
from strike_selector import SensexStrikeSelector
from signal_engine import SignalEngine
from trade_manager import TradeManager
from portfolio_manager import PortfolioManager

class TestTrailingStopLoss(unittest.TestCase):
    def setUp(self):
        # Using exact user-specified scenario:
        # entry=100, SL=20 pts (80), Trigger=10 pts (110), Lock=2 pts (102), Target=40 pts (140)
        self.rm = RiskManager(
            stop_loss_points=20.0,
            target_points=40.0,
            trail_trigger_points=10.0,
            trail_lock_points=2.0,
            enable_trailing_sl=True,
            min_holding_updates=3,
            min_holding_seconds=30.0
        )

    def test_initial_level_calculations(self):
        levels = self.rm.calculate_levels(100.0)
        self.assertEqual(levels["entry_price"], 100.0)
        self.assertEqual(levels["stop_loss_price"], 80.0)
        self.assertEqual(levels["target_price"], 140.0)
        self.assertEqual(levels["trail_trigger_price"], 110.0)
        self.assertEqual(levels["trail_lock_price"], 102.0)

    def test_user_scenario_step_by_step(self):
        """
        User Example Scenario:
        Entry=100, Initial SL=80, Trigger=10, Lock=2
        1. ltp=100 -> trailing_active=False, current_sl=80
        2. ltp=105 -> trailing_active=False, current_sl=80
        3. ltp=110 -> trailing_active=True, current_sl=102
        4. ltp=115 -> trailing_active=True, current_sl=107 (115 - 8)
        5. ltp=107 -> Exit: TRAIL SL HIT
        """
        # 1. Entry at 100
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=100.0,
            current_sl=80.0,
            trailing_active=False,
            elapsed_seconds=1.0,
            update_count=1
        )
        self.assertEqual(status, "HOLD")
        self.assertFalse(tsl_active)
        self.assertEqual(sl, 80.0)

        # 2. Price moves to 105 (below trigger 110)
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=105.0,
            current_sl=80.0,
            trailing_active=False,
            elapsed_seconds=2.0,
            update_count=2
        )
        self.assertEqual(status, "HOLD")
        self.assertFalse(tsl_active)
        self.assertEqual(sl, 80.0)

        # 3. Price reaches trigger 110 -> Trailing Activated! SL moved to 102 (+2 locked)
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=110.0,
            current_sl=80.0,
            trailing_active=False,
            elapsed_seconds=3.0,
            update_count=3
        )
        self.assertEqual(status, "HOLD")
        self.assertTrue(tsl_active)
        self.assertEqual(sl, 102.0)

        # 4. Price advances to 115 -> Continuous Trailing SL moves to 107
        # trail_gap = 10 - 2 = 8 pts -> new_sl = 115 - 8 = 107
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=115.0,
            current_sl=102.0,
            trailing_active=True,
            elapsed_seconds=4.0,
            update_count=4
        )
        self.assertEqual(status, "HOLD")
        self.assertTrue(tsl_active)
        self.assertEqual(sl, 107.0)

        # 5. Price retraces to 107 -> Hit Trailing SL!
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=107.0,
            current_sl=107.0,
            trailing_active=True,
            elapsed_seconds=5.0,
            update_count=5
        )
        self.assertEqual(status, "EXIT_TRAIL_STOPLOSS")
        self.assertIn("TRAIL SL HIT", reason)

    def test_target_hit(self):
        """Target hit at 140 or above triggers TARGET HIT."""
        status, reason, sl, tsl_active = self.rm.evaluate_tick(
            entry_price=100.0,
            current_price=140.0,
            current_sl=80.0,
            trailing_active=False,
            elapsed_seconds=1.0,
            update_count=1
        )
        self.assertEqual(status, "EXIT_TARGET")
        self.assertIn("TARGET HIT", reason)

    def test_trailing_disabled(self):
        """When enable_trailing_sl is False, SL never trails."""
        rm_no_tsl = RiskManager(
            stop_loss_points=20.0,
            target_points=40.0,
            trail_trigger_points=10.0,
            trail_lock_points=2.0,
            enable_trailing_sl=False,
            min_holding_updates=3,
            min_holding_seconds=30.0
        )
        status, reason, sl, tsl_active = rm_no_tsl.evaluate_tick(
            entry_price=100.0,
            current_price=115.0,
            current_sl=80.0,
            trailing_active=False,
            elapsed_seconds=10.0,
            update_count=5
        )
        self.assertEqual(status, "HOLD")
        self.assertFalse(tsl_active)
        self.assertEqual(sl, 80.0)

    def test_simulation_engine_tsl_lifecycle(self):
        """Test full SimulationEngine trade lifecycle with Trailing SL."""
        engine = SimulationEngine(
            risk_manager=self.rm,
            max_trades_per_day=5,
            auto_schedule=False
        )

        # Open trade
        open_res = engine.open_trade(side="CALL", strike=77500, entry_price=100.0, timestamp="2026-08-20 10:00:00")
        self.assertEqual(open_res["status"], "SUCCESS")
        self.assertEqual(engine.active_trade["stop_loss"], 80.0)
        self.assertFalse(engine.active_trade["trailing_active"])

        # Price ticks up to 110 (trigger)
        up_res = engine.update_trade(current_price=110.0, strike=77500, option_type="CE", timestamp="2026-08-20 10:01:00")
        self.assertEqual(up_res["event"], "TRADE_UPDATED")
        self.assertTrue(engine.active_trade["trailing_active"])
        self.assertEqual(engine.active_trade["stop_loss"], 102.0)

        # Price advances to 120 -> SL moves to 112 (120 - 8)
        up_res2 = engine.update_trade(current_price=120.0, strike=77500, option_type="CE", timestamp="2026-08-20 10:02:00")
        self.assertEqual(engine.active_trade["stop_loss"], 112.0)

        # Price drops to 112 -> Closed with TRAIL SL HIT
        close_res = engine.update_trade(current_price=112.0, strike=77500, option_type="CE", timestamp="2026-08-20 10:03:00")
        self.assertEqual(close_res["event"], "TRADE_CLOSED")
        self.assertIn("TRAIL SL HIT", close_res["trade"]["exit_reason"])
        self.assertGreater(close_res["trade"]["pnl_points"], 0) # Locked profit (+12 pts)

if __name__ == "__main__":
    unittest.main()
