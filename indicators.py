"""
indicators.py
Technical indicators calculation module: RSI, EMA(20), and ADX.
Supports standard pandas DataFrame / Series input and returns exact indicators.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI) using Wilder's Smoothing.
    """
    if len(series) < period + 1:
        return pd.Series(index=series.index, dtype=float)
    
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Wilder's exponential smoothing (alpha = 1 / period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # Edge cases: 0 gain -> RSI = 0, 0 loss -> RSI = 100
    rsi = rsi.fillna(50.0)
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    
    return rsi

def calculate_ema(series: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    """
    if len(series) < period:
        return pd.Series(index=series.index, dtype=float)
    return series.ewm(span=period, adjust=False).mean()

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX) using Wilder's Smoothing.
    df must contain columns: 'high', 'low', 'close' (case-insensitive).
    """
    df_cols = {c.lower(): c for c in df.columns}
    required = ['high', 'low', 'close']
    for r in required:
        if r not in df_cols:
            raise ValueError(f"DataFrame missing required column: '{r}'")
            
    high = df[df_cols['high']].astype(float)
    low = df[df_cols['low']].astype(float)
    close = df[df_cols['close']].astype(float)
    
    if len(df) < period * 2:
        return pd.Series(index=df.index, dtype=float)
        
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    
    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high - prev_high
    down_move = prev_low - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)
    
    # Wilder's Smoothing
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    smooth_plus_dm = plus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    smooth_minus_dm = minus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    plus_di = 100.0 * (smooth_plus_dm / atr.replace(0, np.nan))
    minus_di = 100.0 * (smooth_minus_dm / atr.replace(0, np.nan))
    
    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    
    dx = 100.0 * (di_diff / di_sum.replace(0, np.nan))
    dx = dx.fillna(0.0)
    
    adx = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    return adx.fillna(0.0)

class IndicatorEngine:
    """
    Computes and holds indicators for 5m and 15m completed candles.
    """
    def __init__(self, rsi_period: int = 14, ema_period: int = 20, adx_period: int = 14):
        self.rsi_period = rsi_period
        self.ema_period = ema_period
        self.adx_period = adx_period

    def calculate_all(self, df_5min: pd.DataFrame, df_15min: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute latest 5m and 15m indicators from completed OHLCV candle dataframes.
        """
        if df_5min is None or len(df_5min) < self.ema_period:
            return {
                "rsi_5m": None,
                "rsi_15m": None,
                "ema20_5m": None,
                "adx_5m": None,
                "close_5m": None
            }

        close_5m_col = next((c for c in df_5min.columns if c.lower() == 'close'), 'close')
        close_15m_col = next((c for c in df_15min.columns if c.lower() == 'close'), 'close') if df_15min is not None and not df_15min.empty else 'close'

        rsi_5m_series = calculate_rsi(df_5min[close_5m_col], period=self.rsi_period)
        ema20_5m_series = calculate_ema(df_5min[close_5m_col], period=self.ema_period)
        adx_5m_series = calculate_adx(df_5min, period=self.adx_period)

        rsi_15m_series = None
        if df_15min is not None and len(df_15min) >= self.rsi_period:
            rsi_15m_series = calculate_rsi(df_15min[close_15m_col], period=self.rsi_period)

        latest_5m_close = float(df_5min[close_5m_col].iloc[-1])
        latest_rsi_5m = float(rsi_5m_series.iloc[-1]) if not pd.isna(rsi_5m_series.iloc[-1]) else None
        latest_ema20_5m = float(ema20_5m_series.iloc[-1]) if not pd.isna(ema20_5m_series.iloc[-1]) else None
        latest_adx_5m = float(adx_5m_series.iloc[-1]) if not pd.isna(adx_5m_series.iloc[-1]) else None
        latest_rsi_15m = float(rsi_15m_series.iloc[-1]) if (rsi_15m_series is not None and not pd.isna(rsi_15m_series.iloc[-1])) else None

        return {
            "rsi_5m": latest_rsi_5m,
            "rsi_15m": latest_rsi_15m,
            "ema20_5m": latest_ema20_5m,
            "adx_5m": latest_adx_5m,
            "close_5m": latest_5m_close
        }
