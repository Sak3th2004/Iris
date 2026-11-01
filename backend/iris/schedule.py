"""Real appointment times. The gate still does not know what a booking is."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TZ = ZoneInfo("Asia/Kolkata")


def move_to_weekday(fields: dict, day: str, *, now: datetime | None = None) -> dict:
    if day not in WEEKDAYS:
        raise ValueError("Choose a valid weekday.")
    now = (now or datetime.now(TZ)).astimezone(TZ)
    clock = _clock(fields)
    start = (now + timedelta(days=(WEEKDAYS.index(day)-now.weekday()) % 7)).replace(
        hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
    if start <= now:
        start += timedelta(days=7)
    return {"day": day, "time": start.strftime("%H:%M"), "starts_at": start.isoformat()}


def _clock(fields: dict) -> datetime:
    raw = fields.get("starts_at")
    if isinstance(raw, str) and raw:
        parsed=datetime.fromisoformat(raw)
        if parsed.tzinfo is None: raise ValueError('Booking timestamps must include a timezone.')
        return parsed.astimezone(TZ)
    hour, minute = str(fields.get("time", "10:00")).split(":")
    return datetime(2000,1,1,hour=int(hour),minute=int(minute),tzinfo=TZ)


def interval(fields: dict):
    if fields.get('status') == 'cancelled' or not fields.get('starts_at'): return None
    start=datetime.fromisoformat(fields['starts_at'])
    duration=fields.get('duration_minutes',60)
    if start.tzinfo is None or type(duration) is not int or not 1 <= duration <= 1440:
        raise ValueError('A booking needs a timezone and a duration from 1 to 1440 minutes.')
    return start,start+timedelta(minutes=duration)


def overlaps(first: dict, second: dict) -> bool:
    if first.get('host','Studio') != second.get('host','Studio'): return False
    a,b=interval(first),interval(second)
    return bool(a and b and a[0] < b[1] and b[0] < a[1])
