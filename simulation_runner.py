"""
simulation_runner.py
Simulation Runner & Scheduler for BSE Sensex Options.
Handles market session lifecycle (9:15 - 15:30 IST), auto square-off (15:15 IST),
historical replay, and continuous live polling.
"""

import time
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from config import SystemConfig, default_config
from main import SensexSimulationSystem, BankNiftySimulationSystem
from data_feed import HistoricalCSVFeedAdapter, SimulatedLiveFeedAdapter
from logger import logger

class SimulationRunner:
    def __init__(self, system: Optional[SensexSimulationSystem] = None, speed_delay: float = 0.1):
        self.system = system or SensexSimulationSystem()
        self.speed_delay = speed_delay
        self.is_running = False

    def is_market_hours(self, current_time_str: str) -> bool:
        """
        Checks if current timestamp is within trading hours (09:15 to 15:30 IST).
        """
        try:
            time_part = current_time_str.split(" ")[-1] if " " in current_time_str else current_time_str
            t = datetime.strptime(time_part, "%H:%M:%S").time()
            open_t = datetime.strptime(self.system.config.market_open_time, "%H:%M:%S").time()
            close_t = datetime.strptime(self.system.config.market_close_time, "%H:%M:%S").time()
            return open_t <= t <= close_t
        except Exception:
            return True

    def is_squareoff_time(self, current_time_str: str) -> bool:
        """
        Checks if timestamp has reached auto square-off time (15:15 IST).
        """
        try:
            time_part = current_time_str.split(" ")[-1] if " " in current_time_str else current_time_str
            t = datetime.strptime(time_part, "%H:%M:%S").time()
            sq_t = datetime.strptime(self.system.config.auto_squareoff_time, "%H:%M:%S").time()
            return t >= sq_t
        except Exception:
            return False

    def run_replay(self, max_ticks: Optional[int] = None):
        """
        Run simulation across historical data replay feed.
        """
        logger.info("Starting BSE Sensex Historical Replay Simulation...")
        self.is_running = True
        tick_count = 0

        while self.is_running and self.system.feed_adapter.has_next():
            has_next = self.system.feed_adapter.step()
            if not has_next:
                break

            tick_count += 1
            result = self.system.process_market_update()
            
            # Check market session auto-squareoff
            ts = result.get("timestamp", "")
            if self.is_squareoff_time(ts) and self.system.simulation_engine.active_trade is not None:
                logger.info(f"Auto square-off triggered at {ts} for active position.")
                active = self.system.simulation_engine.active_trade
                self.system.simulation_engine.close_trade(
                    exit_price=active["current_price"],
                    exit_reason="AUTO_SQUAREOFF_EOD",
                    timestamp=ts
                )

            if max_ticks and tick_count >= max_ticks:
                break

            if self.speed_delay > 0:
                time.sleep(self.speed_delay)

        self.is_running = False
        summary = self.system.portfolio_manager.get_summary()
        logger.info(f"Replay Completed ({tick_count} ticks). Portfolio Summary: {summary}")
        return summary

    def run_live(self):
        """
        Run continuous live simulation polling feed at speed_delay interval.
        """
        logger.info("Starting Continuous BSE Sensex Live Simulation Loop...")
        self.is_running = True
        
        try:
            while self.is_running:
                self.system.feed_adapter.step()
                result = self.system.process_market_update()
                
                ts = result.get("timestamp", "")
                if self.is_squareoff_time(ts) and self.system.simulation_engine.active_trade is not None:
                    active = self.system.simulation_engine.active_trade
                    self.system.simulation_engine.close_trade(
                        exit_price=active["current_price"],
                        exit_reason="AUTO_SQUAREOFF_EOD",
                        timestamp=ts
                    )
                    
                time.sleep(self.speed_delay)
        except KeyboardInterrupt:
            logger.info("Live Simulation stopped by user.")
        finally:
            self.is_running = False

def create_sample_dataset(num_bars: int = 500) -> pd.DataFrame:
    """Generates synthetic 1-minute historical Sensex data (~81,500 base) for testing."""
    import random
    
    start_time = datetime(2026, 8, 18, 9, 15, 0)
    data = []
    price = 81500.0

    for i in range(num_bars):
        open_p = price
        if i % 60 < 25:
            change = random.gauss(15.0, 25.0) # Up-trend
        elif i % 60 < 45:
            change = random.gauss(-15.0, 25.0) # Down-trend
        else:
            change = random.gauss(0.0, 20.0) # Choppy
            
        close_p = open_p + change
        high_p = max(open_p, close_p) + abs(random.gauss(8.0, 12.0))
        low_p = min(open_p, close_p) - abs(random.gauss(8.0, 12.0))
        vol = random.randint(3000, 20000)

        data.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": vol
        })
        price = close_p

    return pd.DataFrame(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BSE Sensex Options Simulation Runner")
    parser.add_argument("--mode", choices=["replay", "live"], default="replay", help="Simulation mode")
    parser.add_argument("--speed", type=float, default=0.01, help="Delay between ticks in seconds")
    parser.add_argument("--ticks", type=int, default=300, help="Number of ticks to run in replay mode")
    args = parser.parse_args()

    if args.mode == "replay":
        sample_df = create_sample_dataset(num_bars=args.ticks + 100)
        feed = HistoricalCSVFeedAdapter(sample_df)
        system = SensexSimulationSystem(feed_adapter=feed)
        runner = SimulationRunner(system=system, speed_delay=args.speed)
        runner.run_replay(max_ticks=args.ticks)
    else:
        system = SensexSimulationSystem()
        runner = SimulationRunner(system=system, speed_delay=args.speed)
        runner.run_live()
