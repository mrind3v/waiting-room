from datetime import datetime

from .errors import AppError
from .models import Appointment

# target status -> statuses it may be entered from
ALLOWED_FROM: dict[str, tuple[str, ...]] = {
    "CHECKED_IN": ("BOOKED",),
    "IN_CONSULTATION": ("CHECKED_IN",),
    "DONE": ("IN_CONSULTATION",),
    "CANCELLED": ("BOOKED", "CHECKED_IN"),
}

TIMESTAMP_FIELD = {
    "CHECKED_IN": "checked_in_at",
    "IN_CONSULTATION": "consultation_started_at",
    "DONE": "completed_at",
    "CANCELLED": "cancelled_at",
}


def next_targets(current: str) -> list[str]:
    return [to for to, sources in ALLOWED_FROM.items() if current in sources]


def apply_transition(
    appt: Appointment, to_status: str, at: datetime, cancel_reason: str | None
) -> None:
    allowed = ALLOWED_FROM.get(to_status)
    if allowed is None:
        raise AppError(422, "INVALID_STATUS", f"Cannot move an appointment to {to_status}")
    if appt.status not in allowed:
        raise AppError(
            409,
            "INVALID_TRANSITION",
            f"Cannot move appointment from {appt.status} to {to_status}",
            allowed=next_targets(appt.status),
        )
    appt.status = to_status
    setattr(appt, TIMESTAMP_FIELD[to_status], at)
    if to_status == "CANCELLED":
        appt.cancel_reason = cancel_reason
    appt.updated_at = at
