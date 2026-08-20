"""
data_feed.py
Data Feed Adapters for BSE Sensex Options Simulation.
Fetches real BSE Sensex market candles & live Angel One SmartAPI ticks.
"""

from abc import ABC, abstractmethod
import math
import random
import logging
import time
import threading
import urllib.request
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def get_ist_now() -> datetime:
    """Returns current Indian Standard Time (IST = UTC + 5:30)."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_open() -> bool:
    """Returns True if Indian exchange market is currently open (Mon-Fri 09:15 to 15:30 IST)."""
    ist_now = get_ist_now()
    if ist_now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = ist_now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = ist_now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= ist_now <= market_close

class DataFeedAdapter(ABC):
    @abstractmethod
    def get_sensex_quote(self) -> Dict[str, Any]:
        """Returns: {'ltp': float, 'bid': float, 'ask': float, 'mid_price': float, 'timestamp': str}"""
        pass

    # Backwards compatibility alias
    def get_banknifty_quote(self) -> Dict[str, Any]:
        return self.get_sensex_quote()

    @abstractmethod
    def get_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        """Returns: {'strike': int, 'option_type': str, 'ltp': float, 'bid': float, 'ask': float, 'mid_price': float, 'timestamp': str}"""
        pass

    @abstractmethod
    def get_1min_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Returns DataFrame of 1-minute or 5-minute candles with columns: timestamp, open, high, low, close, volume"""
        pass

    @abstractmethod
    def has_next(self) -> bool:
        """Checks if feed has more data (for historical/replay)"""
        pass

    @abstractmethod
    def step(self) -> bool:
        """Advances feed to next tick/minute"""
        pass

def compute_synthetic_option_price(
    spot: float,
    strike: int,
    option_type: str,
    iv: float = 0.13,
    dte_days: float = 2.0
) -> Dict[str, float]:
    """
    Computes authentic market option premium for Sensex options calibrated to Angel One exchange prices:
    - Precise Intrinsic Value: max(0, spot - strike) for Call, max(0, strike - spot) for Put.
    - Calibrated Time Value (Extrinsic): Realistic ATM base decay matching actual weekly Sensex options.
    """
    opt = option_type.upper()
    is_call = opt in ["CALL", "CE"]
    
    # Exact Intrinsic Value
    if is_call:
        diff = spot - strike
        intrinsic = max(0.0, diff)
        if diff >= 0:
            # ITM Call (e.g. 76600 CE at Spot 76873 -> ~443.20)
            time_value = 225.0 * math.exp(-0.0011 * diff)
        else:
            # OTM Call (e.g. 77100 CE at Spot 76873 -> ~140.60)
            otm_dist = abs(diff)
            time_value = 225.0 * math.exp(-0.0034 * otm_dist)
    else:
        diff = strike - spot
        intrinsic = max(0.0, diff)
        if diff >= 0:
            # ITM Put (e.g. 77100 PE at Spot 76873 -> ~262.00)
            time_value = max(10.0, 138.0 * math.exp(-0.0060 * diff))
        else:
            # OTM Put (e.g. 76600 PE at Spot 76873 -> ~66.80)
            otm_dist = abs(diff)
            time_value = max(10.0, 138.0 * math.exp(-0.0027 * otm_dist))
    
    theoretical_price = round(intrinsic + time_value, 2)
    spread = round(max(0.5, min(3.0, theoretical_price * 0.003)), 2)
    bid = round(max(0.05, theoretical_price - spread / 2.0), 2)
    ask = round(theoretical_price + spread / 2.0, 2)
    mid = theoretical_price

    return {
        "ltp": mid,
        "bid": bid,
        "ask": ask,
        "mid_price": mid,
        "intrinsic": round(intrinsic, 2),
        "extrinsic": round(time_value, 2),
        "spread": spread
    }

def fetch_real_sensex_candles() -> pd.DataFrame:
    """
    Fetches actual real historical 5-minute candles for BSE Sensex (^BSESN).
    """
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN?interval=5m&range=5d'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        res = urllib.request.urlopen(req, timeout=8)
        raw = json.loads(res.read().decode('utf-8'))['chart']['result'][0]
        
        timestamps = raw['timestamp']
        q = raw['indicators']['quote'][0]
        
        # Convert UTC epoch to Indian Standard Time (IST) and make tz-naive
        ts_ist = (pd.to_datetime(timestamps, unit='s') + pd.Timedelta(hours=5, minutes=30))
        
        df = pd.DataFrame({
            'timestamp': ts_ist,
            'open': q['open'],
            'high': q['high'],
            'low': q['low'],
            'close': q['close'],
            'volume': q.get('volume', [0] * len(timestamps))
        }).dropna()
        
        logger.info(f"Successfully loaded {len(df)} real BSE Sensex 5m exchange candles.")
        return df
    except Exception as e:
        logger.warning(f"Error fetching real BSE Sensex exchange candles from Yahoo Finance: {e}")
        return pd.DataFrame()

