from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import local_day_bounds, local_today, now
from ..models import Appointment
from ..schemas import DashboardToday, NextUp

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/today", response_model=DashboardToday)
def today(
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
    current: datetime = Depends(now),
):
    day = local_today(current)
    start, end = local_day_bounds(day)
    base = [Appointment.starts_at >= start, Appointment.starts_at < end]
    if doctor_id is not None:
        base.append(Appointment.doctor_id == doctor_id)

    counts = dict(
        db.execute(
            select(Appointment.status, func.count()).where(*base).group_by(Appointment.status)
        ).all()
    )
    wait_seconds = db.scalar(
        select(
            func.avg(
                func.extract(
                    "epoch", Appointment.consultation_started_at - Appointment.checked_in_at
                )
            )
        ).where(
            *base,
            Appointment.consultation_started_at.is_not(None),
            Appointment.checked_in_at.is_not(None),
        )
    )
    upcoming = db.scalars(
        select(Appointment)
        .where(*base, Appointment.status.in_(("BOOKED", "CHECKED_IN")))
        .order_by(Appointment.starts_at)
        .limit(5)
    ).unique()
    return DashboardToday(
        date=day,
        booked=counts.get("BOOKED", 0),
        checked_in=counts.get("CHECKED_IN", 0),
        in_consultation=counts.get("IN_CONSULTATION", 0),
        done=counts.get("DONE", 0),
        cancelled=counts.get("CANCELLED", 0),
        avg_wait_minutes=round(float(wait_seconds) / 60, 1) if wait_seconds is not None else None,
        next_up=[
            NextUp(
                id=a.id,
                patient_name=a.patient.full_name,
                doctor_name=a.doctor.full_name,
                starts_at=a.starts_at,
                status=a.status,
            )
            for a in upcoming
        ],
    )
