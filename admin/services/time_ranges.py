from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

def now_utc():
    return datetime.now(timezone.utc)

def parse_time_range(range_key: str, start: Optional[str] = None, end: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    range_key: "today", "7d", "30d", "this_month", "custom"
    start/end for custom = ISO8601 or "YYYY-MM-DD"
    """
    n = now_utc()
    if range_key == "today":
        start_dt = n.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = n
    elif range_key == "7d":
        start_dt = n - timedelta(days=7)
        end_dt = n
    elif range_key == "30d":
        start_dt = n - timedelta(days=30)
        end_dt = n
    elif range_key == "this_month":
        first = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_dt = first
        end_dt = n
    elif range_key == "custom":
        if not start or not end:
            raise ValueError("custom range requires start and end")
        # naive parsing; accepts YYYY-MM-DD or full ISO
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        if start_dt.tzinfo is None: start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:   end_dt = end_dt.replace(tzinfo=timezone.utc)
    else:
        raise ValueError("invalid range key")
    return start_dt, end_dt
