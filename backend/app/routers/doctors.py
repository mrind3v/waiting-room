from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import clinic_zone, local_day_bounds, now
from ..errors import AppError
from ..models import Appointment, Doctor
from ..schemas import Availability, DoctorIn, DoctorOut, Slot

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


def get_doctor_or_404(db: Session, doctor_id: int) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise AppError(404, "DOCTOR_NOT_FOUND", "Doctor not found")
    return doctor


@router.get("", response_model=list[DoctorOut])
def list_doctors(active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Doctor).order_by(Doctor.full_name)
    if active is not None:
        stmt = stmt.where(Doctor.is_active == active)
    return list(db.scalars(stmt))


@router.post("", response_model=DoctorOut, status_code=201)
def create_doctor(payload: DoctorIn, db: Session = Depends(get_db)):
    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.put("/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, payload: DoctorIn, db: Session = Depends(get_db)):
    doctor = get_doctor_or_404(db, doctor_id)
    for key, value in payload.model_dump().items():
        setattr(doctor, key, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.get("/{doctor_id}/availability", response_model=Availability)
def availability(
    doctor_id: int, date: date, db: Session = Depends(get_db), current: datetime = Depends(now)
):
    doctor = get_doctor_or_404(db, doctor_id)
    tz = clinic_zone()
    day_start, day_end = local_day_bounds(date)
    booked = list(
        db.execute(
            select(Appointment.starts_at, Appointment.ends_at).where(
                Appointment.doctor_id == doctor_id,
                Appointment.status != "CANCELLED",
                Appointment.starts_at < day_end,
                Appointment.ends_at > day_start,
            )
        )
    )
    slots: list[Slot] = []
    cursor = datetime.combine(date, doctor.work_start, tzinfo=tz)
    closing = datetime.combine(date, doctor.work_end, tzinfo=tz)
    step = timedelta(minutes=doctor.slot_minutes)
    while cursor + step <= closing:
        s, e = cursor.astimezone(UTC), (cursor + step).astimezone(UTC)
        taken = any(b_start < e and b_end > s for b_start, b_end in booked)
        slots.append(
            Slot(starts_at=s, ends_at=e, available=doctor.is_active and not taken and s >= current)
        )
        cursor += step
    return Availability(doctor_id=doctor_id, date=date, slots=slots)
