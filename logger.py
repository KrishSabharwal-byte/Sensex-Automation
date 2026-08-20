"""
logger.py
Audit Logging Engine for BSE Sensex Options Simulation.
Persists every market update, indicator snapshot, signal evaluation, and trade action to CSV.
"""

import os
import csv
import logging
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SensexSimulation")

class AuditLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.market_audit_file = os.path.join(self.log_dir, "market_ticks_audit.csv")
        self.trades_audit_file = os.path.join(self.log_dir, "trades_audit.csv")
        self.signals_audit_file = os.path.join(self.log_dir, "signals_audit.csv")
        
        self._init_files()

    def _init_files(self):
        # Market Ticks & Indicators Header
        if not os.path.exists(self.market_audit_file):
            with open(self.market_audit_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "sensex_ltp", "sensex_mid",
                    "rsi_5m", "rsi_15m", "ema20_5m", "adx_5m", "close_5m",
                    "call_strike", "put_strike",
                    "raw_signal", "confirmed_signal",
                    "active_trade_id", "active_trade_side", "active_trade_strike", "active_pnl_pts"
                ])

        # Signals Evaluation Header
        if not os.path.exists(self.signals_audit_file):
            with open(self.signals_audit_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "raw_signal", "confirmed_signal", "confirmation_count",
                    "next_required", "action_taken", "rejection_reason"
                ])

        # Closed Trades Header
        if not os.path.exists(self.trades_audit_file):
            with open(self.trades_audit_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "side", "strike", "symbol",
                    "entry_time", "exit_time",
                    "entry_price", "exit_price", "exit_reason",
                    "pnl_points", "pnl_rupees", "lot_size",
                    "duration_updates", "duration_seconds"
                ])

    def log_market_tick(
        self,
        timestamp: str,
        sensex_ltp: float = 0.0,
        sensex_mid: float = 0.0,
        indicators: Optional[Dict[str, Any]] = None,
        strikes: Optional[Dict[str, Any]] = None,
        signal_state: Optional[Dict[str, Any]] = None,
        active_trade: Optional[Dict[str, Any]] = None,
        banknifty_ltp: Optional[float] = None,
        banknifty_mid: Optional[float] = None
    ):
        ltp = sensex_ltp or banknifty_ltp or 0.0
        mid = sensex_mid or banknifty_mid or 0.0
        indicators = indicators or {}
        strikes = strikes or {}
        signal_state = signal_state or {}

        trade_id = active_trade["trade_id"] if active_trade else ""
        trade_side = active_trade["side"] if active_trade else ""
        trade_strike = active_trade["strike"] if active_trade else ""
        trade_pnl = active_trade.get("unrealized_pnl_points", 0.0) if active_trade else ""

        with open(self.market_audit_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, ltp, mid,
                indicators.get("rsi_5m", ""),
                indicators.get("rsi_15m", ""),
                indicators.get("ema20_5m", ""),
                indicators.get("adx_5m", ""),
                indicators.get("close_5m", ""),
                strikes.get("call_strike", ""),
                strikes.get("put_strike", ""),
                signal_state.get("raw_signal", ""),
                signal_state.get("signal", ""),
                trade_id, trade_side, trade_strike, trade_pnl
            ])

    def log_signal_event(
        self,
        timestamp: str,
        raw_signal: str,
        confirmed_signal: str,
        confirmation_count: int,
        next_required: str,
        action_taken: str,
        rejection_reason: str = ""
    ):
        with open(self.signals_audit_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, raw_signal, confirmed_signal, confirmation_count,
                next_required, action_taken, rejection_reason
            ])

    def log_closed_trade(self, trade_data: Dict[str, Any]):
        with open(self.trades_audit_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade_data.get("trade_id", ""),
                trade_data.get("side", ""),
                trade_data.get("strike", ""),
                trade_data.get("symbol", ""),
                trade_data.get("entry_time", ""),
                trade_data.get("exit_time", ""),
                trade_data.get("entry_price", ""),
                trade_data.get("exit_price", ""),
                trade_data.get("exit_reason", ""),
                trade_data.get("pnl_points", ""),
                trade_data.get("pnl_rupees", ""),
                trade_data.get("lot_size", ""),
                trade_data.get("duration_updates", ""),
                trade_data.get("duration_seconds", "")
            ])

    def clear_today_trades(self, date_str: Optional[str] = None) -> int:
        """
        Removes trade records matching today's date from trades_audit.csv.
        """
        if not os.path.exists(self.trades_audit_file):
            return 0

        if not date_str:
            from datetime import datetime, timedelta, timezone
            ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            date_str = ist_now.strftime("%Y-%m-%d")

        try:
            with open(self.trades_audit_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                self._init_files()
                return 0

            header = rows[0]
            remaining_rows = []
            removed_count = 0

            for row in rows[1:]:
                entry_t = row[4] if len(row) > 4 else ""
                exit_t = row[5] if len(row) > 5 else ""
                if (entry_t and entry_t.startswith(date_str)) or (exit_t and exit_t.startswith(date_str)) or date_str in str(row):
                    removed_count += 1
                else:
                    remaining_rows.append(row)

            with open(self.trades_audit_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(remaining_rows)

            logger.info(f"Cleared {removed_count} trades from audit log for {date_str}.")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to clear trades from audit file: {e}")
            return 0

