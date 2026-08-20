"""
config.py
Central Configuration for BSE Sensex Options Simulation System
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SystemConfig:
    # Angel One SmartAPI Credentials
    angelone_api_key: str = "WeUosnKy"
    angelone_client_code: str = "AACK825219"
    angelone_pin: str = "8004"
    angelone_totp_secret: str = "5XHZ5JMIJLUWJDM4QUXWYAO46I"
    feed_mode: str = "angelone"            # 'angelone', 'simulated', 'replay'

    # Index & Strike Selection Settings (BSE Sensex)
    symbol: str = "SENSEX"
    strike_distance_points: int = 200      # ~200 points OTM strikes
    strike_interval: int = 100             # BSE Sensex strikes are multiples of 100
    lot_size: int = 20                     # BSE Sensex standard lot size is 20
    
    # Indicator Parameters
    rsi_period: int = 14
    ema_period: int = 20
    adx_period: int = 14
    
    # Signal Thresholds
    rsi_call_threshold: float = 60.0       # 5m RSI > 60 AND 15m RSI > 60 for CALL
    rsi_put_threshold: float = 40.0        # 5m RSI < 40 AND 15m RSI < 40 for PUT
    adx_call_threshold: float = 20.0       # 5m ADX > 20 for CALL
    adx_put_threshold: float = 20.0        # 5m ADX < 20 for PUT
    
    # Signal Confirmation (Debounce on completed candles)
    confirmation_candles: int = 1          # Consecutive completed candles required to confirm signal
    
    # Risk Management & Trailing SL Parameters
    stop_loss_points: float = 50.0         # Default SL in premium points
    target_points: float = 100.0           # Default TP in premium points
    trail_trigger_points: float = 25.0     # Points in profit to activate trailing SL
    trail_lock_points: float = 15.0        # Points locked upon trailing activation
    enable_trailing_sl: bool = True        # Enable / disable trailing stop loss
    max_trades_per_day: int = 5            # Maximum accepted trades per trading session
    auto_schedule: bool = True             # Enforce 09:15-15:15 IST execution window
    min_holding_updates: int = 3           # Minimum updates to suppress SL noise
    min_holding_seconds: float = 30.0      # Minimum seconds before SL triggers can execute
    
    # Data & Warm-up Lookback
    min_5m_warmup_candles: int = 15        # Minimum 5m candles required for indicators
    min_15m_warmup_candles: int = 10       # Minimum 15m candles required for indicators
    
    # Market Hours (IST)
    market_open_time: str = "09:15:00"
    market_close_time: str = "15:30:00"
    auto_squareoff_time: str = "15:15:00"
    
    # Audit & Storage Paths
    log_dir: str = "logs"
    audit_trades_file: str = "logs/trades_audit.csv"
    audit_market_file: str = "logs/market_ticks_audit.csv"
    
    # MongoDB Atlas Connection
    mongo_uri: str = "mongodb+srv://crestviewcorporate_db_user:Crestviewcorporate@cluster0.zfk4ahy.mongodb.net/?appName=Cluster0"
    mongo_db_name: str = "new_logic"
    mongo_collection_name: str = "Sensex"

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

default_config = SystemConfig()
