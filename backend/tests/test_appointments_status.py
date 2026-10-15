from datetime import UTC

from .conftest import at


def test_full_status_flow_sets_timestamps(client, clock, doctor, patient, book):
    appt = book(patient["id"], doctor["id"], at(14, 0, day=4)).json()
    url = f"/api/appointments/{appt['id']}/status"

    clock.set_local(13, 50)
    r = client.post(url, json={"status": "CHECKED_IN"})
    assert r.status_code == 200 and r.json()["status"] == "CHECKED_IN"
    assert r.json()["checked_in_at"] == at(13, 50, day=4).astimezone(UTC).isoformat().replace(
        "+00:00", "Z"
    )

    clock.set_local(14, 5)
    r = client.post(url, json={"status": "IN_CONSULTATION"})
    assert r.json()["consultation_started_at"] is not None

    clock.set_local(14, 20)
    r = client.post(url, json={"status": "DONE"})
    assert r.json()["status"] == "DONE"
    assert r.json()["completed_at"] is not None


def test_invalid_transition_409(client, doctor, patient, book):
    appt = book(patient["id"], doctor["id"], at(10)).json()
    url = f"/api/appointments/{appt['id']}/status"
    r = client.post(url, json={"status": "DONE"})
    assert r.status_code == 409
    assert r.json()["code"] == "INVALID_TRANSITION"
    assert "CHECKED_IN" in r.json()["allowed"]

    client.post(url, json={"status": "CHECKED_IN"})
    client.post(url, json={"status": "IN_CONSULTATION"})
    client.post(url, json={"status": "DONE"})
    again = client.post(url, json={"status": "CANCELLED"})
    assert again.status_code == 409


def test_cancel_records_reason_and_cannot_target_booked(client, doctor, patient, book):
    appt = book(patient["id"], doctor["id"], at(10)).json()
    url = f"/api/appointments/{appt['id']}/status"
    assert client.post(url, json={"status": "BOOKED"}).status_code == 422
    r = client.post(url, json={"status": "CANCELLED", "cancel_reason": "Patient unwell"})
    assert r.status_code == 200
    assert r.json()["cancel_reason"] == "Patient unwell"
    assert r.json()["cancelled_at"] is not None


def test_status_404_and_delete_only_cancelled(client, doctor, patient, book):
    assert client.post("/api/appointments/999/status", json={"status": "DONE"}).status_code == 404
    appt = book(patient["id"], doctor["id"], at(10)).json()
    assert client.delete(f"/api/appointments/{appt['id']}").status_code == 409
    client.post(f"/api/appointments/{appt['id']}/status", json={"status": "CANCELLED"})
    assert client.delete(f"/api/appointments/{appt['id']}").status_code == 204
    assert client.get(f"/api/appointments/{appt['id']}").status_code == 404


def test_list_appointments_filters(client, clock, doctor, make_patient, book):
    a, b = make_patient("A"), make_patient("B")
    first = book(a["id"], doctor["id"], at(14, 0, day=4)).json()
    book(b["id"], doctor["id"], at(15, 0, day=4))
    book(b["id"], doctor["id"], at(10, 0, day=5))
    today = client.get("/api/appointments").json()  # defaults to clinic "today" (frozen)
    assert len(today) == 2
    assert [x["starts_at"] for x in today] == sorted(x["starts_at"] for x in today)
    client.post(f"/api/appointments/{first['id']}/status", json={"status": "CHECKED_IN"})
    only = client.get("/api/appointments", params={"status": "CHECKED_IN"}).json()
    assert [x["id"] for x in only] == [first["id"]]
    tomorrow = client.get("/api/appointments", params={"date": "2030-03-05"}).json()
    assert len(tomorrow) == 1
