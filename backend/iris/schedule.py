"""Real appointment times. The gate still does not know what a booking is."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TZ = ZoneInfo("Asia/Kolkata")
WEEK = datetime(2026, 11, 2, tzinfo=TZ)  # Monday of the demo week.


def move_to_weekday(fields: dict, day: str) -> dict:
    if day not in WEEKDAYS:
        raise ValueError("Choose a weekday in the studio week.")
    clock = _clock(fields)
    start = (WEEK + timedelta(days=WEEKDAYS.index(day))).replace(
        hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
    return {"day": day, "time": start.strftime("%H:%M"), "starts_at": start.isoformat()}


def _clock(fields: dict) -> datetime:
    raw = fields.get("starts_at")
    if isinstance(raw, str) and raw:
        return datetime.fromisoformat(raw)
    hour, minute = str(fields.get("time", "10:00")).split(":")
    return WEEK.replace(hour=int(hour), minute=int(minute))
