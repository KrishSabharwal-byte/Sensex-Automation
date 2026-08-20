"""
simulation_engine.py
Core Orchestration Engine for BSE Sensex Options Simulation.
Orchestrates strike selection -> signal evaluation -> alternation checks -> trade lifecycle.
Includes locked instrument enforcement and unified portfolio P&L.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from strike_selector import SensexStrikeSelector, BankNiftyStrikeSelector
from signal_engine import SignalEngine
from trade_manager import TradeManager
from risk_manager import RiskManager
from portfolio_manager import PortfolioManager

logger = logging.getLogger(__name__)

class SimulationEngine:
    def __init__(
        self,
        strike_selector: Optional[SensexStrikeSelector] = None,
        signal_engine: Optional[SignalEngine] = None,
        trade_manager: Optional[TradeManager] = None,
        risk_manager: Optional[RiskManager] = None,
        portfolio_manager: Optional[PortfolioManager] = None,
        max_trades_per_day: int = 5,
        auto_schedule: bool = True
    ):
        self.strike_selector = strike_selector or SensexStrikeSelector()
        self.signal_engine = signal_engine or SignalEngine()
        self.trade_manager = trade_manager or TradeManager()
        self.risk_manager = risk_manager or RiskManager()
        self.portfolio_manager = portfolio_manager or PortfolioManager()
        self.max_trades_per_day = max_trades_per_day
        self.auto_schedule = auto_schedule
        
        self.active_trade: Optional[Dict[str, Any]] = None
        self.trade_counter: int = 0

    @property
    def total_pnl(self) -> float:
        """Single source of truth for P&L from PortfolioManager."""
        return self.portfolio_manager.total_pnl_points

    @property
    def total_pnl_rupees(self) -> float:
        return self.portfolio_manager.total_pnl_rupees

    def open_trade(
        self,
        side: str,
        strike: int,
        entry_price: float,
        timestamp: str = ""
    ) -> Dict[str, Any]:
        """
        Open a new long option position and lock its strike and parameters.
        Enforces single active trade constraint, strict CALL/PUT alternation,
        max trades per day cap, and auto market schedule constraints.
        """
        # 1. Prevent concurrent/overlapping trades
        if self.active_trade is not None:
            logger.warning(
                f"Cannot open {side} trade: Trade #{self.active_trade['trade_id']} ({self.active_trade['side']}) is currently active."
            )
            return {
                "event": "ALREADY_ACTIVE_TRADE",
                "status": "REJECTED",
                "message": f"Active {self.active_trade['side']} position already open. Close it before opening a new trade.",
                "trade": dict(self.active_trade)
            }

        # 2. Check Daily Max Trades limit
        current_daily_trades = len(self.portfolio_manager.trades)
        if self.max_trades_per_day > 0 and current_daily_trades >= self.max_trades_per_day:
            logger.warning(
                f"Max Trades Per Day Reached! Session trades: {current_daily_trades}/{self.max_trades_per_day}."
            )
            return {
                "event": "DAILY_TRADE_LIMIT_REACHED",
                "status": "REJECTED",
                "side": side,
                "reason": f"Daily trade limit reached ({current_daily_trades}/{self.max_trades_per_day} trades completed today)",
                "next_required": self.trade_manager.get_next_required_trade(),
                "skipped_count": self.trade_manager.skipped_signals_count
            }

        # 3. Check Auto 09:15-15:15 IST schedule
        if self.auto_schedule and timestamp:
            time_str = timestamp.split(" ")[1] if " " in timestamp else timestamp
            if time_str:
                if time_str < "09:15:00" or time_str > "15:15:00":
                    logger.warning(f"Trade rejected: {time_str} is outside auto schedule 09:15-15:15 IST.")
                    return {
                        "event": "OUTSIDE_SCHEDULE",
                        "status": "REJECTED",
                        "side": side,
                        "reason": f"Signal '{side}' outside 09:15-15:15 IST schedule ({time_str})",
                        "next_required": self.trade_manager.get_next_required_trade(),
                        "skipped_count": self.trade_manager.skipped_signals_count
                    }

        # 4. Enforce strict CALL / PUT alternation rule
        if not self.trade_manager.can_take_trade(side):
            next_req = self.trade_manager.get_next_required_trade()
            logger.warning(
                f"Trade Alternation Violation! Attempted to open {side} trade, but next required trade is '{next_req}'."
            )
            return {
                "event": "SIGNAL_REJECTED",
                "status": "REJECTED",
                "side": side,
                "reason": f"Signal '{side}' rejected: strictly alternating trades required, waiting for '{next_req}'",
                "next_required": next_req,
                "skipped_count": self.trade_manager.skipped_signals_count
            }

        self.trade_counter += 1
        levels = self.risk_manager.calculate_levels(entry_price)
        
        symbol = f"SENSEX_{strike}_{'CE' if side == 'CALL' else 'PE'}"
        
        self.active_trade = {
            "trade_id": self.trade_counter,
            "side": side,
            "strike": strike,
            "symbol": symbol,
            "entry_price": float(entry_price),
            "current_price": float(entry_price),
            "entry_time": timestamp,
            "last_update_time": timestamp,
            "stop_loss": levels["stop_loss_price"],
            "target": levels["target_price"],
            "trail_trigger": levels["trail_trigger_price"],
            "trail_lock": levels["trail_lock_price"],
            "trailing_active": False,
            "enable_trailing_sl": self.risk_manager.enable_trailing_sl,
            "update_count": 0,
            "duration_seconds": 0.0,
            "highest_price": float(entry_price),
            "lowest_price": float(entry_price),
            "unrealized_pnl_points": 0.0,
            "unrealized_pnl_rupees": 0.0
        }
        
        # Update trade manager alternation tracker
        self.trade_manager.record_trade(side)
        
        logger.info(
            f"OPENED TRADE #{self.trade_counter}: {side} {symbol} @ {entry_price:.2f} | "
            f"SL={levels['stop_loss_price']:.2f}, TP={levels['target_price']:.2f} | "
            f"TSL Trigger={levels['trail_trigger_price']:.2f} (Lock={levels['trail_lock_price']:.2f})"
        )
        
        return {
            "event": "TRADE_OPENED",
            "status": "SUCCESS",
            "trade": dict(self.active_trade),
            "message": f"Opened {side} on strike {strike} at {entry_price:.2f}"
        }

    def update_trade(
        self,
        current_price: float,
        strike: int,
        option_type: str,
        timestamp: str = "",
        elapsed_seconds_delta: float = 1.0
    ) -> Dict[str, Any]:
        """
        Updates an open position with new market price and checks exit conditions (TP/SL/TSL).
        Enforces instrument lock: rejects updates with mismatched strike or type.
        """
        if self.active_trade is None:
            return {"event": "NO_ACTIVE_TRADE", "status": "IGNORED"}

        # Instrument lock verification
        expected_type = "CE" if self.active_trade["side"] == "CALL" else "PE"
        if strike != self.active_trade["strike"] or option_type.upper() != expected_type:
            logger.error(
                f"Instrument Lock Violation! Active trade requires strike={self.active_trade['strike']} ({self.active_trade['side']}), "
                f"but received price update for strike={strike} ({option_type}). Update rejected."
            )
            return {
                "event": "INSTRUMENT_LOCK_ERROR",
                "status": "REJECTED",
                "message": "Update strike/type mismatch with locked active position."
            }

        t = self.active_trade
        t["update_count"] += 1
        t["duration_seconds"] += elapsed_seconds_delta
        t["last_update_time"] = timestamp

        price = max(0.0, float(current_price))
        if current_price < 0:
            logger.warning(f"Received negative option price {current_price}. Clamping to 0.0.")
            price = 0.0

        t["current_price"] = price
        t["highest_price"] = max(t["highest_price"], price)
        t["lowest_price"] = min(t["lowest_price"], price)

        # Calculate unrealized P&L
        pnl_pts = round(t["current_price"] - t["entry_price"], 2)
        pnl_inr = round(pnl_pts * self.portfolio_manager.lot_size, 2)
        t["unrealized_pnl_points"] = pnl_pts
        t["unrealized_pnl_rupees"] = pnl_inr

        # Check exit triggers & update Trailing SL via RiskManager
        exit_status, exit_reason, updated_sl, updated_tsl_active = self.risk_manager.evaluate_tick(
            entry_price=t["entry_price"],
            current_price=t["current_price"],
            current_sl=t.get("stop_loss"),
            trailing_active=t.get("trailing_active", False),
            elapsed_seconds=t["duration_seconds"],
            update_count=t["update_count"]
        )

        t["stop_loss"] = round(updated_sl, 2)
        t["trailing_active"] = updated_tsl_active

        if exit_status in ["EXIT_TARGET", "EXIT_STOPLOSS", "EXIT_TRAIL_STOPLOSS"]:
            return self.close_trade(
                exit_price=t["current_price"],
                exit_reason=exit_reason,
                timestamp=timestamp
            )

        return {
            "event": "TRADE_UPDATED",
            "trade": dict(t),
            "pnl_points": pnl_pts,
            "pnl_rupees": pnl_inr
        }

    def close_trade(
        self,
        exit_price: float,
        exit_reason: str,
        timestamp: str = ""
    ) -> Dict[str, Any]:
        """
        Closes active position, records to portfolio manager, and resets active trade slot.
        """
        if self.active_trade is None:
            return {"event": "NO_ACTIVE_TRADE", "status": "IGNORED"}

        t = self.active_trade
        final_price = max(0.0, float(exit_price))
        pnl_pts = round(final_price - t["entry_price"], 2)
        pnl_inr = round(pnl_pts * self.portfolio_manager.lot_size, 2)

        closed_trade_record = {
            "trade_id": t["trade_id"],
            "side": t["side"],
            "strike": t["strike"],
            "symbol": t["symbol"],
            "entry_time": t["entry_time"],
            "exit_time": timestamp or t["last_update_time"],
            "entry_price": t["entry_price"],
            "exit_price": final_price,
            "exit_reason": exit_reason,
            "pnl_points": pnl_pts,
            "pnl_rupees": pnl_inr,
            "highest_price": t["highest_price"],
            "lowest_price": t["lowest_price"],
            "duration_updates": t["update_count"],
            "duration_seconds": t["duration_seconds"],
            "lot_size": self.portfolio_manager.lot_size
        }

        # Unified single source of truth portfolio tracking
        self.portfolio_manager.record_closed_trade(closed_trade_record)

        logger.info(
            f"CLOSED TRADE #{t['trade_id']}: {t['side']} {t['symbol']} | "
            f"Exit={final_price:.2f} ({exit_reason}) | P&L={pnl_pts:+.2f} pts (₹{pnl_inr:+.2f})"
        )

        self.active_trade = None

        return {
            "event": "TRADE_CLOSED",
            "trade": closed_trade_record,
            "pnl_points": pnl_pts,
            "pnl_rupees": pnl_inr,
            "portfolio_summary": self.portfolio_manager.get_summary()
        }

    def process_market_tick(
        self,
        sensex_ltp: float = 0.0,
        indicator_data: Optional[Dict[str, Any]] = None,
        option_quotes: Optional[Dict[str, Any]] = None,
        timestamp: str = "",
        banknifty_ltp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Unified market update step.
        - If active trade: updates trade with locked strike mid-price.
        - If no trade: evaluates strikes, indicator signals, confirmation debounce, and alternation rules.
        """
        ltp = sensex_ltp or banknifty_ltp or 0.0
        indicator_data = indicator_data or {}
        option_quotes = option_quotes or {}

        # 1. Active Position Handling
        if self.active_trade is not None:
            locked_strike = self.active_trade["strike"]
            locked_side = self.active_trade["side"]
            
            # Lookup price for locked instrument
            key = f"{locked_strike}_{'CE' if locked_side == 'CALL' else 'PE'}"
            opt_data = option_quotes.get(key) or option_quotes.get(locked_side) or option_quotes.get(str(locked_strike))
            
            if opt_data is None:
                return {
                    "event": "WAITING_FOR_DATA",
                    "message": f"Option quote for locked instrument {key} not found in update."
                }
                
            opt_price = opt_data.get("mid_price", opt_data.get("ltp", opt_data if isinstance(opt_data, (int, float)) else 0.0))
            return self.update_trade(
                current_price=opt_price,
                strike=locked_strike,
                option_type="CE" if locked_side == "CALL" else "PE",
                timestamp=timestamp
            )

        # 2. No Active Trade: Evaluate Strike Selection & Signals
        strikes = self.strike_selector.get_strikes(ltp)
        
        signal_result = self.signal_engine.get_signal(
            rsi_5m=indicator_data.get("rsi_5m"),
            rsi_15m=indicator_data.get("rsi_15m"),
            ema20_5m=indicator_data.get("ema20_5m"),
            adx_5m=indicator_data.get("adx_5m"),
            close_5m=indicator_data.get("close_5m", ltp)
        )

        signal = signal_result["signal"] # Confirmed signal after debounce

        if signal in ["CALL", "PUT"]:
            # Check TradeManager alternation
            alt_result = self.trade_manager.process_signal(signal)
            
            if alt_result["status"] == "ACCEPTED":
                selected_strike = strikes["call_strike"] if signal == "CALL" else strikes["put_strike"]
                key = f"{selected_strike}_{'CE' if signal == 'CALL' else 'PE'}"
                
                opt_data = option_quotes.get(key) or option_quotes.get(signal)
                if opt_data is None:
                    return {
                        "event": "DATA_UNAVAILABLE",
                        "message": f"Confirmed {signal} signal on strike {selected_strike}, but quote unavailable."
                    }
                
                entry_price = opt_data.get("mid_price", opt_data.get("ltp", opt_data if isinstance(opt_data, (int, float)) else 0.0))
                if entry_price is None or float(entry_price) <= 0:
                    return {
                        "event": "DATA_PENDING",
                        "message": f"Confirmed {signal} signal on strike {selected_strike}, waiting for live exchange LTP quote."
                    }
                return self.open_trade(
                    side=signal,
                    strike=selected_strike,
                    entry_price=float(entry_price),
                    timestamp=timestamp
                )
            else:
                return {
                    "event": "SIGNAL_REJECTED",
                    "signal": signal,
                    "reason": alt_result["reason"],
                    "next_required": alt_result["next_required"],
                    "skipped_count": alt_result["skipped_count"]
                }

        return {
            "event": "NO_ACTION",
            "signal_state": signal_result,
            "strikes": strikes
        }
