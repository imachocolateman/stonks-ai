"""Trading session time utilities."""

from datetime import datetime, time
from enum import Enum

import pytz

from src.config import get_settings

# US Eastern timezone for market hours
ET = pytz.timezone("US/Eastern")


class SessionPhase(str, Enum):
    """Trading session phases per 0DTE strategy."""

    PRE_MARKET = "pre_market"
    PRIME_TIME = "prime_time"  # 9:30-11:00 - best for V-dip setups
    LUNCH_DOLDRUMS = "lunch_doldrums"  # 11:00-13:30 - avoid
    MID_SESSION = "mid_session"  # 13:30-15:30 - post-lunch repositioning
    DANGER_ZONE = "danger_zone"  # 15:30-16:00 - extreme gamma risk
    AFTER_HOURS = "after_hours"


def _parse_time(t: str) -> time:
    """Parse HH:MM string to time object."""
    h, m = map(int, t.split(":"))
    return time(h, m)


def get_et_now() -> datetime:
    """Get current time in US Eastern."""
    return datetime.now(ET)


def get_session_phase(dt: datetime | None = None) -> SessionPhase:
    """
    Determine current trading session phase.

    Per strategy doc:
    - Prime Time: 9:30-11:00 (60% of daily range forms here)
    - Lunch: 11:00-13:30 (volatility drops 30-50%)
    - Mid Session: 13:30-15:30 (56.1% chance SPX closes within 0.20% of 1:30 price)
    - Danger Zone: 15:30-16:00 (extreme gamma risk)
    """
    if dt is None:
        dt = get_et_now()
    elif dt.tzinfo is None:
        dt = ET.localize(dt)
    else:
        dt = dt.astimezone(ET)

    settings = get_settings()
    current = dt.time()

    market_open = _parse_time(settings.market_open)
    market_close = _parse_time(settings.market_close)
    prime_end = _parse_time(settings.prime_time_end)
    lunch_end = _parse_time(settings.lunch_end)
    danger_start = _parse_time(settings.danger_zone_start)

    if current < market_open:
        return SessionPhase.PRE_MARKET
    elif current < prime_end:
        return SessionPhase.PRIME_TIME
    elif current < lunch_end:
        return SessionPhase.LUNCH_DOLDRUMS
    elif current < danger_start:
        return SessionPhase.MID_SESSION
    elif current < market_close:
        return SessionPhase.DANGER_ZONE
    else:
        return SessionPhase.AFTER_HOURS


def is_trading_allowed(dt: datetime | None = None) -> tuple[bool, str]:
    """
    Check if trading is allowed at given time.

    Returns (allowed, reason) tuple.
    """
    phase = get_session_phase(dt)

    if phase == SessionPhase.PRE_MARKET:
        return False, "Market not open yet"
    elif phase == SessionPhase.AFTER_HOURS:
        return False, "Market closed"
    elif phase == SessionPhase.DANGER_ZONE:
        return False, "DANGER ZONE - exit positions only, no new trades"
    elif phase == SessionPhase.LUNCH_DOLDRUMS:
        return True, "Lunch doldrums - low volatility, consider waiting"

    return True, f"Trading allowed ({phase.value})"


def minutes_to_close(dt: datetime | None = None) -> int:
    """Calculate minutes until market close (4:00 PM ET)."""
    if dt is None:
        dt = get_et_now()
    elif dt.tzinfo is None:
        dt = ET.localize(dt)
    else:
        dt = dt.astimezone(ET)

    settings = get_settings()
    close_time = _parse_time(settings.market_close)
    close_dt = dt.replace(
        hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0
    )

    if dt >= close_dt:
        return 0

    delta = close_dt - dt
    return int(delta.total_seconds() / 60)


def minutes_to_exit_deadline(dt: datetime | None = None) -> int:
    """Calculate minutes until exit deadline (3:45 PM ET)."""
    if dt is None:
        dt = get_et_now()
    elif dt.tzinfo is None:
        dt = ET.localize(dt)
    else:
        dt = dt.astimezone(ET)

    settings = get_settings()
    deadline = _parse_time(settings.exit_deadline)
    deadline_dt = dt.replace(
        hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0
    )

    if dt >= deadline_dt:
        return 0

    delta = deadline_dt - dt
    return int(delta.total_seconds() / 60)


def is_0dte_day(dt: datetime | None = None) -> bool:
    """
    Check if today is a 0DTE expiration day.

    SPX has expirations on Mon, Wed, Fri (and daily since late 2022).
    For this strategy we focus on Mon/Wed/Fri.
    """
    if dt is None:
        dt = get_et_now()

    # Monday=0, Wednesday=2, Friday=4
    return dt.weekday() in (0, 2, 4)


def get_session_info(dt: datetime | None = None) -> dict:
    """Get comprehensive session info for display."""
    if dt is None:
        dt = get_et_now()

    phase = get_session_phase(dt)
    allowed, reason = is_trading_allowed(dt)
    to_close = minutes_to_close(dt)
    to_exit = minutes_to_exit_deadline(dt)
    is_0dte = is_0dte_day(dt)

    return {
        "current_time_et": dt.strftime("%H:%M:%S ET"),
        "session_phase": phase.value,
        "trading_allowed": allowed,
        "reason": reason,
        "minutes_to_close": to_close,
        "minutes_to_exit_deadline": to_exit,
        "is_0dte_day": is_0dte,
        "weekday": dt.strftime("%A"),
    }


def get_phase_description(phase: SessionPhase) -> str:
    """Get description of session phase."""
    descriptions = {
        SessionPhase.PRE_MARKET: "Market not yet open",
        SessionPhase.PRIME_TIME: "Prime trading hours (9:30-11:00) - Best for V-dip setups",
        SessionPhase.LUNCH_DOLDRUMS: "Lunch doldrums (11:00-13:30) - Low volatility, wider spreads",
        SessionPhase.MID_SESSION: "Mid session (13:30-15:30) - Post-lunch repositioning",
        SessionPhase.DANGER_ZONE: "DANGER ZONE (15:30-16:00) - Exit all positions by 15:45!",
        SessionPhase.AFTER_HOURS: "Market closed",
    }
    return descriptions.get(phase, "Unknown phase")
