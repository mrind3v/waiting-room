from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import clinic_zone, local_day_bounds, local_today, now
from ..errors import AppError
from ..metrics import APPOINTMENTS_BOOKED, BOOKING_CONFLICTS, TRANSITIONS
from ..models import Appointment, Doctor, Patient
from ..schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, Status, StatusChange
from ..status_flow import apply_transition

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


def to_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id,
        patient_id=a.patient_id,
        patient_name=a.patient.full_name,
        doctor_id=a.doctor_id,
        doctor_name=a.doctor.full_name,
        room=a.doctor.room,
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        reason=a.reason,
        status=a.status,
        checked_in_at=a.checked_in_at,
        consultation_started_at=a.consultation_started_at,
        completed_at=a.completed_at,
        cancelled_at=a.cancelled_at,
        cancel_reason=a.cancel_reason,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _get_or_404(db: Session, appt_id: int, *, lock: bool = False) -> Appointment:
    stmt = select(Appointment).where(Appointment.id == appt_id)
    if lock:
        stmt = stmt.with_for_update(of=Appointment)
    appt = db.scalars(stmt).first()
    if not appt:
        raise AppError(404, "APPOINTMENT_NOT_FOUND", "Appointment not found")
    return appt


def _check_slot_rules(doctor: Doctor, starts_at: datetime, ends_at: datetime, current: datetime):
    if not doctor.is_active:
        raise AppError(422, "DOCTOR_INACTIVE", f"{doctor.full_name} is not taking appointments")
    if starts_at < current:
        raise AppError(422, "IN_PAST", "Appointment cannot start in the past")
    tz = clinic_zone()
    ls, le = starts_at.astimezone(tz), ends_at.astimezone(tz)
    if ls.date() != le.date() or ls.time() < doctor.work_start or le.time() > doctor.work_end:
        raise AppError(
            422,
            "OUTSIDE_WORKING_HOURS",
            f"{doctor.full_name} works {doctor.work_start:%H:%M}-{doctor.work_end:%H:%M}",
        )


def _conflict(doctor: Doctor, starts_at: datetime, ends_at: datetime) -> AppError:
    BOOKING_CONFLICTS.inc()
    tz = clinic_zone()
    return AppError(
        409,
        "SLOT_TAKEN",
        f"{doctor.full_name} already has an appointment overlapping "
        f"{starts_at.astimezone(tz):%H:%M}-{ends_at.astimezone(tz):%H:%M}",
    )


def _commit_or_conflict(db: Session, doctor: Doctor, starts_at: datetime, ends_at: datetime):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # 23P01 = exclusion_violation: the no-overlap constraint fired.
        if getattr(exc.orig, "sqlstate", None) == "23P01":
            raise _conflict(doctor, starts_at, ends_at) from exc
        raise


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    date: date | None = None,
    doctor_id: int | None = None,
    status: Status | None = None,
    db: Session = Depends(get_db),
    current: datetime = Depends(now),
):
    day = date or local_today(current)
    start, end = local_day_bounds(day)
    stmt = (
        select(Appointment)
        .where(Appointment.starts_at >= start, Appointment.starts_at < end)
        .order_by(Appointment.starts_at, Appointment.id)
    )
    if doctor_id is not None:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if status is not None:
        stmt = stmt.where(Appointment.status == status)
    return [to_out(a) for a in db.scalars(stmt).unique()]


@router.get("/{appt_id}", response_model=AppointmentOut)
def get_appointment(appt_id: int, db: Session = Depends(get_db)):
    return to_out(_get_or_404(db, appt_id))


@router.post("", response_model=AppointmentOut, status_code=201)
def book_appointment(
    payload: AppointmentCreate, db: Session = Depends(get_db), current: datetime = Depends(now)
):
    if not db.get(Patient, payload.patient_id):
        raise AppError(404, "PATIENT_NOT_FOUND", "Patient not found")
    doctor = db.get(Doctor, payload.doctor_id)
    if not doctor:
        raise AppError(404, "DOCTOR_NOT_FOUND", "Doctor not found")
    minutes = payload.duration_minutes or doctor.slot_minutes
    starts_at = payload.starts_at
    ends_at = starts_at + timedelta(minutes=minutes)
    _check_slot_rules(doctor, starts_at, ends_at, current)
    appt = Appointment(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=payload.reason,
        status="BOOKED",
        created_at=current,
        updated_at=current,
    )
    db.add(appt)
    _commit_or_conflict(db, doctor, starts_at, ends_at)
    APPOINTMENTS_BOOKED.inc()
    db.refresh(appt)
    return to_out(appt)


@router.put("/{appt_id}", response_model=AppointmentOut)
def reschedule_appointment(
    appt_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    current: datetime = Depends(now),
):
    appt = _get_or_404(db, appt_id, lock=True)
    if appt.status != "BOOKED":
        raise AppError(
            409, "NOT_EDITABLE", f"Only BOOKED appointments can be edited ({appt.status})"
        )
    doctor = db.get(Doctor, payload.doctor_id or appt.doctor_id)
    if not doctor:
        raise AppError(404, "DOCTOR_NOT_FOUND", "Doctor not found")
    starts_at = payload.starts_at or appt.starts_at
    minutes = payload.duration_minutes or int((appt.ends_at - appt.starts_at).total_seconds() // 60)
    ends_at = starts_at + timedelta(minutes=minutes)
    if payload.starts_at or payload.doctor_id or payload.duration_minutes:
        _check_slot_rules(doctor, starts_at, ends_at, current)
    appt.doctor_id = doctor.id
    appt.starts_at, appt.ends_at = starts_at, ends_at
    if payload.reason is not None:
        appt.reason = payload.reason
    appt.updated_at = current
    _commit_or_conflict(db, doctor, starts_at, ends_at)
    db.expire(appt)
    return to_out(_get_or_404(db, appt_id))


@router.post("/{appt_id}/status", response_model=AppointmentOut)
def change_status(
    appt_id: int,
    payload: StatusChange,
    db: Session = Depends(get_db),
    current: datetime = Depends(now),
):
    appt = _get_or_404(db, appt_id, lock=True)
    apply_transition(appt, payload.status, current, payload.cancel_reason)
    db.commit()
    TRANSITIONS.labels(to_status=payload.status).inc()
    return to_out(_get_or_404(db, appt_id))


@router.delete("/{appt_id}", status_code=204)
def delete_appointment(appt_id: int, db: Session = Depends(get_db)):
    appt = _get_or_404(db, appt_id)
    if appt.status != "CANCELLED":
        raise AppError(409, "NOT_CANCELLED", "Only CANCELLED appointments can be deleted")
    db.delete(appt)
    db.commit()
    return Response(status_code=204)
