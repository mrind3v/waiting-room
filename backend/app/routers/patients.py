from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import now
from ..errors import AppError
from ..models import Appointment, Patient
from ..schemas import PatientDetail, PatientIn, PatientOut
from .appointments import to_out

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None)


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise AppError(404, "PATIENT_NOT_FOUND", "Patient not found")
    return patient


@router.get("", response_model=list[PatientOut])
def search_patients(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Patient).order_by(Patient.full_name).limit(50)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Patient.full_name.ilike(like), Patient.phone.ilike(like)))
    return list(db.scalars(stmt))


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int, db: Session = Depends(get_db), current: datetime = Depends(now)):
    patient = get_patient_or_404(db, patient_id)
    upcoming = db.scalars(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status.in_(("BOOKED", "CHECKED_IN", "IN_CONSULTATION")),
            Appointment.ends_at >= current,
        )
        .order_by(Appointment.starts_at)
    )
    data = PatientOut.model_validate(patient, from_attributes=True).model_dump()
    return PatientDetail(**data, upcoming_appointments=[to_out(a) for a in upcoming])


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientIn, db: Session = Depends(get_db)):
    patient = Patient(**payload.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _sqlstate(exc) == "23505":
            raise AppError(
                409, "DUPLICATE_PHONE", "A patient with this phone already exists"
            ) from exc
        raise
    db.refresh(patient)
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, payload: PatientIn, db: Session = Depends(get_db)):
    patient = get_patient_or_404(db, patient_id)
    for key, value in payload.model_dump().items():
        setattr(patient, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _sqlstate(exc) == "23505":
            raise AppError(
                409, "DUPLICATE_PHONE", "A patient with this phone already exists"
            ) from exc
        raise
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=204)
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = get_patient_or_404(db, patient_id)
    has_any = db.scalar(select(Appointment.id).where(Appointment.patient_id == patient_id).limit(1))
    if has_any:
        raise AppError(409, "HAS_APPOINTMENTS", "Patient has appointments and cannot be deleted")
    db.delete(patient)
    db.commit()
    return Response(status_code=204)