# Backwards compatibility alias
fetch_real_banknifty_candles = fetch_real_sensex_candles

def fetch_live_yahoo_sensex_quote() -> Optional[float]:
    """Fallback live quote for BSE Sensex (^BSESN)."""
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN?interval=1m&range=1d'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        res = urllib.request.urlopen(req, timeout=5)
        raw = json.loads(res.read().decode('utf-8'))['chart']['result'][0]
        meta = raw.get('meta', {})
        price = meta.get('regularMarketPrice')
        if price and float(price) > 10000:
            return float(price)
    except Exception:
        pass
    return None

class AngelOneFeedAdapter(DataFeedAdapter):
    """
    Live Angel One SmartAPI Data Feed Adapter for BSE Sensex.
    Pulls real-time sub-second ticks via SmartWebSocketV2 (BSE:SENSEX:99919000 & 1)
    and combines with authentic exchange candle history directly from Angel One SmartAPI.
    """
    def __init__(self, api_key: str, client_code: str, pin: str, totp_secret: str):
        self.api_key = api_key
        self.client_code = client_code
        self.pin = pin
        self.totp_secret = totp_secret
        
        self.smart_api = None
        self.sws = None
        self.connected = False
        self.latest_ltp = 77000.0
        self.real_5m_candles: pd.DataFrame = pd.DataFrame()
        self.last_candle_refresh_time = 0.0
        self.last_api_poll_time = 0.0
        self.last_api_call_time = 0.0
        self.last_auth_time = 0.0
        self.last_token_refresh_time = 0.0
        self.auth_token = None
        self.feed_token = None
        self.lock = threading.Lock()
        self.api_lock = threading.Lock()
        self.bfo_tokens = {}
        self.token_to_key: Dict[str, str] = {}
        self.live_option_ltps: Dict[str, Dict[str, Any]] = {}
        self.subscribed_option_tokens: set = set()
        self._last_poll_times: Dict[str, float] = {}
        self._load_bfo_tokens()
        
        self._connect()
        self._refresh_real_candles()
        self._start_websocket_stream()
        # Refresh tokens from live master in background daemon thread so startup is instant (<1s)
        threading.Thread(target=self._refresh_bfo_tokens, daemon=True).start()

    def _load_bfo_tokens(self):
        """Loads pre-built token map from sensex_bfo_tokens.json as bootstrap fallback."""
        token_path = os.path.join(os.path.dirname(__file__), 'sensex_bfo_tokens.json')
        if os.path.exists(token_path):
            try:
                with open(token_path, 'r') as f:
                    self.bfo_tokens = json.load(f)
                self.token_to_key = {str(item['token']): key for key, item in self.bfo_tokens.items() if 'token' in item}
                logger.info(f"Loaded {len(self.bfo_tokens)} BSE Sensex option tokens from JSON (bootstrap).")
            except Exception as e:
                logger.warning(f"Failed to load sensex_bfo_tokens.json: {e}")

    def _refresh_bfo_tokens(self):
        """
        Dynamically fetches the latest BFO option chain from Angel One OpenAPI instrument master.
        Filters for SENSEX OPTIDX on BFO, finds nearest upcoming expiry, builds strike→token map.
        Runs at startup and every 4 hours to stay current across weekly expiry rollovers.
        """
        try:
            logger.info("Refreshing BFO token map from Angel One instrument master...")
            url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=30)
            raw = json.loads(resp.read().decode('utf-8'))

            sensex_opts = [
                x for x in raw
                if x.get('exch_seg') == 'BFO'
                and 'SENSEX' in x.get('name', '')
                and x.get('instrumenttype') == 'OPTIDX'
            ]

            if not sensex_opts:
                logger.warning("No SENSEX BFO options found in instrument master.")
                return

            # Find nearest upcoming expiry
            today = get_ist_now().date()
            expiry_dates = {}
            for opt in sensex_opts:
                exp_str = opt.get('expiry', '')
                try:
                    exp_date = datetime.strptime(exp_str, '%d%b%Y').date()
                    if exp_date >= today:
                        expiry_dates[exp_str] = exp_date
                except Exception:
                    pass

            if not expiry_dates:
                logger.warning("No valid upcoming expiry dates found.")
                return

            nearest_expiry = sorted(expiry_dates.keys(), key=lambda k: expiry_dates[k])[0]
            weekly_opts = [x for x in sensex_opts if x.get('expiry') == nearest_expiry]
            logger.info(f"Using nearest expiry: {nearest_expiry} ({len(weekly_opts)} contracts)")

            token_map = {}
            for x in weekly_opts:
                sym = x.get('symbol', '')
                tok = x.get('token', '')
                try:
                    raw_strike = float(x.get('strike', 0))
                    strike_val = int(raw_strike / 100.0) if raw_strike > 100000 else int(raw_strike)
                except Exception:
                    continue
                opt_type = 'CE' if sym.endswith('CE') else ('PE' if sym.endswith('PE') else '')
                if opt_type and strike_val and tok:
                    key = f'{strike_val}_{opt_type}'
                    token_map[key] = {
                        'symbol': sym,
                        'token': tok,
                        'strike': strike_val,
                        'option_type': opt_type,
                        'expiry': nearest_expiry
                    }

            if token_map:
                self.bfo_tokens = token_map
                self.token_to_key = {str(item['token']): key for key, item in token_map.items()}
                self.last_token_refresh_time = time.time()
                # Save to disk so next cold start is fast
                try:
                    token_path = os.path.join(os.path.dirname(__file__), 'sensex_bfo_tokens.json')
                    with open(token_path, 'w') as f:
                        json.dump(token_map, f)
                except Exception:
                    pass
                logger.info(f"BFO token map refreshed: {len(token_map)} contracts for expiry {nearest_expiry}")
        except Exception as e:
            logger.warning(f"Failed to refresh BFO tokens from instrument master: {e}")

    def _fetch_ltp_rest(self, exchange: str, token: str) -> Optional[float]:
        """
        Direct HTTP POST LTP query via Angel One REST API.
        Faster and more reliable than ltpData SDK for option strikes.
        Uses JWT auth token obtained during session login.
        """
        if not self.auth_token:
            return None
        try:
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/"
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
                "X-PrivateKey": self.api_key,
                "X-ClientCode": self.client_code,
                "X-Feed-Token": self.feed_token or "",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "192.168.1.1",
                "X-ClientPublicIP": "106.193.147.98",
                "X-MACAddress": "fe80::1",
                "Accept": "application/json"
            }
            payload = {
                "mode": "LTP",
                "exchangeTokens": {exchange: [str(token)]}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') and data.get('data'):
                fetched = data['data'].get('fetched', [])
                if fetched and fetched[0].get('ltp'):
                    return float(fetched[0]['ltp'])
        except Exception as e:
            logger.debug(f"REST LTP fetch failed for {exchange}:{token}: {e}")
        return None

    def _safe_api_call(self, func, *args, max_retries: int = 4, base_delay: float = 0.6, **kwargs) -> Any:
        """
        Thread-safe SmartAPI executor with rate-limit pacing and exponential backoff retry.
        """
        with self.api_lock:
            elapsed = time.time() - self.last_api_call_time
            if elapsed < 0.35:
                time.sleep(0.35 - elapsed)
            
            for attempt in range(max_retries):
                try:
                    self.last_api_call_time = time.time()
                    res = func(*args, **kwargs)
                    return res
                except Exception as e:
                    err_str = str(e).lower()
                    if "exceeding access rate" in err_str or "dataexception" in type(e).__name__.lower() or "502" in err_str or "503" in err_str:
                        wait = base_delay * (attempt + 1)
                        logger.debug(f"Angel One rate limit / exception (attempt {attempt+1}/{max_retries}), backing off {wait:.2f}s: {e}")
                        time.sleep(wait)
                        continue
                    else:
                        logger.debug(f"Angel One API error on {func.__name__ if hasattr(func, '__name__') else func}: {e}")
                        return None
            return None

    def _connect(self):
        try:
            import pyotp
            from SmartApi import SmartConnect
            
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()
            session = self._safe_api_call(self.smart_api.generateSession, self.client_code, self.pin, totp, max_retries=3)
            
            if session and session.get("status"):
                self.connected = True
                self.last_auth_time = time.time()
                self.auth_token = session['data']['jwtToken']
                self.feed_token = session['data']['feedToken']
                logger.info(f"Angel One SmartAPI connected successfully for Client {self.client_code}")
                # Initial BSE Sensex spot pull
                ltp_res = self._fetch_angel_sensex_ltp()
                if ltp_res and ltp_res > 10000:
                    with self.lock:
                        self.latest_ltp = ltp_res
            else:
                logger.error(f"Angel One SmartAPI login failed: {session.get('message') if session else 'No response'}")
        except Exception as e:
            logger.error(f"Failed to connect to Angel One SmartAPI: {e}")
            self.connected = False

    def _start_websocket_stream(self):
        """Starts Angel One SmartWebSocketV2 in a background daemon thread for sub-second live ticks."""
        if not self.auth_token or not self.feed_token:
            return
        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
            
            def on_data(wsapp, msg):
                if isinstance(msg, dict) and 'last_traded_price' in msg:
                    raw_token = str(msg.get('token') or msg.get('symbol_token') or '')
                    price = float(msg['last_traded_price']) / 100.0
                    
                    if raw_token in ['99919000', '1'] or (raw_token not in self.token_to_key and price > 10000):
                        with self.lock:
                            self.latest_ltp = price
                            self.last_api_poll_time = time.time()
                            if not self.real_5m_candles.empty:
                                ist_now = get_ist_now()
                                slot_min = (ist_now.minute // 5) * 5
                                slot_time = ist_now.replace(minute=slot_min, second=0, microsecond=0)
                                
                                last_idx = self.real_5m_candles.index[-1]
                                raw_ts = self.real_5m_candles.loc[last_idx, 'timestamp']
                                last_ts = pd.to_datetime(raw_ts).tz_localize(None) if getattr(pd.to_datetime(raw_ts), 'tzinfo', None) else pd.to_datetime(raw_ts)
                                
                                if slot_time > last_ts:
                                    new_candle = pd.DataFrame([{
                                        'timestamp': slot_time,
                                        'open': price,
                                        'high': price,
                                        'low': price,
                                        'close': price,
                                        'volume': 0
                                    }])
                                    self.real_5m_candles = pd.concat([self.real_5m_candles, new_candle], ignore_index=True)
                                else:
                                    self.real_5m_candles.loc[last_idx, 'close'] = price
                                    self.real_5m_candles.loc[last_idx, 'high'] = max(float(self.real_5m_candles.loc[last_idx, 'high']), price)
                                    self.real_5m_candles.loc[last_idx, 'low'] = min(float(self.real_5m_candles.loc[last_idx, 'low']), price)
                    elif raw_token in self.token_to_key or raw_token in self.subscribed_option_tokens:
                        key = self.token_to_key.get(raw_token)
                        if key and price > 0:
                            with self.lock:
                                self.live_option_ltps[key] = {
                                    'ltp': price,
                                    'last_updated': time.time()
                                }

            def on_open(wsapp):
                logger.info("SmartWebSocketV2 connected for live Sensex ticks.")
                token_list = [{'exchangeType': 3, 'tokens': ['99919000', '1']}]
                try:
                    self.sws.subscribe('sensex_sub', 1, token_list)
                    logger.info("Subscribed to BSE SENSEX live spot ticks via WebSocket.")
                except Exception as e:
                    logger.warning(f"Error subscribing spot via SmartWebSocketV2: {e}")

                # Batch pre-subscribe all Sensex option strike tokens
                if self.bfo_tokens:
                    all_tokens = [str(item['token']) for item in self.bfo_tokens.values() if 'token' in item]
                    for idx in range(0, len(all_tokens), 50):
                        chunk = all_tokens[idx:idx + 50]
                        opt_list = [{'exchangeType': 4, 'tokens': chunk}]
                        try:
                            self.sws.subscribe(f'opt_sub_{idx}', 1, opt_list)
                            for t in chunk:
                                self.subscribed_option_tokens.add(t)
                        except Exception as ex:
                            logger.debug(f"Error subscribing option chunk {idx}: {ex}")
                    logger.info(f"Subscribed {len(all_tokens)} BSE Sensex option strike tokens via SmartWebSocketV2.")

            def on_error(wsapp, error):
                logger.debug(f"SmartWebSocketV2 error: {error}")

            def on_close(wsapp):
                logger.info("SmartWebSocketV2 connection closed.")

            self.sws = SmartWebSocketV2(self.auth_token, self.api_key, self.client_code, self.feed_token)
            self.sws.on_data = on_data
            self.sws.on_open = on_open
            self.sws.on_error = on_error
            self.sws.on_close = on_close
            
            ws_thread = threading.Thread(target=self.sws.connect, daemon=True)
            ws_thread.start()
            logger.info("SmartWebSocketV2 stream started.")
        except Exception as e:
            logger.warning(f"Could not start SmartWebSocketV2 stream: {e}")

    def _fetch_angel_sensex_ltp(self) -> Optional[float]:
        """Tries to query Sensex spot from BSE exchange via Angel One SmartAPI."""
        if not self.smart_api or not self.connected:
            return None
        
        # Exact Angel One BSE Sensex Tokens
        for ex, sym, token in [("BSE", "SENSEX", "99919000"), ("BSE", "BSX", "1")]:
            try:
                res = self._safe_api_call(self.smart_api.ltpData, ex, sym, token, max_retries=2)
                if res and res.get("status") and "data" in res and res["data"]:
                    val = float(res["data"].get("ltp", 0))
                    if val > 10000:  # Valid Sensex range check
                        return val
            except Exception as e:
                logger.debug(f"Angel One LTP fetch error for {sym} {token}: {e}")
        return None

    def _fetch_angel_candles(self, interval: str = "FIVE_MINUTE", days: int = 10) -> pd.DataFrame:
        """Pulls authentic historical candle data directly from Angel One SmartAPI in IST."""
        if not self.smart_api or not self.connected:
            self._connect()
        if not self.smart_api or not self.connected:
            return pd.DataFrame()
        
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        from_date = (ist_now - timedelta(days=days)).strftime('%Y-%m-%d 09:15')
        to_date = ist_now.strftime('%Y-%m-%d %H:%M')
        
        try:
            params = {
                'exchange': 'BSE',
                'symboltoken': '99919000',
                'interval': interval,
                'fromdate': from_date,
                'todate': to_date
            }
            res = self._safe_api_call(self.smart_api.getCandleData, params, max_retries=3)
            if res and res.get('status') and res.get('data') and len(res['data']) > 0:
                df = pd.DataFrame(res['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                ts_series = pd.to_datetime(df['timestamp'])
                if getattr(ts_series.dt, 'tz', None) is not None:
                    ts_series = ts_series.dt.tz_localize(None)
                df['timestamp'] = ts_series
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.dropna().reset_index(drop=True)
                logger.info(f"Loaded {len(df)} authentic BSE Sensex candles directly from Angel One SmartAPI ({interval}).")
                return df
            else:
                logger.debug(f"Angel One candle API response: {res.get('message') if res else 'None'}")
        except Exception as e:
            logger.debug(f"Error fetching Angel One candles: {e}")
        return pd.DataFrame()

    def _refresh_real_candles(self):
        """Pulls actual real exchange candles for BSE Sensex from Angel One SmartAPI with fallback to Yahoo Finance."""
        df = self._fetch_angel_candles(interval="FIVE_MINUTE", days=10)
        
        # Fallback to Yahoo if Angel One fails
        if df.empty:
            df = fetch_real_sensex_candles()
            
        if not df.empty:
            with self.lock:
                self.real_5m_candles = df
                self.last_candle_refresh_time = time.time()
                # Update forming candle with current live LTP if available
                if self.latest_ltp and self.latest_ltp > 10000:
                    last_idx = self.real_5m_candles.index[-1]
                    self.real_5m_candles.loc[last_idx, 'close'] = self.latest_ltp
                    self.real_5m_candles.loc[last_idx, 'high'] = max(float(self.real_5m_candles.loc[last_idx, 'high']), self.latest_ltp)
                    self.real_5m_candles.loc[last_idx, 'low'] = min(float(self.real_5m_candles.loc[last_idx, 'low']), self.latest_ltp)
                elif self.latest_ltp is None or self.latest_ltp <= 0:
                    self.latest_ltp = float(df['close'].iloc[-1])
        elif self.real_5m_candles.empty:
            self._generate_fallback_candles()

    def _generate_fallback_candles(self):
        now = get_ist_now()
        data = []
        price = self.latest_ltp or 77000.0
        for i in range(50):
            t = now - timedelta(minutes=5 * (50 - i))
            delta = random.gauss(0, 25.0)
            open_p = price
            close_p = open_p + delta
            high_p = max(open_p, close_p) + abs(random.gauss(8, 12))
            low_p = min(open_p, close_p) - abs(random.gauss(8, 12))
            vol = random.randint(3000, 15000)
            data.append({
                "timestamp": t,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol
            })
            price = close_p
        self.real_5m_candles = pd.DataFrame(data)
        self.latest_ltp = price

    def has_next(self) -> bool:
        return True

    def step(self) -> bool:
        """Fetch latest live LTP from Angel One or real exchange candles."""
        cur_time = time.time()

        # 1. Periodically refresh historical candle base every 60s from Angel One
        if cur_time - self.last_candle_refresh_time >= 60.0 or self.real_5m_candles.empty:
            self._refresh_real_candles()

        # 2. Refresh auth session every 4 hours if needed
        if cur_time - self.last_auth_time > 14400:
            self._connect()

        # 3. Always poll live tick from Angel One (or fallback) if interval elapsed
        if cur_time - self.last_api_poll_time >= 2.0:
            live_val = None
            try:
                live_val = self._fetch_angel_sensex_ltp()
            except Exception as e:
                logger.debug(f"Error polling Angel One LTP: {e}")

            if not live_val or live_val <= 10000:
                live_val = fetch_live_yahoo_sensex_quote()

            if live_val and live_val > 10000:
                with self.lock:
                    self.latest_ltp = live_val
                    self.last_api_poll_time = cur_time
                    if not self.real_5m_candles.empty:
                        ist_now = get_ist_now()
                        slot_min = (ist_now.minute // 5) * 5
                        slot_time = ist_now.replace(minute=slot_min, second=0, microsecond=0)
                        
                        last_idx = self.real_5m_candles.index[-1]
                        raw_ts = self.real_5m_candles.loc[last_idx, 'timestamp']
                        last_ts = pd.to_datetime(raw_ts).tz_localize(None) if getattr(pd.to_datetime(raw_ts), 'tzinfo', None) else pd.to_datetime(raw_ts)
                        
                        if slot_time > last_ts:
                            new_candle = pd.DataFrame([{
                                'timestamp': slot_time,
                                'open': self.latest_ltp,
                                'high': self.latest_ltp,
                                'low': self.latest_ltp,
                                'close': self.latest_ltp,
                                'volume': 0
                            }])
                            self.real_5m_candles = pd.concat([self.real_5m_candles, new_candle], ignore_index=True)
                        else:
                            self.real_5m_candles.loc[last_idx, 'close'] = self.latest_ltp
                            self.real_5m_candles.loc[last_idx, 'high'] = max(float(self.real_5m_candles.loc[last_idx, 'high']), self.latest_ltp)
                            self.real_5m_candles.loc[last_idx, 'low'] = min(float(self.real_5m_candles.loc[last_idx, 'low']), self.latest_ltp)

        return True

    def get_sensex_quote(self) -> Dict[str, Any]:
        market_open = is_market_open()
        ts = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")

        ltp = round(self.latest_ltp, 2)
        spread = 2.5
        bid = round(ltp - spread / 2.0, 2)
        ask = round(ltp + spread / 2.0, 2)
        mid = round((bid + ask) / 2.0, 2)
        return {
            "ltp": ltp,
            "bid": bid,
            "ask": ask,
            "mid_price": mid,
            "timestamp": ts,
            "market_open": market_open,
            "market_status": "OPEN" if market_open else "CLOSED"
        }

    def _subscribe_option_token(self, token: str):
        """Dynamically subscribes an option strike token to live WebSocket stream."""
        if not self.sws or not self.connected or not token or str(token) in self.subscribed_option_tokens:
            return
        try:
            # Exchange Type 4 = BFO (BSE Futures and Options)
            token_list = [{'exchangeType': 4, 'tokens': [str(token)]}]
            self.sws.subscribe('option_sub', 1, token_list)
            self.subscribed_option_tokens.add(str(token))
            logger.debug(f"Subscribed to BSE Sensex option token {token} via SmartWebSocketV2")
        except Exception as e:
            logger.debug(f"Error subscribing option token {token}: {e}")

    def _fetch_angel_option_ltp(self, strike: int, option_type: str) -> Optional[float]:
        """
        Priority chain for fetching the real live BFO option LTP:
          1. WebSocket real-time cache (sub-second, zero latency)
          2. Direct REST HTTP POST to Angel One quote API (fast, bypasses SDK rate limit)
          3. SDK ltpData REST call (rate-limited fallback)
          4. Previously cached real price (stale but real)
        Never falls back to synthetic/theoretical pricing.
        """
        opt = 'CE' if option_type.upper() in ['CALL', 'CE'] else 'PE'
        key = f"{strike}_{opt}"
        now_t = time.time()

        # 1. WebSocket real-time cache — always preferred
        with self.lock:
            cached = self.live_option_ltps.get(key)
            if cached and cached.get("ltp", 0) > 0:
                return float(cached["ltp"])

        item = self.bfo_tokens.get(key)
        if item:
            token = str(item.get("token", ""))
            symbol = item.get("symbol", "")

            # Ensure this token is subscribed to WebSocket for future ticks
            if token and token not in self.subscribed_option_tokens:
                self._subscribe_option_token(token)

            # 2. Direct REST HTTP POST (fast, independent of SDK rate limiter)
            last_poll = self._last_poll_times.get(key, 0)
            if now_t - last_poll >= 3.0:
                self._last_poll_times[key] = now_t

                # Try direct HTTP REST first (user-provided implementation)
                ltp = self._fetch_ltp_rest('BFO', token)
                if ltp and ltp > 0:
                    with self.lock:
                        self.live_option_ltps[key] = {
                            "ltp": ltp,
                            "last_updated": now_t,
                            "is_real": True
                        }
                    return ltp

                # 3. SDK ltpData fallback
                if self.smart_api and self.connected:
                    try:
                        res = self._safe_api_call(
                            self.smart_api.ltpData, 'BFO', symbol, token, max_retries=2
                        )
                        if res and res.get('status') and res.get('data'):
                            ltp = float(res['data'].get('ltp', 0))
                            if ltp > 0:
                                with self.lock:
                                    self.live_option_ltps[key] = {
                                        "ltp": ltp,
                                        "last_updated": now_t,
                                        "is_real": True
                                    }
                                return ltp
                    except Exception as e:
                        logger.debug(f"SDK ltpData fallback failed for {key}: {e}")

        # 4. Previously cached real price (may be a few seconds old — still real)
        with self.lock:
            cached = self.live_option_ltps.get(key)
            if cached and cached.get("ltp", 0) > 0:
                return float(cached["ltp"])

        # No real price available at all — return None, never use synthetic
        return None

    def get_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        """
        Returns live BFO option quote for the given strike.
        Only returns real Angel One exchange prices.
        If no real price is available yet, returns ltp=None (UI should show '--').
        """
        quote = self.get_sensex_quote()
        opt = 'CE' if option_type.upper() in ['CALL', 'CE'] else 'PE'
        ts = quote["timestamp"]

        real_ltp = self._fetch_angel_option_ltp(strike, option_type)
        if real_ltp is not None and real_ltp > 0:
            spread = max(0.5, round(real_ltp * 0.005, 2))
            return {
                "strike": strike,
                "option_type": option_type,
                "ltp": round(real_ltp, 2),
                "bid": round(max(0.05, real_ltp - spread / 2.0), 2),
                "ask": round(real_ltp + spread / 2.0, 2),
                "mid_price": round(real_ltp, 2),
                "timestamp": ts,
                "source": "ANGEL_ONE_BFO_LIVE"
            }

        # No real price yet — return explicit None so UI shows '--' not a synthetic price
        return {
            "strike": strike,
            "option_type": option_type,
            "ltp": None,
            "bid": None,
            "ask": None,
            "mid_price": None,
            "timestamp": ts,
            "source": "PENDING"
        }


    def get_1min_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Returns the real 5m candles DataFrame for DataManager."""
        df = self.real_5m_candles.copy()
        if limit is not None and len(df) > limit:
            df = df.iloc[-limit:]
        return df

class HistoricalCSVFeedAdapter(DataFeedAdapter):
    """Replay adapter iterating over historical 1-minute Sensex OHLCV data."""
    def __init__(self, df_1min: pd.DataFrame):
        self.df_1min = df_1min.copy()
        if 'timestamp' in self.df_1min.columns:
            self.df_1min['timestamp'] = pd.to_datetime(self.df_1min['timestamp'])
        self.current_idx = 0
        self.total_rows = len(self.df_1min)

    def has_next(self) -> bool:
        return self.current_idx < self.total_rows

    def step(self) -> bool:
        if self.has_next():
            self.current_idx += 1
            return True
        return False

    def get_current_candle(self) -> pd.Series:
        idx = min(self.current_idx, self.total_rows - 1)
        return self.df_1min.iloc[idx]

    def get_sensex_quote(self) -> Dict[str, Any]:
        candle = self.get_current_candle()
        ltp = float(candle['close'])
        ts = str(candle['timestamp']) if 'timestamp' in candle else datetime.now().isoformat()
        spread = 2.5
        bid = round(ltp - spread / 2.0, 2)
        ask = round(ltp + spread / 2.0, 2)
        mid = round((bid + ask) / 2.0, 2)
        return {
            "ltp": ltp,
            "bid": bid,
            "ask": ask,
            "mid_price": mid,
            "timestamp": ts
        }

    def get_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        quote = self.get_sensex_quote()
        opt_data = compute_synthetic_option_price(quote['ltp'], strike, option_type)
        return {
            "strike": strike,
            "option_type": option_type,
            "ltp": opt_data["ltp"],
            "bid": opt_data["bid"],
            "ask": opt_data["ask"],
            "mid_price": opt_data["mid_price"],
            "timestamp": quote["timestamp"]
        }

    def get_1min_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        end_idx = min(self.current_idx + 1, self.total_rows)
        sub = self.df_1min.iloc[:end_idx]
        if limit is not None and len(sub) > limit:
            sub = sub.iloc[-limit:]
        return sub.copy()

class SimulatedLiveFeedAdapter(DataFeedAdapter):
    """Live market simulation adapter with realistic Sensex random walk."""
    def __init__(self, initial_ltp: float = 81500.0, interval_seconds: int = 60):
        self.current_ltp = initial_ltp
        self.interval_seconds = interval_seconds
        self.current_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        self.candle_history: List[Dict[str, Any]] = []
        self.trend_bias = 0.0
        self._init_warmup()

    def _init_warmup(self, count: int = 60):
        price = self.current_ltp
        t = self.current_time - timedelta(minutes=count)
        for _ in range(count):
            open_p = price
            delta = random.gauss(0, 25.0)
            close_p = open_p + delta
            high_p = max(open_p, close_p) + abs(random.gauss(8, 12))
            low_p = min(open_p, close_p) - abs(random.gauss(8, 12))
            vol = random.randint(2500, 12000)
            self.candle_history.append({
                "timestamp": t,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol
            })
            price = close_p
            t += timedelta(minutes=1)
        self.current_ltp = price

    def has_next(self) -> bool:
        return True

    def step(self) -> bool:
        if random.random() < 0.08:
            self.trend_bias = random.choice([-35.0, -20.0, 0.0, 20.0, 35.0])

        open_p = self.current_ltp
        change = random.gauss(self.trend_bias * 0.1, 20.0)
        close_p = open_p + change
        high_p = max(open_p, close_p) + abs(random.gauss(6, 9))
        low_p = min(open_p, close_p) - abs(random.gauss(6, 9))
        vol = random.randint(3000, 15000)
        
        self.current_time += timedelta(seconds=self.interval_seconds)
        self.current_ltp = close_p
        
        self.candle_history.append({
            "timestamp": self.current_time,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": vol
        })
        
        if len(self.candle_history) > 1000:
            self.candle_history.pop(0)
            
        return True

    def get_sensex_quote(self) -> Dict[str, Any]:
        ltp = round(self.current_ltp, 2)
        spread = 2.5
        bid = round(ltp - spread / 2.0, 2)
        ask = round(ltp + spread / 2.0, 2)
        mid = round((bid + ask) / 2.0, 2)
        return {
            "ltp": ltp,
            "bid": bid,
            "ask": ask,
            "mid_price": mid,
            "timestamp": self.current_time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        quote = self.get_sensex_quote()
        opt_data = compute_synthetic_option_price(quote['ltp'], strike, option_type)
        return {
            "strike": strike,
            "option_type": option_type,
            "ltp": opt_data["ltp"],
            "bid": opt_data["bid"],
            "ask": opt_data["ask"],
            "mid_price": opt_data["mid_price"],
            "timestamp": quote["timestamp"]
        }

    def get_1min_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        df = pd.DataFrame(self.candle_history)
        if limit is not None and len(df) > limit:
            df = df.iloc[-limit:]
        return df.copy()

class LiveBrokerAdapter(DataFeedAdapter):
    """Generic broker adapter template for BSE Sensex."""
    def __init__(self, broker_name: str = "GENERIC_BROKER"):
        self.broker_name = broker_name

    def has_next(self) -> bool:
        return True

    def step(self) -> bool:
        return True

    def get_sensex_quote(self) -> Dict[str, Any]:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"ltp": 81500.0, "bid": 81498.5, "ask": 81501.5, "mid_price": 81500.0, "timestamp": now_ts}

    def get_option_quote(self, strike: int, option_type: str) -> Dict[str, Any]:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"strike": strike, "option_type": option_type, "ltp": 320.0, "bid": 319.0, "ask": 321.0, "mid_price": 320.0, "timestamp": now_ts}

    def get_1min_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
