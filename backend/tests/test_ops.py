from app.routers import ops


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_reports_ready_when_db_up(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_ready_returns_503_when_schema_not_at_head(client, monkeypatch):
    monkeypatch.setattr(ops, "_alembic_head", lambda: "does-not-exist")
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not-ready"


def test_metrics_exposes_prometheus_and_custom_counters(client):
    client.get("/api/doctors")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "waitingroom_booking_conflicts_total" in body


def test_root_and_config(client):
    assert client.get("/").json()["service"] == "waiting-room-api"
    assert client.get("/api/config").json()["clinic_tz"] == "Australia/Sydney"


def test_unknown_route_uses_error_shape(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["code"] == "HTTP_404"
