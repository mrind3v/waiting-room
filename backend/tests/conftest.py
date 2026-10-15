import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# --- configure the app for tests BEFORE importing it -------------------------------------
_url = os.environ.get("TEST_DATABASE_URL")
if not _url and os.environ.get("POSTGRES_PASSWORD"):
    _url = (
        f"postgresql+psycopg://waitingroom:{os.environ['POSTGRES_PASSWORD']}"
        "@127.0.0.1:5432/waitingroom_test"
    )
if not _url:
    pytest.exit("Set TEST_DATABASE_URL (database name must end with _test)", returncode=2)
if not _url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    pytest.exit("Refusing to run: test database name must end with '_test'", returncode=2)

os.environ["DATABASE_URL"] = _url
os.environ["CLINIC_TZ"] = "Australia/Sydney"
os.environ["GIT_SHA"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.deps import now as now_dep  # noqa: E402
from app.main import app  # noqa: E402

SYDNEY = ZoneInfo("Australia/Sydney")
BACKEND = Path(__file__).resolve().parents[1]


def at(hour: int, minute: int = 0, day: int = 5) -> datetime:
    """Local clinic time on 2030-03-<day> (AEDT, so safely in the 'future' of the clock)."""
    return datetime(2030, 3, day, hour, minute, tzinfo=SYDNEY)


class Clock:
    def __init__(self):
        self.now = datetime(2030, 3, 4, 0, 0, tzinfo=UTC)  # 2030-03-04 11:00 Sydney

    def set_local(self, hour: int, minute: int = 0, day: int = 4):
        self.now = at(hour, minute, day).astimezone(UTC)


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_schema):
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE appointments, patients, doctors RESTART IDENTITY CASCADE"))


@pytest.fixture
def clock():
    c = Clock()
    app.dependency_overrides[now_dep] = lambda: c.now
    yield c
    app.dependency_overrides.pop(now_dep, None)


@pytest.fixture
def client(clock):
    return TestClient(app)


@pytest.fixture
def doctor(client):
    r = client.post(
        "/api/doctors",
        json={"full_name": "Dr. Test", "specialty": "General Practice", "slot_minutes": 15},
    )
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def make_patient(client):
    counter = iter(range(1000))

    def _make(name: str = "Pat Ient") -> dict:
        r = client.post(
            "/api/patients",
            json={
                "full_name": name,
                "date_of_birth": "1990-05-05",
                "phone": f"0400{next(counter):06d}",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def patient(make_patient):
    return make_patient()


@pytest.fixture
def book(client):
    def _book(patient_id, doctor_id, start: datetime, minutes: int | None = None, **extra):
        body = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "starts_at": start.isoformat(),
            **extra,
        }
        if minutes:
            body["duration_minutes"] = minutes
        return client.post("/api/appointments", json=body)

    return _book


def day(d: int = 5) -> date:
    return date(2030, 3, d)


def utc_plus(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)
