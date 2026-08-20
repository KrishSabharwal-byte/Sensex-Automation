"""
risk_manager.py
Risk Management Engine for BSE Sensex Options.
Handles Dynamic Trailing Stop-Loss (TSL), Target Profit calculation,
minimum holding period noise suppression, and option price zero-clamping safety.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(
        self,
        stop_loss_points: float = 30.0,
        target_points: float = 40.0,
        trail_trigger_points: float = 25.0,
        trail_lock_points: float = 15.0,
        enable_trailing_sl: bool = True,
        min_holding_updates: int = 3,
        min_holding_seconds: float = 30.0
    ):
        self.stop_loss_points = float(stop_loss_points)
        self.target_points = float(target_points)
        self.trail_trigger_points = float(trail_trigger_points)
        self.trail_lock_points = float(trail_lock_points)
        self.enable_trailing_sl = bool(enable_trailing_sl)
        self.min_holding_updates = int(min_holding_updates)
        self.min_holding_seconds = float(min_holding_seconds)

    def calculate_levels(self, entry_price: float) -> Dict[str, Any]:
        """
        Compute Stop-Loss, Target Profit, and Trailing Trigger/Lock absolute price levels.
        """
        if entry_price <= 0:
            logger.warning(f"Option entry price {entry_price} <= 0; clamped to 0.0")
            entry_price = max(0.0, entry_price)

        initial_sl = max(0.0, entry_price - self.stop_loss_points)
        target_price = entry_price + self.target_points
        trail_trigger_price = entry_price + self.trail_trigger_points
        trail_lock_price = entry_price + self.trail_lock_points

        return {
            "entry_price": entry_price,
            "stop_loss_price": initial_sl,
            "target_price": target_price,
            "trail_trigger_price": trail_trigger_price,
            "trail_lock_price": trail_lock_price,
            "stop_loss_points": self.stop_loss_points,
            "target_points": self.target_points,
            "trail_trigger_points": self.trail_trigger_points,
            "trail_lock_points": self.trail_lock_points,
            "enable_trailing_sl": self.enable_trailing_sl
        }

    def evaluate_tick(
        self,
        entry_price: float,
        current_price: float,
        current_sl: Optional[float] = None,
        trailing_active: bool = False,
        elapsed_seconds: float = 0.0,
        update_count: int = 0
    ) -> Tuple[str, str, float, bool]:
        """
        Comprehensive tick evaluator with dynamic Trailing Stop Loss logic.
        
        Logic:
        1. If Trailing SL enabled and current_price >= entry_price + trail_trigger:
           - If not trailing_active:
               trailing_active = True
               current_sl = entry_price + trail_lock
           - Continuous Trailing:
               new_sl = max(current_sl, current_price - (trail_trigger - trail_lock))
               if new_sl > current_sl:
                   current_sl = new_sl
        2. Check Exits:
           - if current_price >= target_price -> EXIT_TARGET ("TARGET HIT")
           - if current_price <= current_sl:
               exit_status = "EXIT_TRAIL_STOPLOSS" if trailing_active else "EXIT_STOPLOSS"
               exit_reason = "TRAIL SL HIT" if trailing_active else "STOP LOSS HIT"
               
        Returns: (exit_status, exit_reason, updated_sl, updated_trailing_active)
        exit_status: 'HOLD', 'EXIT_TARGET', 'EXIT_STOPLOSS', 'EXIT_TRAIL_STOPLOSS'
        """
        if current_price < 0:
            logger.warning(f"Received negative option price {current_price}. Clamping to 0.0.")
            current_price = 0.0

        if current_sl is None:
            current_sl = max(0.0, entry_price - self.stop_loss_points)

        target_level = entry_price + self.target_points

        # 1. Trailing SL Activation & Continuous Trailing
        if self.enable_trailing_sl and current_price >= (entry_price + self.trail_trigger_points):
            if not trailing_active:
                trailing_active = True
                current_sl = max(current_sl, entry_price + self.trail_lock_points)
                logger.info(f"Trailing SL Activated: SL locked at {current_sl:.2f} (+{self.trail_lock_points} pts profit)")

            # Continuous Trailing: Maintain trailing gap
            trail_gap = self.trail_trigger_points - self.trail_lock_points
            new_sl = max(current_sl, current_price - trail_gap)
            if new_sl > current_sl:
                logger.debug(f"Continuous Trailing SL moved up from {current_sl:.2f} to {new_sl:.2f}")
                current_sl = new_sl

        # 2. Check Target Profit hit (immediate exit)
        if current_price >= target_level:
            return (
                "EXIT_TARGET",
                f"TARGET HIT: {current_price:.2f} >= {target_level:.2f} (+{self.target_points} pts)",
                current_sl,
                trailing_active
            )

        # 3. Check Stop-Loss / Trailing SL hit
        if current_price <= current_sl:
            # Trailing SL exits immediately once profit is locked.
            # Initial SL respects minimum holding noise suppression filter.
            is_holding_satisfied = (
                trailing_active or
                elapsed_seconds >= self.min_holding_seconds or
                update_count >= self.min_holding_updates
            )

            if is_holding_satisfied:
                if trailing_active:
                    return (
                        "EXIT_TRAIL_STOPLOSS",
                        f"TRAIL SL HIT: {current_price:.2f} <= {current_sl:.2f}",
                        current_sl,
                        trailing_active
                    )
                else:
                    return (
                        "EXIT_STOPLOSS",
                        f"STOP LOSS HIT: {current_price:.2f} <= {current_sl:.2f} (-{self.stop_loss_points} pts)",
                        current_sl,
                        trailing_active
                    )
            else:
                logger.debug(
                    f"Stop-loss condition met ({current_price:.2f} <= {current_sl:.2f}), "
                    f"but suppressed during min holding window (elapsed={elapsed_seconds:.1f}s/{self.min_holding_seconds}s, updates={update_count}/{self.min_holding_updates})"
                )
                return (
                    "HOLD",
                    f"SL suppressed during min holding period ({update_count}/{self.min_holding_updates} updates)",
                    current_sl,
                    trailing_active
                )

        return ("HOLD", "Within risk boundaries", current_sl, trailing_active)

    def check_exit(
        self,
        entry_price: float,
        current_price: float,
        elapsed_seconds: float = 0.0,
        update_count: int = 0,
        current_sl: Optional[float] = None,
        trailing_active: bool = False
    ) -> Tuple[str, str]:
        """
        Backwards-compatible convenience wrapper returning (exit_status, exit_reason).
        """
        status, reason, _, _ = self.evaluate_tick(
            entry_price=entry_price,
            current_price=current_price,
            current_sl=current_sl,
            trailing_active=trailing_active,
            elapsed_seconds=elapsed_seconds,
            update_count=update_count
        )
        return (status, reason)
