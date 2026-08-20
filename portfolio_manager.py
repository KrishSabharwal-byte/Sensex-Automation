"""
portfolio_manager.py
Portfolio Management and Performance Analytics Engine.
Single source of truth for P&L bookkeeping, trade history, win-rates, and risk metrics.
"""

from typing import List, Dict, Any, Optional
import math

class PortfolioManager:
    def __init__(self, lot_size: int = 15):
        self.lot_size = lot_size
        self.trades: List[Dict[str, Any]] = []
        self.total_pnl_points: float = 0.0
        self.total_pnl_rupees: float = 0.0
        self.peak_pnl_rupees: float = 0.0
        self.max_drawdown_rupees: float = 0.0
        self.max_drawdown_points: float = 0.0

    def record_closed_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a closed trade and update portfolio statistics.
        """
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        
        # For long option positions (both long CE and long PE), P&L = exit_price - entry_price
        pnl_points = exit_price - entry_price
        pnl_rupees = pnl_points * self.lot_size

        trade_record = {
            "trade_id": trade.get("trade_id", len(self.trades) + 1),
            "side": trade.get("side", "UNKNOWN"),
            "strike": trade.get("strike", 0),
            "symbol": trade.get("symbol", ""),
            "entry_time": trade.get("entry_time", ""),
            "exit_time": trade.get("exit_time", ""),
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "exit_reason": trade.get("exit_reason", "MANUAL"),
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees": round(pnl_rupees, 2),
            "lot_size": self.lot_size,
            "duration_updates": trade.get("update_count", 0),
            "duration_seconds": trade.get("duration_seconds", 0.0)
        }

        self.trades.append(trade_record)
        self.total_pnl_points = round(self.total_pnl_points + pnl_points, 2)
        self.total_pnl_rupees = round(self.total_pnl_rupees + pnl_rupees, 2)

        # Track Drawdown
        if self.total_pnl_rupees > self.peak_pnl_rupees:
            self.peak_pnl_rupees = self.total_pnl_rupees
        current_dd_rupees = self.peak_pnl_rupees - self.total_pnl_rupees
        if current_dd_rupees > self.max_drawdown_rupees:
            self.max_drawdown_rupees = round(current_dd_rupees, 2)

        return trade_record

    def get_summary(self) -> Dict[str, Any]:
        """
        Compute and return comprehensive performance metrics.
        """
        total_trades = len(self.trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "win_rate_pct": 0.0,
                "total_pnl_points": 0.0,
                "total_pnl_rupees": 0.0,
                "best_trade_rupees": 0.0,
                "worst_trade_rupees": 0.0,
                "best_trade_points": 0.0,
                "worst_trade_points": 0.0,
                "avg_trade_rupees": 0.0,
                "avg_trade_points": 0.0,
                "call_trades_count": 0,
                "put_trades_count": 0,
                "call_win_rate_pct": 0.0,
                "put_win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_rupees": 0.0,
                "lot_size": self.lot_size
            }

        winning = [t for t in self.trades if t["pnl_points"] > 0]
        losing = [t for t in self.trades if t["pnl_points"] < 0]
        breakeven = [t for t in self.trades if t["pnl_points"] == 0]

        win_count = len(winning)
        loss_count = len(losing)
        win_rate = (win_count / total_trades) * 100.0

        gross_profit = sum(t["pnl_rupees"] for t in winning)
        gross_loss = abs(sum(t["pnl_rupees"] for t in losing))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        best_trade = max(self.trades, key=lambda t: t["pnl_rupees"])
        worst_trade = min(self.trades, key=lambda t: t["pnl_rupees"])

        call_trades = [t for t in self.trades if t["side"] == "CALL"]
        put_trades = [t for t in self.trades if t["side"] == "PUT"]

        call_wins = len([t for t in call_trades if t["pnl_points"] > 0])
        put_wins = len([t for t in put_trades if t["pnl_points"] > 0])

        call_win_rate = (call_wins / len(call_trades) * 100.0) if call_trades else 0.0
        put_win_rate = (put_wins / len(put_trades) * 100.0) if put_trades else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "breakeven_trades": len(breakeven),
            "win_rate_pct": round(win_rate, 2),
            "total_pnl_points": round(self.total_pnl_points, 2),
            "total_pnl_rupees": round(self.total_pnl_rupees, 2),
            "best_trade_rupees": round(best_trade["pnl_rupees"], 2),
            "worst_trade_rupees": round(worst_trade["pnl_rupees"], 2),
            "best_trade_points": round(best_trade["pnl_points"], 2),
            "worst_trade_points": round(worst_trade["pnl_points"], 2),
            "avg_trade_rupees": round(self.total_pnl_rupees / total_trades, 2),
            "avg_trade_points": round(self.total_pnl_points / total_trades, 2),
            "call_trades_count": len(call_trades),
            "put_trades_count": len(put_trades),
            "call_win_rate_pct": round(call_win_rate, 2),
            "put_win_rate_pct": round(put_win_rate, 2),
            "profit_factor": profit_factor,
            "max_drawdown_rupees": round(self.max_drawdown_rupees, 2),
            "lot_size": self.lot_size
        }

    def get_trade_history(self) -> List[Dict[str, Any]]:
        return list(self.trades)

    def clear_today_trades(self, date_str: Optional[str] = None) -> int:
        """
        Clears today's trades from in-memory records and recalculates portfolio statistics.
        """
        if not self.trades:
            return 0

        if not date_str:
            from datetime import datetime, timedelta, timezone
            ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            date_str = ist_now.strftime("%Y-%m-%d")

        initial_count = len(self.trades)
        remaining = [
            t for t in self.trades
            if not ((t.get("exit_time") or "").startswith(date_str) or (t.get("entry_time") or "").startswith(date_str))
        ]
        
        self.trades = remaining
        if not self.trades:
            self.reset()
        else:
            self.total_pnl_points = round(sum(t.get("pnl_points", 0.0) for t in self.trades), 2)
            self.total_pnl_rupees = round(sum(t.get("pnl_rupees", 0.0) for t in self.trades), 2)
            self.peak_pnl_rupees = max(0.0, self.total_pnl_rupees)
            self.max_drawdown_rupees = 0.0
            self.max_drawdown_points = 0.0

        return initial_count - len(self.trades)

    def reset(self):
        self.trades = []
        self.total_pnl_points = 0.0
        self.total_pnl_rupees = 0.0
        self.peak_pnl_rupees = 0.0
        self.max_drawdown_rupees = 0.0
        self.max_drawdown_points = 0.0

