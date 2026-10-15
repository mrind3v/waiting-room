from .conftest import at, day


def test_create_and_list_doctors(client):
    r = client.post(
        "/api/doctors", json={"full_name": "Dr. B", "specialty": "Paediatrics", "room": "Room 2"}
    )
    assert r.status_code == 201
    client.post("/api/doctors", json={"full_name": "Dr. A", "specialty": "GP", "is_active": False})
    names = [d["full_name"] for d in client.get("/api/doctors").json()]
    assert names == ["Dr. A", "Dr. B"]
    active = client.get("/api/doctors", params={"active": True}).json()
    assert [d["full_name"] for d in active] == ["Dr. B"]


def test_create_doctor_validation_422(client):
    r = client.post(
        "/api/doctors",
        json={"full_name": "X", "specialty": "GP", "work_start": "17:00", "work_end": "09:00"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_update_doctor_put_and_404(client, doctor):
    payload = {**doctor, "room": "Room 9", "is_active": False}
    r = client.put(f"/api/doctors/{doctor['id']}", json=payload)
    assert r.status_code == 200
    assert r.json()["room"] == "Room 9"
    assert r.json()["is_active"] is False
    assert client.put("/api/doctors/9999", json=payload).status_code == 404


def test_availability_marks_booked_unavailable_and_cancelled_free(client, doctor, patient, book):
    start = at(10, 0)
    appt = book(patient["id"], doctor["id"], start).json()

    def slot_at_10():
        slots = client.get(
            f"/api/doctors/{doctor['id']}/availability", params={"date": day().isoformat()}
        ).json()["slots"]
        assert len(slots) == 32  # 09:00-17:00 in 15 min steps
        return next(s for s in slots if s["starts_at"].startswith("2030-03-04T23:00"))

    assert slot_at_10()["available"] is False
    r = client.post(f"/api/appointments/{appt['id']}/status", json={"status": "CANCELLED"})
    assert r.status_code == 200
    assert slot_at_10()["available"] is True


def test_availability_404_for_unknown_doctor(client):
    r = client.get("/api/doctors/999/availability", params={"date": "2030-03-05"})
    assert r.status_code == 404
