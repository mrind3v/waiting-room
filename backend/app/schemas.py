import re
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Status = Literal["BOOKED", "CHECKED_IN", "IN_CONSULTATION", "DONE", "CANCELLED"]


class DoctorIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    specialty: str = Field(min_length=1, max_length=80)
    room: str | None = Field(default=None, max_length=20)
    slot_minutes: int = Field(default=15, ge=5, le=120)
    work_start: time = time(9, 0)
    work_end: time = time(17, 0)
    is_active: bool = True

    @model_validator(mode="after")
    def _hours(self):
        if self.work_end <= self.work_start:
            raise ValueError("work_end must be after work_start")
        return self


class DoctorOut(DoctorIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class PatientIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    phone: str
    email: EmailStr | None = None
    notes: str = ""

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-().]", "", v)
        if not re.fullmatch(r"\+?\d{6,19}", cleaned):
            raise ValueError("phone must contain 6-19 digits (optional leading +)")
        return cleaned

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v


class PatientOut(PatientIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    starts_at: datetime
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
    reason: str = Field(default="", max_length=255)

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("starts_at must include a timezone offset")
        return v


class AppointmentUpdate(BaseModel):
    doctor_id: int | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("starts_at must include a timezone offset")
        return v


class StatusChange(BaseModel):
    status: Status
    cancel_reason: str | None = Field(default=None, max_length=255)


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    doctor_name: str
    room: str | None
    starts_at: datetime
    ends_at: datetime
    reason: str
    status: Status
    checked_in_at: datetime | None
    consultation_started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class PatientDetail(PatientOut):
    upcoming_appointments: list[AppointmentOut]


class Slot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    available: bool


class Availability(BaseModel):
    doctor_id: int
    date: date
    slots: list[Slot]


class NextUp(BaseModel):
    id: int
    patient_name: str
    doctor_name: str
    starts_at: datetime
    status: Status


class DashboardToday(BaseModel):
    date: date
    booked: int
    checked_in: int
    in_consultation: int
    done: int
    cancelled: int
    avg_wait_minutes: float | None
    next_up: list[NextUp]
