"""
test_signal_engine.py
Unit tests for SignalEngine CALL/PUT conditions and confirmation debounce.
"""

import unittest
from signal_engine import SignalEngine

class TestSignalEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SignalEngine(
            rsi_call_threshold=60.0,
            rsi_put_threshold=40.0,
            adx_call_threshold=20.0,
            adx_put_threshold=20.0,
            confirmation_candles=2  # Test 2-candle confirmation requirement
        )

    def test_call_conditions_all_pass(self):
        # 5m RSI > 60, 15m RSI > 60, 5m close > EMA20, 5m ADX > 20
        res = self.engine.evaluate_conditions(
            rsi_5m=65.0,
            rsi_15m=62.0,
            ema20_5m=48400.0,
            adx_5m=25.0,
            close_5m=48500.0
        )
        self.assertTrue(res["call_all_met"])
        self.assertFalse(res["put_all_met"])
        self.assertEqual(res["raw_signal"], "CALL")

    def test_put_conditions_all_pass(self):
        # 5m RSI < 40, 15m RSI < 40, 5m close < EMA20, 5m ADX < 20
        res = self.engine.evaluate_conditions(
            rsi_5m=35.0,
            rsi_15m=38.0,
            ema20_5m=48600.0,
            adx_5m=18.0,
            close_5m=48500.0
        )
        self.assertTrue(res["put_all_met"])
        self.assertFalse(res["call_all_met"])
        self.assertEqual(res["raw_signal"], "PUT")

    def test_no_trade_when_conditions_mixed(self):
        # 5m RSI > 60 but 15m RSI < 60 -> NO_TRADE
        res = self.engine.evaluate_conditions(
            rsi_5m=65.0,
            rsi_15m=55.0, # Fails CALL
            ema20_5m=48400.0,
            adx_5m=25.0,
            close_5m=48500.0
        )
        self.assertFalse(res["call_all_met"])
        self.assertEqual(res["raw_signal"], "NO_TRADE")

    def test_confirmation_debounce_2_candles(self):
        """Fix #4: Signal requires 2 consecutive candles before confirmation."""
        # Candle 1: CALL conditions met
        sig1 = self.engine.get_signal(rsi_5m=65.0, rsi_15m=62.0, ema20_5m=48400.0, adx_5m=25.0, close_5m=48500.0)
        self.assertEqual(sig1["raw_signal"], "CALL")
        self.assertEqual(sig1["signal"], "NO_TRADE") # Not confirmed yet!
        self.assertEqual(sig1["consecutive_call_count"], 1)

        # Candle 2: CALL conditions still met -> confirmed!
        sig2 = self.engine.get_signal(rsi_5m=66.0, rsi_15m=63.0, ema20_5m=48420.0, adx_5m=26.0, close_5m=48520.0)
        self.assertEqual(sig2["raw_signal"], "CALL")
        self.assertEqual(sig2["signal"], "CALL") # Confirmed!
        self.assertEqual(sig2["consecutive_call_count"], 2)

        # Candle 3: Conditions drop to NO_TRADE -> resets counter
        sig3 = self.engine.get_signal(rsi_5m=50.0, rsi_15m=50.0, ema20_5m=48420.0, adx_5m=15.0, close_5m=48420.0)
        self.assertEqual(sig3["raw_signal"], "NO_TRADE")
        self.assertEqual(sig3["signal"], "NO_TRADE")
        self.assertEqual(sig3["consecutive_call_count"], 0)

if __name__ == "__main__":
    unittest.main()
