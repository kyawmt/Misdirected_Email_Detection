"""Chronological split windows.

Boundaries are Mondays so each generated week falls in exactly one split.
End timestamps are exclusive.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

UTC = timezone.utc

# (name, inclusive start, exclusive end) as UTC instants.
SPLIT_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("warmup", "2024-01-08T00:00:00Z", "2024-07-01T00:00:00Z"),
    ("train", "2024-07-01T00:00:00Z", "2025-03-31T00:00:00Z"),
    ("validation", "2025-03-31T00:00:00Z", "2025-09-01T00:00:00Z"),
    ("test", "2025-09-01T00:00:00Z", "2026-01-05T00:00:00Z"),
)

SPLIT_NAMES = tuple(name for name, _, _ in SPLIT_WINDOWS)
ASSESSMENT_SPLITS = ("train", "validation", "test")
FROZEN_SUBSETS = ("test_product_like", "test_diagnostic")


def parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp lacks a timezone: {value}")
    return parsed.astimezone(UTC)


def format_ts(value: datetime) -> str:
    current = value.astimezone(UTC).replace(microsecond=0)
    return current.strftime("%Y-%m-%dT%H:%M:%SZ")


@lru_cache(maxsize=1)
def windows() -> tuple[tuple[str, datetime, datetime], ...]:
    return tuple((name, parse_ts(start), parse_ts(end)) for name, start, end in SPLIT_WINDOWS)


def split_for(moment: datetime) -> str:
    current = moment.astimezone(UTC)
    for name, start, end in windows():
        if start <= current < end:
            return name
    raise ValueError(f"Timestamp is outside the dataset calendar: {format_ts(current)}")


def split_bounds(name: str) -> tuple[datetime, datetime]:
    for candidate, start, end in windows():
        if candidate == name:
            return start, end
    raise KeyError(name)


def iter_weeks():
    start, _ = split_bounds("warmup")
    _, end = split_bounds("test")
    cursor = start
    while cursor < end:
        yield cursor
        cursor += timedelta(days=7)


def weeks_in(split: str) -> list[datetime]:
    start, end = split_bounds(split)
    return [week for week in iter_weeks() if start <= week < end]
