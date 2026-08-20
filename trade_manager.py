"""
trade_manager.py
Enforces the strict CALL / PUT alternation rule for BSE Sensex options trading.
"""

from typing import Optional, Dict, Any

class TradeManager:
    def __init__(self):
        self.last_trade: Optional[str] = None
        self.skipped_signals_count: int = 0
        self.skipped_call_count: int = 0
        self.skipped_put_count: int = 0
        self.total_accepted_trades: int = 0

    def get_next_required_trade(self) -> str:
        """
        Returns 'ANY' if no previous trade, otherwise opposite of last_trade ('CALL' or 'PUT').
        """
        if self.last_trade is None:
            return "ANY"
        elif self.last_trade.upper() == "CALL":
            return "PUT"
        elif self.last_trade.upper() == "PUT":
            return "CALL"
        return "ANY"

    def can_take_trade(self, signal: str) -> bool:
        """
        Checks if incoming signal obeys the alternation rule.
        """
        if not signal or signal.upper() not in ["CALL", "PUT"]:
            return False

        sig = signal.upper()
        if self.last_trade is None:
            return True
        return sig != self.last_trade.upper()

    def process_signal(self, signal: str) -> Dict[str, Any]:
        """
        Evaluates incoming confirmed signal against alternation rule.
        If allowed, returns status 'ACCEPTED'.
        If disallowed (same side), increments skipped counters and returns 'REJECTED'.
        """
        if not signal or signal.upper() not in ["CALL", "PUT"]:
            return {
                "status": "NO_ACTION",
                "reason": "No actionable signal",
                "next_required": self.get_next_required_trade()
            }

        sig = signal.upper()
        if self.can_take_trade(sig):
            return {
                "status": "ACCEPTED",
                "side": sig,
                "reason": "Valid alternation" if self.last_trade else "First trade of session",
                "next_required": self.get_next_required_trade()
            }
        else:
            self.skipped_signals_count += 1
            if sig == "CALL":
                self.skipped_call_count += 1
            else:
                self.skipped_put_count += 1

            return {
                "status": "REJECTED",
                "side": sig,
                "reason": f"Signal '{sig}' rejected: waiting for '{self.get_next_required_trade()}'",
                "next_required": self.get_next_required_trade(),
                "skipped_count": self.skipped_signals_count
            }

    def record_trade(self, side: str):
        """
        Updates last_trade state when a trade is officially opened.
        """
        if side and side.upper() in ["CALL", "PUT"]:
            self.last_trade = side.upper()
            self.total_accepted_trades += 1

    def reset(self):
        """
        Resets session state (e.g. at market opening).
        """
        self.last_trade = None
        self.skipped_signals_count = 0
        self.skipped_call_count = 0
        self.skipped_put_count = 0
        self.total_accepted_trades = 0

    def get_state(self) -> Dict[str, Any]:
        return {
            "last_trade": self.last_trade,
            "next_required": self.get_next_required_trade(),
            "skipped_signals_count": self.skipped_signals_count,
            "skipped_call_count": self.skipped_call_count,
            "skipped_put_count": self.skipped_put_count,
            "total_accepted_trades": self.total_accepted_trades
        }
