from app import seed

from .conftest import at


def test_today_counts_and_avg_wait(client, clock, doctor, make_patient, book):
    a, b, c = make_patient("A"), make_patient("B"), make_patient("C")
    one = book(a["id"], doctor["id"], at(14, 0, day=4)).json()
    book(b["id"], doctor["id"], at(14, 30, day=4))
    cancelled = book(c["id"], doctor["id"], at(15, 0, day=4)).json()
    client.post(f"/api/appointments/{cancelled['id']}/status", json={"status": "CANCELLED"})

    clock.set_local(13, 40)
    client.post(f"/api/appointments/{one['id']}/status", json={"status": "CHECKED_IN"})
    clock.set_local(14, 0)
    client.post(f"/api/appointments/{one['id']}/status", json={"status": "IN_CONSULTATION"})

    data = client.get("/api/dashboard/today").json()
    assert data["booked"] == 1
    assert data["in_consultation"] == 1
    assert data["cancelled"] == 1
    assert data["avg_wait_minutes"] == 20.0
    assert [n["status"] for n in data["next_up"]] == ["BOOKED"]


def test_dashboard_empty_day(client):
    data = client.get("/api/dashboard/today").json()
    assert data["avg_wait_minutes"] is None
    assert data["next_up"] == []


def test_seed_is_idempotent(client):
    seed.main()
    seed.main()
    assert len(client.get("/api/doctors").json()) == 4
