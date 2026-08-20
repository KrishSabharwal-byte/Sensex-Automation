"""
data_manager.py
Data Management Engine for BSE Sensex Options Simulation.
Handles non-repainting completed candle aggregation (5m, 15m), rolling history buffers,
and locked-instrument mid-price lookups across both Live and Replay feed modes.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from data_feed import DataFeedAdapter

class DataManager:
    def __init__(self, feed_adapter: DataFeedAdapter, min_5m_buffer: int = 15, min_15m_buffer: int = 10):
        self.feed = feed_adapter
        self.min_5m_buffer = min_5m_buffer
        self.min_15m_buffer = min_15m_buffer
        self.raw_buffer: pd.DataFrame = pd.DataFrame()
        self.completed_5min_buffer: pd.DataFrame = pd.DataFrame()
        self.completed_15min_buffer: pd.DataFrame = pd.DataFrame()

    def get_completed_5min_candles(self, df_input: pd.DataFrame) -> pd.DataFrame:
        """
        Builds completed 5-minute candles from either 1-minute bars or direct 5-minute exchange data.
        """
        if df_input is None or df_input.empty:
            return pd.DataFrame()

        df = df_input.copy()
        if 'timestamp' in df.columns:
            ts_series = pd.to_datetime(df['timestamp'])
            if getattr(ts_series.dtype, 'tz', None) is not None:
                ts_series = ts_series.dt.tz_localize(None)
            df['timestamp'] = ts_series
            df = df.set_index('timestamp')

        df = df.sort_index()

        # Check spacing using median difference to avoid night/weekend gap distortion
        if len(df) > 1:
            diffs = pd.Series(df.index).diff().dt.total_seconds().dropna()
            med_diff = diffs.median()
            # If already 5-minute bars (~300s), return cleaned DataFrame
            if 240 <= med_diff <= 360:
                return df.dropna().reset_index()

        # Otherwise resample 1-minute bars into 5-minute completed bars
        resampled = df.resample('5min', label='left', closed='left').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        return resampled.dropna().reset_index()

    def get_completed_15min_candles(self, df_input: pd.DataFrame) -> pd.DataFrame:
        """
        Builds completed 15-minute candles from 5-min or 1-min bars using session-aware grouping.
        """
        if df_input is None or df_input.empty:
            return pd.DataFrame()

        df_5m = self.get_completed_5min_candles(df_input)
        if df_5m.empty:
            return pd.DataFrame()

        df = df_5m.copy()
        ts_series = pd.to_datetime(df['timestamp'])
        if getattr(ts_series.dtype, 'tz', None) is not None:
            ts_series = ts_series.dt.tz_localize(None)
        df['dt'] = ts_series
        df['date'] = df['dt'].dt.date

        bars_15m = []
        for date, day_df in df.groupby('date', sort=True):
            day_df = day_df.sort_values('dt').reset_index(drop=True)
            for i in range(0, len(day_df), 3):
                chunk = day_df.iloc[i:i+3]
                if not chunk.empty:
                    bars_15m.append({
                        'timestamp': chunk['timestamp'].iloc[0],
                        'open': chunk['open'].iloc[0],
                        'high': chunk['high'].max(),
                        'low': chunk['low'].min(),
                        'close': chunk['close'].iloc[-1],
                        'volume': chunk['volume'].sum() if 'volume' in chunk else 0
                    })

        return pd.DataFrame(bars_15m)

    def refresh_market_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        """
        Fetches latest bars from feed adapter, builds completed 5m and 15m candles,
        and retrieves latest Sensex mid-price quote.
        """
        df_raw = self.feed.get_1min_candles()
        self.raw_buffer = df_raw

        df_5min = self.get_completed_5min_candles(df_raw)
        df_15min = self.get_completed_15min_candles(df_raw)

        self.completed_5min_buffer = df_5min
        self.completed_15min_buffer = df_15min

        if hasattr(self.feed, "get_sensex_quote"):
            quote = self.feed.get_sensex_quote()
        else:
            quote = self.feed.get_banknifty_quote()

        return df_5min, df_15min, quote

    def get_locked_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        """
        Given a strike and option type, fetches mid-price for exactly that locked instrument.
        """
        quote = self.feed.get_option_quote(strike=strike, option_type=option_type)
        return quote

    def get_option_quotes_for_strikes(self, call_strike: int, put_strike: int) -> Dict[str, Any]:
        call_quote = self.get_locked_option_quote(call_strike, "CE")
        put_quote = self.get_locked_option_quote(put_strike, "PE")
        
        return {
            f"{call_strike}_CE": call_quote,
            f"{put_strike}_PE": put_quote,
            "CALL": call_quote,
            "PUT": put_quote
        }
