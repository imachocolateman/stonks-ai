"""Unit tests for pure bar aggregation logic."""

from datetime import datetime, timezone

from src.data.bar_aggregator import Bar, bucket_start, update_bar


def t(hh: int, mm: int, ss: int, micro: int = 0) -> datetime:
    """UTC timestamp shorthand for tests."""
    return datetime(2026, 6, 1, hh, mm, ss, micro, tzinfo=timezone.utc)


# ---- bucket_start ----


def test_bucket_start_floors_to_5s_boundary():
    assert bucket_start(t(13, 30, 7), 5) == t(13, 30, 5)
    assert bucket_start(t(13, 30, 9, 999), 5) == t(13, 30, 5)
    assert bucket_start(t(13, 30, 10), 5) == t(13, 30, 10)


def test_bucket_start_handles_naive_datetime_as_utc():
    naive = datetime(2026, 6, 1, 13, 30, 7)  # no tzinfo
    assert bucket_start(naive, 5) == t(13, 30, 5)


def test_bucket_start_works_with_other_intervals():
    assert bucket_start(t(13, 32, 30), 60) == t(13, 32, 0)
    assert bucket_start(t(13, 32, 30), 1) == t(13, 32, 30)


# ---- update_bar: first tick creates the bar ----


def test_first_tick_initializes_bar():
    bar, closed = update_bar(None, 7580.5, 100, t(9, 30, 2), 5)
    assert closed is None
    assert bar.bucket_ts == t(9, 30, 0)
    assert bar.open == bar.high == bar.low == bar.close == 7580.5
    assert bar.volume == 100
    assert bar.tick_count == 1


# ---- update_bar: same bucket extends OHLC ----


def test_same_bucket_updates_high_low_close():
    bar, _ = update_bar(None, 7580.0, 50, t(9, 30, 0), 5)
    bar, closed = update_bar(bar, 7585.0, 30, t(9, 30, 2), 5)
    assert closed is None
    assert bar.open == 7580.0  # unchanged
    assert bar.high == 7585.0
    assert bar.low == 7580.0
    assert bar.close == 7585.0
    assert bar.volume == 80
    assert bar.tick_count == 2


def test_same_bucket_with_lower_price_updates_low():
    bar, _ = update_bar(None, 7580.0, 0, t(9, 30, 0), 5)
    bar, _ = update_bar(bar, 7575.0, 0, t(9, 30, 1), 5)
    bar, _ = update_bar(bar, 7582.0, 0, t(9, 30, 3), 5)
    assert bar.open == 7580.0
    assert bar.high == 7582.0
    assert bar.low == 7575.0
    assert bar.close == 7582.0


# ---- update_bar: bucket rollover closes the bar ----


def test_rollover_returns_closed_bar_and_starts_new():
    bar, _ = update_bar(None, 7580.0, 100, t(9, 30, 1), 5)
    bar, _ = update_bar(bar, 7583.0, 50, t(9, 30, 3), 5)
    new_bar, closed = update_bar(bar, 7585.0, 25, t(9, 30, 5), 5)
    # the 9:30:00-9:30:04 bar closes
    assert closed is not None
    assert closed.bucket_ts == t(9, 30, 0)
    assert closed.open == 7580.0
    assert closed.high == 7583.0
    assert closed.close == 7583.0
    assert closed.volume == 150
    # new bar starts at 9:30:05
    assert new_bar.bucket_ts == t(9, 30, 5)
    assert new_bar.open == 7585.0
    assert new_bar.tick_count == 1


def test_rollover_skipping_buckets_is_safe():
    """If no tick lands in a bucket, we don't synthesize an empty bar.
    The next tick simply opens whatever bucket it falls into.
    """
    bar, _ = update_bar(None, 7580.0, 0, t(9, 30, 1), 5)
    new_bar, closed = update_bar(bar, 7590.0, 0, t(9, 30, 17), 5)
    assert closed is not None
    assert closed.bucket_ts == t(9, 30, 0)
    assert new_bar.bucket_ts == t(9, 30, 15)  # 9:30:15-19, not 9:30:05-09


# ---- update_bar: out-of-order ticks (clock skew protection) ----


def test_tick_landing_in_current_bucket_with_earlier_ts_still_aggregates():
    """A delayed tick that lands inside the current bucket should still aggregate.
    (Sequence numbering / dedup happens upstream in TickSubscriber.)
    """
    bar, _ = update_bar(None, 7580.0, 0, t(9, 30, 3), 5)
    bar, closed = update_bar(bar, 7579.0, 0, t(9, 30, 1), 5)  # earlier ts, same bucket
    assert closed is None
    assert bar.low == 7579.0
    assert bar.close == 7579.0  # close is latest tick we saw, ts-naive


# ---- Bar.to_dict for Lightweight Charts ----


def test_to_dict_uses_unix_seconds_time_key():
    bar = Bar(
        bucket_ts=t(9, 30, 0),
        open=7580.0, high=7585.0, low=7579.0, close=7583.0,
        volume=500, tick_count=10,
    )
    d = bar.to_dict()
    assert d["time"] == int(t(9, 30, 0).timestamp())
    assert d["open"] == 7580.0
    assert d["close"] == 7583.0
    assert d["volume"] == 500
    assert "tick_count" not in d  # internal detail
