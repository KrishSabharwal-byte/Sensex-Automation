"""
test_indicators.py
Unit tests for IndicatorEngine (RSI, EMA20, ADX) against known reference calculations.
"""

import unittest
import pandas as pd
import numpy as np
from indicators import calculate_rsi, calculate_ema, calculate_adx, IndicatorEngine

class TestIndicators(unittest.TestCase):
    def test_ema_known_sequence(self):
        """Test EMA calculation against hand-verified recursive formula."""
        # Simple sequence of 20 constant values then jump
        prices = [100.0] * 20 + [110.0]
        s = pd.Series(prices)
        ema = calculate_ema(s, period=20)
        
        # Initial EMA is 100.0, next is 100 + (2/(21))*(110 - 100) = 100 + 0.95238 = 100.95238
        self.assertAlmostEqual(ema.iloc[19], 100.0, places=4)
        self.assertAlmostEqual(ema.iloc[20], 100.95238, places=4)

    def test_rsi_monotonically_rising(self):
        """Monotonically rising prices should produce RSI near 100."""
        prices = [100.0 + i * 2.0 for i in range(30)]
        s = pd.Series(prices)
        rsi = calculate_rsi(s, period=14)
        self.assertGreater(rsi.iloc[-1], 95.0)

    def test_rsi_monotonically_falling(self):
        """Monotonically falling prices should produce RSI near 0."""
        prices = [200.0 - i * 2.0 for i in range(30)]
        s = pd.Series(prices)
        rsi = calculate_rsi(s, period=14)
        self.assertLess(rsi.iloc[-1], 5.0)

    def test_adx_trending_fixture(self):
        """Test ADX calculation on strong trending fixture."""
        n = 50
        dates = pd.date_range("2026-08-18 09:15", periods=n, freq="5min")
        highs = [100.0 + i * 3.0 + 1.0 for i in range(n)]
        lows = [100.0 + i * 3.0 - 1.0 for i in range(n)]
        closes = [100.0 + i * 3.0 for i in range(n)]
        
        df = pd.DataFrame({
            "timestamp": dates,
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": 1000
        })
        
        adx = calculate_adx(df, period=14)
        # In a sustained strong trend, ADX rises well above 20
        self.assertGreater(adx.iloc[-1], 30.0)

    def test_indicator_engine_warmup(self):
        """Test IndicatorEngine returns None before warm-up threshold is met."""
        engine = IndicatorEngine(rsi_period=14, ema_period=20, adx_period=14)
        df_short = pd.DataFrame({
            "open": [100.0]*5, "high": [101.0]*5, "low": [99.0]*5, "close": [100.0]*5, "volume": [100]*5
        })
        res = engine.calculate_all(df_short, df_short)
        self.assertIsNone(res["rsi_5m"])
        self.assertIsNone(res["ema20_5m"])

if __name__ == "__main__":
    unittest.main()
