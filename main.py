"""
main.py
Main Pipeline & Wiring Entrypoint for BSE Sensex Options Simulation System.
"""

from typing import Dict, Any, Optional
from config import SystemConfig, default_config
from strike_selector import SensexStrikeSelector, BankNiftyStrikeSelector
from indicators import IndicatorEngine
from signal_engine import SignalEngine
from trade_manager import TradeManager
from risk_manager import RiskManager
from portfolio_manager import PortfolioManager
from simulation_engine import SimulationEngine
from data_manager import DataManager
from data_feed import DataFeedAdapter, SimulatedLiveFeedAdapter
from logger import AuditLogger, logger

class SensexSimulationSystem:
    def __init__(self, config: Optional[SystemConfig] = None, feed_adapter: Optional[DataFeedAdapter] = None):
        self.config = config or default_config
        
        # Instantiate Core Engines
        self.strike_selector = SensexStrikeSelector(
            strike_distance=self.config.strike_distance_points,
            strike_interval=self.config.strike_interval
        )
        self.indicator_engine = IndicatorEngine(
            rsi_period=self.config.rsi_period,
            ema_period=self.config.ema_period,
            adx_period=self.config.adx_period
        )
        self.signal_engine = SignalEngine(
            rsi_call_threshold=self.config.rsi_call_threshold,
            rsi_put_threshold=self.config.rsi_put_threshold,
            adx_call_threshold=self.config.adx_call_threshold,
            adx_put_threshold=self.config.adx_put_threshold,
            confirmation_candles=self.config.confirmation_candles
        )
        self.trade_manager = TradeManager()
        self.risk_manager = RiskManager(
            stop_loss_points=self.config.stop_loss_points,
            target_points=self.config.target_points,
            trail_trigger_points=self.config.trail_trigger_points,
            trail_lock_points=self.config.trail_lock_points,
            enable_trailing_sl=self.config.enable_trailing_sl,
            min_holding_updates=self.config.min_holding_updates,
            min_holding_seconds=self.config.min_holding_seconds
        )
        self.portfolio_manager = PortfolioManager(lot_size=self.config.lot_size)
        
        self.simulation_engine = SimulationEngine(
            strike_selector=self.strike_selector,
            signal_engine=self.signal_engine,
            trade_manager=self.trade_manager,
            risk_manager=self.risk_manager,
            portfolio_manager=self.portfolio_manager,
            max_trades_per_day=self.config.max_trades_per_day,
            auto_schedule=self.config.auto_schedule
        )
        
        self.feed_adapter = feed_adapter or SimulatedLiveFeedAdapter()
        self.data_manager = DataManager(self.feed_adapter)
        self.audit_logger = AuditLogger(log_dir=self.config.log_dir)

        # MongoDB Atlas Persistence
        try:
            from db_manager import MongoDatabaseManager
            self.db_manager = MongoDatabaseManager(
                mongo_uri=self.config.mongo_uri,
                db_name=self.config.mongo_db_name,
                collection_name=self.config.mongo_collection_name
            )
            # Persist initial system configuration
            self.db_manager.save_configuration(self.config.to_dict())

            # Load latest closed trades from MongoDB
            saved_trades = self.db_manager.get_saved_trades(limit=100)
            if saved_trades:
                for st in saved_trades:
                    t_rec = {
                        "trade_id": st.get("trade_id", len(self.portfolio_manager.trades) + 1),
                        "side": st.get("side", "CALL"),
                        "strike": st.get("strike", 0),
                        "symbol": st.get("option_symbol", st.get("symbol", "")),
                        "entry_time": st.get("entry_time", ""),
                        "exit_time": st.get("exit_time", ""),
                        "entry_price": round(float(st.get("entry_price", 0.0)), 2),
                        "exit_price": round(float(st.get("exit_price", 0.0)), 2),
                        "exit_reason": st.get("exit_reason", ""),
                        "pnl_points": round(float(st.get("pnl_points", 0.0)), 2),
                        "pnl_rupees": round(float(st.get("pnl_rupees", 0.0)), 2),
                        "lot_size": self.config.lot_size,
                        "duration_updates": st.get("update_count", 0),
                        "duration_seconds": float(st.get("duration_seconds", 0.0))
                    }
                    self.portfolio_manager.trades.append(t_rec)
                self.portfolio_manager.total_pnl_points = round(sum(t["pnl_points"] for t in self.portfolio_manager.trades), 2)
                self.portfolio_manager.total_pnl_rupees = round(sum(t["pnl_rupees"] for t in self.portfolio_manager.trades), 2)
                logger.info(f"Loaded {len(saved_trades)} closed trade(s) from MongoDB into PortfolioManager.")
        except Exception as e:
            logger.warning(f"Could not initialize MongoDB persistence: {e}")
            self.db_manager = None

    def process_market_update(self) -> Dict[str, Any]:
        """
        Executes a single market update cycle:
        1. Refreshes data from feed (1m, 5m, 15m completed candles, Sensex quote)
        2. Checks warm-up buffer requirements
        3. Computes indicators (RSI 5m/15m, EMA20 5m, ADX 5m)
        4. Selects strikes (~200 pts OTM)
        5. Fetches locked mid-prices for active position or candidate strikes
        6. Processes tick in SimulationEngine (Signal -> Debounce -> Alternation -> Open/Update/Close)
        7. Logs full decision trail to CSV audit files
        8. Returns rich snapshot of system state
        """
        # Step 1: Data Refresh
        df_5min, df_15min, quote = self.data_manager.refresh_market_data()
        timestamp = quote["timestamp"]
        sensex_ltp = quote["ltp"]
        sensex_mid = quote["mid_price"]

        # Step 2: Calculate Indicators
        indicators = self.indicator_engine.calculate_all(df_5min, df_15min)

        # Warm-up check for signal processing
        has_warmup = (
            len(df_5min) >= self.config.min_5m_warmup_candles and
            len(df_15min) >= self.config.min_15m_warmup_candles
        )

        strikes = self.strike_selector.get_strikes(sensex_mid)

        if not has_warmup:
            return {
                "status": "WARMING_UP",
                "timestamp": timestamp,
                "sensex_ltp": sensex_ltp,
                "sensex_mid": sensex_mid,
                "banknifty_ltp": sensex_ltp,
                "banknifty_mid": sensex_mid,
                "indicators": indicators,
                "strikes": strikes,
                "5m_candles_count": len(df_5min),
                "15m_candles_count": len(df_15min),
                "message": f"Warming up indicators... 5m: {len(df_5min)}/{self.config.min_5m_warmup_candles}, 15m: {len(df_15min)}/{self.config.min_15m_warmup_candles}"
            }

        # Step 5: Option Quotes Lookup
        option_quotes = self.data_manager.get_option_quotes_for_strikes(
            call_strike=strikes["call_strike"],
            put_strike=strikes["put_strike"]
        )
        # If there is an active trade, also fetch its locked instrument's quote
        # and store it under its own key ONLY. Never overwrite "CALL"/"PUT" display keys
        # with a different strike's price (that would cause LTP flickering in the UI).
        if self.simulation_engine.active_trade is not None:
            locked_strike = self.simulation_engine.active_trade["strike"]
            locked_side = self.simulation_engine.active_trade["side"]
            opt_type = "CE" if locked_side == "CALL" else "PE"
            locked_quote = self.data_manager.get_locked_option_quote(locked_strike, opt_type)
            # Always store under the specific key so engine can price the open position
            option_quotes[f"{locked_strike}_{opt_type}"] = locked_quote
            # Only overwrite CALL/PUT if the active trade is on the SAME strike as currently selected
            selected_strike = strikes["call_strike"] if locked_side == "CALL" else strikes["put_strike"]
            if locked_strike == selected_strike:
                option_quotes[locked_side] = locked_quote

        option_quotes["call"] = option_quotes.get("CALL")
        option_quotes["put"] = option_quotes.get("PUT")

        # Step 6: Process Tick in Simulation Engine
        engine_result = self.simulation_engine.process_market_tick(
            sensex_ltp=sensex_mid,
            indicator_data=indicators,
            option_quotes=option_quotes,
            timestamp=timestamp
        )

        # Detailed signal conditions for UI / Audit
        condition_eval = self.signal_engine.evaluate_conditions(
            rsi_5m=indicators["rsi_5m"],
            rsi_15m=indicators["rsi_15m"],
            ema20_5m=indicators["ema20_5m"],
            adx_5m=indicators["adx_5m"],
            close_5m=indicators["close_5m"]
        )

        signal_state = {
            "signal": engine_result.get("signal_state", {}).get("signal", "NO_TRADE"),
            "raw_signal": condition_eval["raw_signal"],
            "conditions": condition_eval,
            "consecutive_call_count": self.signal_engine.consecutive_call_count,
            "consecutive_put_count": self.signal_engine.consecutive_put_count,
            "next_required": self.trade_manager.get_next_required_trade(),
            "skipped_signals_count": self.trade_manager.skipped_signals_count
        }

        # Step 7: Audit Logging
        self.audit_logger.log_market_tick(
            timestamp=timestamp,
            sensex_ltp=sensex_ltp,
            sensex_mid=sensex_mid,
            indicators=indicators,
            strikes=strikes,
            signal_state=signal_state,
            active_trade=self.simulation_engine.active_trade
        )

        if engine_result["event"] in ["TRADE_OPENED", "SIGNAL_REJECTED"]:
            self.audit_logger.log_signal_event(
                timestamp=timestamp,
                raw_signal=signal_state["raw_signal"],
                confirmed_signal=signal_state["signal"],
                confirmation_count=max(self.signal_engine.consecutive_call_count, self.signal_engine.consecutive_put_count),
                next_required=self.trade_manager.get_next_required_trade(),
                action_taken=engine_result["event"],
                rejection_reason=engine_result.get("reason", "")
            )

        if engine_result["event"] == "TRADE_CLOSED":
            self.audit_logger.log_closed_trade(engine_result["trade"])
            if self.db_manager:
                try:
                    self.db_manager.save_closed_trade(engine_result["trade"])
                    self.db_manager.save_portfolio_summary(self.portfolio_manager.get_summary())
                except Exception as e:
                    logger.warning(f"Error persisting trade to MongoDB: {e}")

        # Step 8: Return snapshot
        return {
            "status": "PROCESSED",
            "event": engine_result["event"],
            "timestamp": timestamp,
            "sensex_ltp": sensex_ltp,
            "sensex_mid": sensex_mid,
            "banknifty_ltp": sensex_ltp,
            "banknifty_mid": sensex_mid,
            "indicators": indicators,
            "conditions": condition_eval,
            "strikes": strikes,
            "option_quotes": option_quotes,
            "signal_state": signal_state,
            "trade_manager": self.trade_manager.get_state(),
            "active_trade": self.simulation_engine.active_trade,
            "portfolio_summary": self.portfolio_manager.get_summary(),
            "engine_result": engine_result,
            "market_open": quote.get("market_open", True),
            "market_status": quote.get("market_status", "OPEN")
        }

    def reset_session(self):
        """Resets session stats, alternation rules, and confirmation debounce."""
        self.signal_engine.reset()
        self.trade_manager.reset()
        self.portfolio_manager.reset()
        self.simulation_engine.active_trade = None
        self.simulation_engine.trade_counter = 0

    def clear_today_trades(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Clears today's closed trades from in-memory portfolio, CSV audit file, and MongoDB.
        """
        cleared_memory = self.portfolio_manager.clear_today_trades(date_str)
        cleared_csv = self.audit_logger.clear_today_trades(date_str)
        cleared_db = 0
        if self.db_manager:
            try:
                cleared_db = self.db_manager.clear_today_trades(date_str)
            except Exception as e:
                logger.warning(f"Error clearing DB trades: {e}")

        if self.portfolio_manager.trades:
            self.trade_manager.last_trade = self.portfolio_manager.trades[-1].get("side")
        else:
            self.trade_manager.reset()

        return {
            "cleared_memory": cleared_memory,
            "cleared_csv": cleared_csv,
            "cleared_db": cleared_db,
            "portfolio_summary": self.portfolio_manager.get_summary()
        }


# Backwards compatibility alias
BankNiftySimulationSystem = SensexSimulationSystem

if __name__ == "__main__":
    system = SensexSimulationSystem()
    print("Executing 5 sample BSE Sensex simulation ticks...")
    for i in range(5):
        system.feed_adapter.step()
        result = system.process_market_update()
        print(f"Tick #{i+1}: SENSEX LTP={result['sensex_ltp']}, Status={result['status']}, Event={result.get('event')}")
