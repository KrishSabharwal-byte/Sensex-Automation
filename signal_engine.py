"""
signal_engine.py
Signal Generation Engine for BSE Sensex Options.
Includes Debounce logic on completed candles to prevent whipsaws.
"""

from typing import Dict, Any, Optional

class SignalEngine:
    def __init__(
        self,
        rsi_call_threshold: float = 60.0,
        rsi_put_threshold: float = 40.0,
        adx_call_threshold: float = 20.0,
        adx_put_threshold: float = 20.0,
        confirmation_candles: int = 1
    ):
        self.rsi_call_threshold = rsi_call_threshold
        self.rsi_put_threshold = rsi_put_threshold
        self.adx_call_threshold = adx_call_threshold
        self.adx_put_threshold = adx_put_threshold
        self.confirmation_candles = confirmation_candles
        
        # Debounce state counters (Consecutive completed candles)
        self.consecutive_call_count = 0
        self.consecutive_put_count = 0

    def evaluate_conditions(
        self,
        rsi_5m: Optional[float],
        rsi_15m: Optional[float],
        ema20_5m: Optional[float],
        adx_5m: Optional[float],
        close_5m: Optional[float]
    ) -> Dict[str, Any]:
        """
        Evaluates raw indicators against CALL and PUT condition criteria.
        """
        if any(v is None for v in [rsi_5m, rsi_15m, ema20_5m, adx_5m, close_5m]):
            return {
                "call_all_met": False,
                "put_all_met": False,
                "call_conditions_met": False,
                "put_conditions_met": False,
                "raw_signal": "NO_TRADE",
                "details": {
                    "rsi_5m_call": False, "rsi_15m_call": False, "ema_call": False, "adx_call": False,
                    "rsi_5m_put": False, "rsi_15m_put": False, "ema_put": False, "adx_put": False
                }
            }

        # CALL Conditions:
        # 1. 5m RSI > 60
        # 2. 15m RSI > 60
        # 3. 5m Close > 5m EMA(20)
        # 4. 5m ADX > 20
        rsi_5m_call = (rsi_5m > self.rsi_call_threshold)
        rsi_15m_call = (rsi_15m > self.rsi_call_threshold)
        ema_call = (close_5m > ema20_5m)
        adx_call = (adx_5m > self.adx_call_threshold)
        call_all = bool(rsi_5m_call and rsi_15m_call and ema_call and adx_call)

        # PUT Conditions:
        # 1. 5m RSI < 40
        # 2. 15m RSI < 40
        # 3. 5m Close < 5m EMA(20)
        # 4. 5m ADX < 20
        rsi_5m_put = (rsi_5m < self.rsi_put_threshold)
        rsi_15m_put = (rsi_15m < self.rsi_put_threshold)
        ema_put = (close_5m < ema20_5m)
        adx_put = (adx_5m < self.adx_put_threshold)
        put_all = bool(rsi_5m_put and rsi_15m_put and ema_put and adx_put)

        raw_signal = "NO_TRADE"
        if call_all and not put_all:
            raw_signal = "CALL"
        elif put_all and not call_all:
            raw_signal = "PUT"

        return {
            "call_all_met": call_all,
            "put_all_met": put_all,
            "call_conditions_met": call_all,
            "put_conditions_met": put_all,
            "raw_signal": raw_signal,
            "details": {
                "rsi_5m_call": rsi_5m_call,
                "rsi_15m_call": rsi_15m_call,
                "ema_call": ema_call,
                "adx_call": adx_call,
                "rsi_5m_put": rsi_5m_put,
                "rsi_15m_put": rsi_15m_put,
                "ema_put": ema_put,
                "adx_put": adx_put
            }
        }

    def get_signal(
        self,
        rsi_5m: Optional[float],
        rsi_15m: Optional[float],
        ema20_5m: Optional[float],
        adx_5m: Optional[float],
        close_5m: Optional[float]
    ) -> Dict[str, Any]:
        """
        Calculates signal and applies multi-candle confirmation debounce.
        """
        eval_result = self.evaluate_conditions(rsi_5m, rsi_15m, ema20_5m, adx_5m, close_5m)
        raw_signal = eval_result["raw_signal"]

        # Debounce tracking
        if raw_signal == "CALL":
            self.consecutive_call_count += 1
            self.consecutive_put_count = 0
        elif raw_signal == "PUT":
            self.consecutive_put_count += 1
            self.consecutive_call_count = 0
        else:
            self.consecutive_call_count = 0
            self.consecutive_put_count = 0

        # Require N consecutive completed candles
        confirmed_signal = "NO_TRADE"
        if self.consecutive_call_count >= self.confirmation_candles:
            confirmed_signal = "CALL"
        elif self.consecutive_put_count >= self.confirmation_candles:
            confirmed_signal = "PUT"

        return {
            "signal": confirmed_signal,
            "raw_signal": raw_signal,
            "consecutive_call_count": self.consecutive_call_count,
            "consecutive_put_count": self.consecutive_put_count,
            "confirmation_required": self.confirmation_candles,
            "is_confirmed": (confirmed_signal != "NO_TRADE"),
            "condition_details": eval_result["details"]
        }

    def reset(self):
        """Resets debounce counters."""
        self.consecutive_call_count = 0
        self.consecutive_put_count = 0
