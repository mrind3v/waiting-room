"""Idempotent demo data: `python -m app.seed`. Skips if any doctor already exists."""

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select

from .db import SessionLocal
from .deps import clinic_zone, now
from .models import Appointment, Doctor, Patient

DOCTORS = [
    ("Dr. Amelia Chen", "General Practice", "Room 1", 15),
    ("Dr. Marcus Oyelaran", "Paediatrics", "Room 2", 20),
    ("Dr. Priya Raman", "Cardiology", "Room 3", 30),
    ("Dr. Tom Hargreaves", "Dermatology", "Room 4", 15),
]
PATIENTS = [
    ("Isla Thompson", "1988-03-14"),
    ("Noah Williams", "1975-11-02"),
    ("Olivia Nguyen", "2015-06-21"),
    ("Liam Patel", "1992-09-09"),
    ("Charlotte Kelly", "1960-01-30"),
    ("Oliver Brown", "2001-12-17"),
    ("Ava Martin", "1983-07-25"),
    ("Jack Wilson", "1999-04-04"),
    ("Mia Taylor", "2010-10-10"),
    ("Ethan Davies", "1955-05-19"),
    ("Grace Murphy", "1978-08-08"),
    ("Lucas Scott", "1990-02-27"),
    ("Sophie Evans", "1969-06-06"),
    ("Henry Clarke", "2018-01-15"),
    ("Zoe Harris", "1995-03-03"),
]
# (doctor index, minutes after 09:00, status, minutes since check-in / start)
PLAN = [
    (0, 0, "DONE", 0),
    (0, 15, "IN_CONSULTATION", 4),
    (0, 30, "CHECKED_IN", 12),
    (0, 45, "CHECKED_IN", 3),
    (0, 60, "BOOKED", 0),
    (0, 90, "CANCELLED", 0),
    (1, 0, "DONE", 0),
    (1, 20, "IN_CONSULTATION", 7),
    (1, 40, "CHECKED_IN", 9),
    (1, 60, "BOOKED", 0),
    (1, 80, "BOOKED", 0),
    (2, 0, "IN_CONSULTATION", 11),
    (2, 30, "CHECKED_IN", 5),
    (2, 60, "BOOKED", 0),
    (3, 15, "CHECKED_IN", 16),
    (3, 30, "BOOKED", 0),
    (3, 45, "BOOKED", 0),
]
REASONS = ["Check-up", "Follow-up", "Vaccination", "Skin rash", "Chest pain review", "Referral"]


def main() -> None:
    current = now()
    tz = clinic_zone()
    with SessionLocal() as db:
        if db.scalar(select(Doctor.id).limit(1)):
            print("seed: doctors already exist, nothing to do")
            return
        doctors = [
            Doctor(
                full_name=n,
                specialty=s,
                room=r,
                slot_minutes=m,
                work_start=time(9, 0),
                work_end=time(17, 0),
            )
            for n, s, r, m in DOCTORS
        ]
        patients = [
            Patient(
                full_name=n,
                date_of_birth=datetime.fromisoformat(d).date(),
                phone=f"04{i:02d}555{i * 7 % 1000:03d}",
            )
            for i, (n, d) in enumerate(PATIENTS, start=10)
        ]
        db.add_all(doctors + patients)
        db.flush()

        local_day = current.astimezone(tz).date()
        base = datetime.combine(local_day, time(9, 0), tzinfo=tz).astimezone(UTC)
        for i, (d_idx, offset, status, mins) in enumerate(PLAN):
            doc = doctors[d_idx]
            start = base + timedelta(minutes=offset)
            appt = Appointment(
                patient_id=patients[i % len(patients)].id,
                doctor_id=doc.id,
                starts_at=start,
                ends_at=start + timedelta(minutes=doc.slot_minutes),
                reason=REASONS[i % len(REASONS)],
                status=status,
            )
            if status in ("CHECKED_IN", "IN_CONSULTATION", "DONE"):
                appt.checked_in_at = current - timedelta(minutes=mins + 10)
            if status == "CHECKED_IN":
                appt.checked_in_at = current - timedelta(minutes=mins)
            if status in ("IN_CONSULTATION", "DONE"):
                appt.consultation_started_at = current - timedelta(minutes=mins)
            if status == "DONE":
                appt.completed_at = current - timedelta(minutes=5)
            if status == "CANCELLED":
                appt.cancelled_at = current - timedelta(hours=1)
                appt.cancel_reason = "Patient called to cancel"
            db.add(appt)
        db.commit()
        print(f"seed: {len(doctors)} doctors, {len(patients)} patients, {len(PLAN)} appointments")


if __name__ == "__main__":
    main()
