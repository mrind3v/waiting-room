from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import get_settings


def now() -> datetime:
    """Current UTC time. A dependency so tests can freeze the clock."""
    return datetime.now(UTC)


def clinic_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_tz)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = clinic_zone()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def local_today(at: datetime) -> date:
    return at.astimezone(clinic_zone()).date()
