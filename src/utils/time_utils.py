from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as dateutil_parser


def parse_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = dateutil_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, OverflowError):
        return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
