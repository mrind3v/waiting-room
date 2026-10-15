import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import at


def test_book_appointment_computes_ends_at(doctor, patient, book):
    r = book(patient["id"], doctor["id"], at(10, 0), reason="Check-up")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "BOOKED"
    assert body["patient_name"] == patient["full_name"]
    assert body["ends_at"] == "2030-03-04T23:15:00Z"  # 10:15 Sydney == 23:15Z the day before


def test_same_slot_double_booking_409(doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    assert book(a["id"], doctor["id"], at(10, 0)).status_code == 201
    r = book(b["id"], doctor["id"], at(10, 0))
    assert r.status_code == 409
    assert r.json()["code"] == "SLOT_TAKEN"


def test_partial_overlap_409(doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    assert book(a["id"], doctor["id"], at(10, 0), minutes=30).status_code == 201
    r = book(b["id"], doctor["id"], at(10, 15), minutes=15)
    assert r.status_code == 409
    assert r.json()["code"] == "SLOT_TAKEN"


def test_back_to_back_slots_allowed(doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    assert book(a["id"], doctor["id"], at(10, 0)).status_code == 201
    assert book(b["id"], doctor["id"], at(10, 15)).status_code == 201


def test_same_time_different_doctor_allowed(client, doctor, make_patient, book):
    other = client.post("/api/doctors", json={"full_name": "Dr. Two", "specialty": "GP"}).json()
    a, b = make_patient("A"), make_patient("B")
    assert book(a["id"], doctor["id"], at(10, 0)).status_code == 201
    assert book(b["id"], other["id"], at(10, 0)).status_code == 201


def test_cancelled_appointment_frees_slot(client, doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    first = book(a["id"], doctor["id"], at(10, 0)).json()
    assert book(b["id"], doctor["id"], at(10, 0)).status_code == 409
    client.post(f"/api/appointments/{first['id']}/status", json={"status": "CANCELLED"})
    assert book(b["id"], doctor["id"], at(10, 0)).status_code == 201


def test_reschedule_into_overlap_409_and_only_when_booked(client, doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    book(a["id"], doctor["id"], at(10, 0))
    second = book(b["id"], doctor["id"], at(11, 0)).json()
    url = f"/api/appointments/{second['id']}"

    clash = client.put(url, json={"starts_at": at(10, 10).isoformat()})
    assert clash.status_code == 409
    assert clash.json()["code"] == "SLOT_TAKEN"

    ok = client.put(url, json={"starts_at": at(10, 15).isoformat(), "reason": "moved"})
    assert ok.status_code == 200
    assert ok.json()["reason"] == "moved"

    client.post(f"{url}/status", json={"status": "CHECKED_IN"})
    locked = client.put(url, json={"reason": "late edit"})
    assert locked.status_code == 409
    assert locked.json()["code"] == "NOT_EDITABLE"


def test_outside_hours_inactive_doctor_and_past_422(client, doctor, patient, book):
    early = book(patient["id"], doctor["id"], at(8, 0))
    assert early.status_code == 422 and early.json()["code"] == "OUTSIDE_WORKING_HOURS"
    late = book(patient["id"], doctor["id"], at(16, 50), minutes=30)
    assert late.status_code == 422 and late.json()["code"] == "OUTSIDE_WORKING_HOURS"
    past = book(patient["id"], doctor["id"], at(9, 0, day=1))
    assert past.status_code == 422 and past.json()["code"] == "IN_PAST"
    client.put(f"/api/doctors/{doctor['id']}", json={**doctor, "is_active": False})
    inactive = book(patient["id"], doctor["id"], at(10, 0))
    assert inactive.status_code == 422 and inactive.json()["code"] == "DOCTOR_INACTIVE"


def test_unknown_patient_or_doctor_404(doctor, patient, book):
    assert book(9999, doctor["id"], at(10)).status_code == 404
    assert book(patient["id"], 9999, at(10)).status_code == 404


def test_naive_datetime_rejected(client, doctor, patient):
    r = client.post(
        "/api/appointments",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "starts_at": "2030-03-05T10:00:00",
        },
    )
    assert r.status_code == 422


@pytest.mark.concurrency
def test_concurrent_booking_only_one_wins(doctor, make_patient):
    a, b = make_patient("A"), make_patient("B")
    barrier = threading.Barrier(2)
    results: list[int] = []

    def worker(pid: int):
        c = TestClient(app)
        barrier.wait()
        r = c.post(
            "/api/appointments",
            json={"patient_id": pid, "doctor_id": doctor["id"], "starts_at": at(10).isoformat()},
        )
        results.append(r.status_code)

    threads = [threading.Thread(target=worker, args=(p["id"],)) for p in (a, b)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201, 409]
