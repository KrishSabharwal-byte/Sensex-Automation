"""
strike_selector.py
BSE Sensex Strike Selection Engine.
Selects ~200 points OTM strikes for CALL and PUT options on Sensex:
- CALL strike: Forced below current LTP (closest 100-point strike ~200 pts below LTP)
- PUT strike: Forced above current LTP (closest 100-point strike ~200 pts above LTP)

Hysteresis: strikes are locked until spot moves >= 40 pts past the new zone boundary,
preventing the strike from oscillating when spot hovers near a rounding boundary.
"""

import math
from typing import Dict, Any, Optional

# Minimum points spot must move past the rounding boundary midpoint before the strike changes.
# With 100-pt interval, the rounding midpoint is at old_strike ± 50.
# Setting band to 55 means spot must be 55 pts past that midpoint to commit a strike change.
_HYSTERESIS_BAND = 55  # points

class SensexStrikeSelector:
    def __init__(self, strike_distance: int = 200, strike_interval: int = 100):
        self.strike_distance = strike_distance
        self.strike_interval = strike_interval

        # Hysteresis state — tracks the last confirmed strikes and the spot at which they were set
        self._last_call_strike: Optional[int] = None
        self._last_put_strike: Optional[int] = None
        self._last_ltp_for_call: Optional[float] = None
        self._last_ltp_for_put: Optional[float] = None

    def _raw_call_strike(self, ltp: float) -> int:
        raw_target = ltp - self.strike_distance
        strike = round(raw_target / self.strike_interval) * self.strike_interval
        if strike >= ltp:
            strike = math.floor((ltp - 1.0) / self.strike_interval) * self.strike_interval
        return int(strike)

    def _raw_put_strike(self, ltp: float) -> int:
        raw_target = ltp + self.strike_distance
        strike = round(raw_target / self.strike_interval) * self.strike_interval
        if strike <= ltp:
            strike = math.ceil((ltp + 1.0) / self.strike_interval) * self.strike_interval
        return int(strike)

    def get_call_strike(self, ltp: float) -> int:
        """
        Calculate CALL strike ~200 points below LTP with hysteresis.
        Strike only changes when spot has moved >= 40 pts into the new zone.
        """
        raw = self._raw_call_strike(ltp)

        if self._last_call_strike is None:
            # Cold start — accept immediately
            self._last_call_strike = raw
            self._last_ltp_for_call = ltp
            return raw

        if raw == self._last_call_strike:
            self._last_ltp_for_call = ltp
            return raw

        # Candidate strike changed — apply hysteresis.
        # The rounding boundary between old strike and new strike is at the midpoint
        # between the two candidate strikes in spot-space.
        # old spot target = old_strike + distance, new spot target = raw + distance
        # midpoint (rounding boundary) = (old + new) / 2 + distance
        boundary = ((self._last_call_strike + raw) / 2.0) + self.strike_distance
        move_past_boundary = abs(ltp - boundary)
        if move_past_boundary >= _HYSTERESIS_BAND:
            self._last_call_strike = raw
            self._last_ltp_for_call = ltp

        return self._last_call_strike

    def get_put_strike(self, ltp: float) -> int:
        """
        Calculate PUT strike ~200 points above LTP with hysteresis.
        Strike only changes when spot has moved >= 40 pts into the new zone.
        """
        raw = self._raw_put_strike(ltp)

        if self._last_put_strike is None:
            self._last_put_strike = raw
            self._last_ltp_for_put = ltp
            return raw

        if raw == self._last_put_strike:
            self._last_ltp_for_put = ltp
            return raw

        boundary = ((self._last_put_strike + raw) / 2.0) - self.strike_distance
        move_past_boundary = abs(ltp - boundary)
        if move_past_boundary >= _HYSTERESIS_BAND:
            self._last_put_strike = raw
            self._last_ltp_for_put = ltp

        return self._last_put_strike

    def get_strikes(self, ltp: float) -> Dict[str, Any]:
        """
        Returns dictionary with call and put strikes for the given Sensex LTP.
        Strikes are stabilised with hysteresis to prevent boundary oscillation.
        """
        if ltp <= 0:
            raise ValueError(f"Invalid LTP value: {ltp}")

        call_strike = self.get_call_strike(ltp)
        put_strike = self.get_put_strike(ltp)

        return {
            "ltp": float(ltp),
            "call_strike": call_strike,
            "put_strike": put_strike,
            "call_symbol": f"SENSEX_{call_strike}_CE",
            "put_symbol": f"SENSEX_{put_strike}_PE"
        }

    def reset(self):
        """Resets hysteresis state (call when session is cleared or on reset)."""
        self._last_call_strike = None
        self._last_put_strike = None
        self._last_ltp_for_call = None
        self._last_ltp_for_put = None

# Backwards compatibility alias
BankNiftyStrikeSelector = SensexStrikeSelector

if __name__ == "__main__":
    selector = SensexStrikeSelector()
    # Simulate spot bouncing between 77418 and 77452 (boundary oscillation scenario)
    for spot in [77500, 77452, 77418, 77445, 77412, 77380, 77320]:
        result = selector.get_strikes(spot)
        print(f"Spot {spot}: call={result['call_strike']} CE | put={result['put_strike']} PE")
