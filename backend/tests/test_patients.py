from .conftest import at


def test_register_patient_and_duplicate_phone_409(client):
    body = {"full_name": "Ann Lee", "date_of_birth": "1985-02-01", "phone": "0412 345 678"}
    r = client.post("/api/patients", json=body)
    assert r.status_code == 201
    assert r.json()["phone"] == "0412345678"  # normalised
    dup = client.post("/api/patients", json={**body, "full_name": "Other"})
    assert dup.status_code == 409
    assert dup.json()["code"] == "DUPLICATE_PHONE"


def test_patient_validation_422(client):
    r = client.post(
        "/api/patients", json={"full_name": "A", "date_of_birth": "2999-01-01", "phone": "abc"}
    )
    assert r.status_code == 422


def test_search_patients_by_name_and_phone(client, make_patient):
    make_patient("Alice Wong")
    make_patient("Bob Marley")
    assert [p["full_name"] for p in client.get("/api/patients", params={"q": "ali"}).json()] == [
        "Alice Wong"
    ]
    assert len(client.get("/api/patients", params={"q": "0400"}).json()) == 2


def test_update_patient_put(client, patient):
    r = client.put(
        f"/api/patients/{patient['id']}",
        json={
            "full_name": "Renamed",
            "date_of_birth": "1990-05-05",
            "phone": patient["phone"],
            "notes": "allergic to penicillin",
        },
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "allergic to penicillin"
    assert client.get(f"/api/patients/{patient['id']}").json()["full_name"] == "Renamed"


def test_patient_detail_lists_upcoming_appointments(client, doctor, patient, book):
    book(patient["id"], doctor["id"], at(10))
    detail = client.get(f"/api/patients/{patient['id']}").json()
    assert len(detail["upcoming_appointments"]) == 1
    assert detail["upcoming_appointments"][0]["doctor_name"] == "Dr. Test"


def test_delete_patient_204_and_409_when_has_appointments(client, doctor, make_patient, book):
    free = make_patient("Free One")
    busy = make_patient("Busy One")
    book(busy["id"], doctor["id"], at(10))
    assert client.delete(f"/api/patients/{free['id']}").status_code == 204
    assert client.get(f"/api/patients/{free['id']}").status_code == 404
    r = client.delete(f"/api/patients/{busy['id']}")
    assert r.status_code == 409
    assert r.json()["code"] == "HAS_APPOINTMENTS"
