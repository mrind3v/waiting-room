from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

STATUSES = ("BOOKED", "CHECKED_IN", "IN_CONSULTATION", "DONE", "CANCELLED")


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (
        CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="ck_doctors_slot_minutes"),
        CheckConstraint("work_end > work_start", name="ck_doctors_work_hours"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(80))
    room: Mapped[str | None] = mapped_column(String(20))
    slot_minutes: Mapped[int] = mapped_column(SmallInteger, server_default="15")
    work_start: Mapped[time] = mapped_column(Time, server_default="09:00")
    work_end: Mapped[time] = mapped_column(Time, server_default="17:00")
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (CheckConstraint("date_of_birth <= current_date", name="ck_patients_dob"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(254))
    notes: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointments_range"),
        CheckConstraint(
            "status IN ('BOOKED','CHECKED_IN','IN_CONSULTATION','DONE','CANCELLED')",
            name="ck_appointments_status",
        ),
        Index("ix_appointments_doctor_starts", "doctor_id", "starts_at"),
        Index("ix_appointments_starts", "starts_at"),
        Index("ix_appointments_patient", "patient_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(255), server_default="")
    status: Mapped[str] = mapped_column(String(20), server_default="BOOKED")
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consultation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[Patient] = relationship(lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")
