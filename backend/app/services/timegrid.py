from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Seoul")


def at(day: date, value: time) -> datetime:
    return datetime.combine(day, value, TZ)


def slots(start: datetime, end: datetime, minutes: int = 15):
    """Half-open [start,end) slots prevent boundary double-counting."""
    step = timedelta(minutes=minutes)
    cursor = start
    while cursor < end:
        yield cursor, min(cursor + step, end)
        cursor += step


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end
