"""
test_clear_trades.py
Unit tests for clearing today's closed trades audit log.
"""

import unittest
import os
import shutil
import tempfile
from portfolio_manager import PortfolioManager
from logger import AuditLogger
from main import SensexSimulationSystem
from data_feed import SimulatedLiveFeedAdapter

class TestClearTrades(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_portfolio_manager_clear_today_trades(self):
        pm = PortfolioManager(lot_size=20)
        pm.record_closed_trade({
            "trade_id": 1,
            "side": "CALL",
            "strike": 77500,
            "entry_price": 200.0,
            "exit_price": 250.0,
            "entry_time": "2026-08-19 10:00:00",
            "exit_time": "2026-08-19 10:10:00",
            "pnl_points": 50.0,
            "pnl_rupees": 1000.0
        })
        pm.record_closed_trade({
            "trade_id": 2,
            "side": "PUT",
            "strike": 77100,
            "entry_price": 200.0,
            "exit_price": 180.0,
            "entry_time": "2026-08-18 14:00:00",
            "exit_time": "2026-08-18 14:15:00",
            "pnl_points": -20.0,
            "pnl_rupees": -400.0
        })

        self.assertEqual(len(pm.trades), 2)
        cleared = pm.clear_today_trades("2026-08-19")
        self.assertEqual(cleared, 1)
        self.assertEqual(len(pm.trades), 1)
        self.assertEqual(pm.trades[0]["trade_id"], 2)
        self.assertEqual(pm.total_pnl_rupees, -400.0)

    def test_audit_logger_clear_today_trades(self):
        logger = AuditLogger(log_dir=self.test_dir)
        logger.log_closed_trade({
            "trade_id": 1,
            "side": "CALL",
            "strike": 77500,
            "symbol": "SENSEX26AUG77500CE",
            "entry_time": "2026-08-19 10:00:00",
            "exit_time": "2026-08-19 10:10:00",
            "entry_price": 200.0,
            "exit_price": 250.0,
            "exit_reason": "TARGET_HIT",
            "pnl_points": 50.0,
            "pnl_rupees": 1000.0,
            "lot_size": 20
        })
        logger.log_closed_trade({
            "trade_id": 2,
            "side": "PUT",
            "strike": 77100,
            "symbol": "SENSEX26AUG77100PE",
            "entry_time": "2026-08-18 14:00:00",
            "exit_time": "2026-08-18 14:15:00",
            "entry_price": 200.0,
            "exit_price": 180.0,
            "exit_reason": "STOP_LOSS",
            "pnl_points": -20.0,
            "pnl_rupees": -400.0,
            "lot_size": 20
        })

        cleared = logger.clear_today_trades("2026-08-19")
        self.assertEqual(cleared, 1)

        with open(logger.trades_audit_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 1 header line + 1 remaining trade row
        self.assertEqual(len(lines), 2)
        self.assertIn("SENSEX26AUG77100PE", lines[1])

    def test_system_clear_today_trades(self):
        system = SensexSimulationSystem(feed_adapter=SimulatedLiveFeedAdapter())
        system.portfolio_manager.record_closed_trade({
            "trade_id": 1,
            "side": "CALL",
            "strike": 77500,
            "entry_price": 200.0,
            "exit_price": 250.0,
            "entry_time": "2026-08-19 10:00:00",
            "exit_time": "2026-08-19 10:10:00",
            "pnl_points": 50.0,
            "pnl_rupees": 1000.0
        })
        res = system.clear_today_trades("2026-08-19")
        self.assertEqual(res["cleared_memory"], 1)
        self.assertEqual(len(system.portfolio_manager.get_trade_history()), 0)

if __name__ == "__main__":
    unittest.main()
