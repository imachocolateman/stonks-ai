"""Custom indicators not in TA-Lib. For everything else, use talib directly."""

import numpy as np


def vwap(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray
) -> np.ndarray:
    """Volume Weighted Average Price (cumulative, reset at market open for intraday)."""
    tp = (high + low + close) / 3
    cum_tp_vol = np.cumsum(tp * volume)
    cum_vol = np.cumsum(volume)
    return np.divide(
        cum_tp_vol, cum_vol, out=np.zeros_like(cum_tp_vol), where=cum_vol != 0
    )


def pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """Standard pivot points from previous day's HLC."""
    pp = (high + low + close) / 3
    return {
        "PP": pp,
        "R1": 2 * pp - low,
        "R2": pp + (high - low),
        "R3": high + 2 * (pp - low),
        "S1": 2 * pp - high,
        "S2": pp - (high - low),
        "S3": low - 2 * (high - pp),
    }


def latest(arr: np.ndarray) -> float | None:
    """Get last non-NaN value from array."""
    if arr is None or len(arr) == 0:
        return None
    valid = arr[~np.isnan(arr)]
    return float(valid[-1]) if len(valid) > 0 else None
