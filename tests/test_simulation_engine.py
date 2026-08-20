"""
test_simulation_engine.py
Unit tests for SimulationEngine lifecycle, locked instrument enforcement, and portfolio P&L on Sensex.
"""

import unittest
from simulation_engine import SimulationEngine
from strike_selector import SensexStrikeSelector
from signal_engine import SignalEngine
from trade_manager import TradeManager
from risk_manager import RiskManager
from portfolio_manager import PortfolioManager

class TestSimulationEngine(unittest.TestCase):
    def setUp(self):
        self.selector = SensexStrikeSelector(strike_distance=200, strike_interval=100)
        self.signal_engine = SignalEngine(confirmation_candles=1)
        self.trade_manager = TradeManager()
        self.risk_manager = RiskManager(stop_loss_points=50, target_points=100, min_holding_updates=2)
        self.portfolio_manager = PortfolioManager(lot_size=10) # Sensex standard lot size
        
        self.sim = SimulationEngine(
            strike_selector=self.selector,
            signal_engine=self.signal_engine,
            trade_manager=self.trade_manager,
            risk_manager=self.risk_manager,
            portfolio_manager=self.portfolio_manager
        )

    def test_trade_lifecycle_open_update_target_exit(self):
        # Open trade
        open_res = self.sim.open_trade(side="CALL", strike=81300, entry_price=300.0, timestamp="2026-08-18 09:30:00")
        self.assertEqual(open_res["event"], "TRADE_OPENED")
        self.assertIsNotNone(self.sim.active_trade)
        self.assertEqual(self.sim.active_trade["strike"], 81300)
        self.assertEqual(self.sim.active_trade["symbol"], "SENSEX_81300_CE")

        # Update trade (within range)
        up_res = self.sim.update_trade(current_price=340.0, strike=81300, option_type="CE", timestamp="2026-08-18 09:31:00")
        self.assertEqual(up_res["event"], "TRADE_UPDATED")
        self.assertEqual(self.sim.active_trade["unrealized_pnl_points"], 40.0)

        # Target hit (+100 pts -> 400.0)
        close_res = self.sim.update_trade(current_price=405.0, strike=81300, option_type="CE", timestamp="2026-08-18 09:32:00")
        self.assertEqual(close_res["event"], "TRADE_CLOSED")
        self.assertIsNone(self.sim.active_trade)
        
        # Portfolio stats check
        self.assertEqual(len(self.portfolio_manager.trades), 1)
        self.assertEqual(self.portfolio_manager.total_pnl_points, 105.0)
        self.assertEqual(self.portfolio_manager.total_pnl_rupees, 105.0 * 10)
        self.assertEqual(self.sim.total_pnl, 105.0)

    def test_locked_instrument_enforcement(self):
        """Updating with wrong strike or option type must be rejected."""
        self.sim.open_trade(side="CALL", strike=81300, entry_price=300.0)

        # Update with wrong strike (81400 instead of locked 81300)
        res_mismatch = self.sim.update_trade(current_price=310.0, strike=81400, option_type="CE")
        self.assertEqual(res_mismatch["event"], "INSTRUMENT_LOCK_ERROR")
        self.assertEqual(res_mismatch["status"], "REJECTED")

        # Active trade remains unchanged
        self.assertEqual(self.sim.active_trade["strike"], 81300)
        self.assertEqual(self.sim.active_trade["current_price"], 300.0)

    def test_process_market_tick_full_cycle(self):
        indicator_data_call = {
            "rsi_5m": 65.0, "rsi_15m": 65.0, "ema20_5m": 81400.0, "adx_5m": 35.0, "close_5m": 81500.0
        }
        quotes = {
            "81300_CE": {"ltp": 350.0, "mid_price": 350.0},
            "81700_PE": {"ltp": 320.0, "mid_price": 320.0}
        }
        
        # 1. First tick -> CALL signal generated & opened on 81300 CE
        res1 = self.sim.process_market_tick(
            sensex_ltp=81500.0,
            indicator_data=indicator_data_call,
            option_quotes=quotes,
            timestamp="2026-08-18 09:30:00"
        )
        self.assertEqual(res1["event"], "TRADE_OPENED")
        self.assertEqual(self.sim.active_trade["side"], "CALL")
        self.assertEqual(self.sim.active_trade["strike"], 81300)
        self.assertEqual(self.sim.active_trade["symbol"], "SENSEX_81300_CE")

        # 2. Next tick while active trade is open -> updates locked position
        quotes_update = {
            "81300_CE": {"ltp": 370.0, "mid_price": 370.0}
        }
        res2 = self.sim.process_market_tick(
            sensex_ltp=81550.0,
            indicator_data=indicator_data_call,
            option_quotes=quotes_update,
            timestamp="2026-08-18 09:31:00"
        )
        self.assertEqual(res2["event"], "TRADE_UPDATED")
        self.assertEqual(self.sim.active_trade["unrealized_pnl_points"], 20.0)

    def test_alternation_enforcement_in_open_trade(self):
        """Verifies that consecutive trades of the same side (CALL -> CALL or PUT -> PUT) are strictly blocked."""
        # 1. Open and close first trade (CALL)
        res1 = self.sim.open_trade(side="CALL", strike=81300, entry_price=300.0)
        self.assertEqual(res1["event"], "TRADE_OPENED")
        self.assertEqual(res1["status"], "SUCCESS")
        self.sim.close_trade(exit_price=350.0, exit_reason="TARGET")
        self.assertIsNone(self.sim.active_trade)

        # 2. Attempt to open second CALL trade -> MUST BE REJECTED
        res2 = self.sim.open_trade(side="CALL", strike=81300, entry_price=300.0)
        self.assertEqual(res2["event"], "SIGNAL_REJECTED")
        self.assertEqual(res2["status"], "REJECTED")
        self.assertIn("strictly alternating trades required", res2["reason"])
        self.assertEqual(res2["next_required"], "PUT")
        self.assertIsNone(self.sim.active_trade)

        # 3. Open alternating PUT trade -> MUST SUCCEED
        res3 = self.sim.open_trade(side="PUT", strike=81700, entry_price=280.0)
        self.assertEqual(res3["event"], "TRADE_OPENED")
        self.assertEqual(res3["status"], "SUCCESS")
        self.sim.close_trade(exit_price=330.0, exit_reason="TARGET")

        # 4. Attempt to open second PUT trade -> MUST BE REJECTED
        res4 = self.sim.open_trade(side="PUT", strike=81700, entry_price=280.0)
        self.assertEqual(res4["event"], "SIGNAL_REJECTED")
        self.assertEqual(res4["status"], "REJECTED")
        self.assertEqual(res4["next_required"], "CALL")

    def test_overlapping_trade_prevention(self):
        """Verifies that a new trade cannot be opened while an active trade is running."""
        res1 = self.sim.open_trade(side="CALL", strike=81300, entry_price=300.0)
        self.assertEqual(res1["event"], "TRADE_OPENED")

        # Attempt to open PUT while CALL is still active
        res2 = self.sim.open_trade(side="PUT", strike=81700, entry_price=280.0)
        self.assertEqual(res2["event"], "ALREADY_ACTIVE_TRADE")
        self.assertEqual(res2["status"], "REJECTED")
        self.assertEqual(self.sim.active_trade["side"], "CALL")

if __name__ == "__main__":
    unittest.main()
