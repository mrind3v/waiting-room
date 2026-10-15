#!/usr/bin/env bash
# End-to-end API walkthrough. Usage: BASE=http://localhost:8000 ./scripts/smoke-api.sh
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"
fail() { echo "FAIL: $*" >&2; exit 1; }
code() { curl -s -o /tmp/smoke.json -w '%{http_code}' "$@"; }
expect() { local want=$1; shift; local got; got=$(code "$@"); [ "$got" = "$want" ] || { cat /tmp/smoke.json; fail "expected $want got $got: $*"; }; }
J='content-type: application/json'
SUF=$(date +%s)

expect 200 "$BASE/health"
expect 200 "$BASE/ready"
expect 200 "$BASE/metrics"
expect 201 -X POST "$BASE/api/doctors" -H "$J" -d '{"full_name":"Dr Smoke","specialty":"GP","slot_minutes":15}'
DOC=$(python3 -c 'import json;print(json.load(open("/tmp/smoke.json"))["id"])')
expect 201 -X POST "$BASE/api/patients" -H "$J" -d "{\"full_name\":\"Smoke Patient\",\"date_of_birth\":\"1990-01-01\",\"phone\":\"+6140${SUF: -7}\"}"
PAT=$(python3 -c 'import json;print(json.load(open("/tmp/smoke.json"))["id"])')
expect 409 -X POST "$BASE/api/patients" -H "$J" -d "{\"full_name\":\"Dup\",\"date_of_birth\":\"1990-01-01\",\"phone\":\"+6140${SUF: -7}\"}"

# next weekday-agnostic slot: tomorrow 10:00 Sydney == use availability to find a free slot
TOMORROW=$(python3 -c 'import datetime as d;print(d.date.today()+d.timedelta(days=2))')
expect 200 "$BASE/api/doctors/$DOC/availability?date=$TOMORROW"
START=$(python3 -c 'import json;print([s for s in json.load(open("/tmp/smoke.json"))["slots"] if s["available"]][4]["starts_at"])')
expect 201 -X POST "$BASE/api/appointments" -H "$J" -d "{\"patient_id\":$PAT,\"doctor_id\":$DOC,\"starts_at\":\"$START\",\"reason\":\"smoke\"}"
APPT=$(python3 -c 'import json;print(json.load(open("/tmp/smoke.json"))["id"])')
expect 409 -X POST "$BASE/api/appointments" -H "$J" -d "{\"patient_id\":$PAT,\"doctor_id\":$DOC,\"starts_at\":\"$START\"}"
grep -q SLOT_TAKEN /tmp/smoke.json || fail "expected SLOT_TAKEN"
expect 409 -X POST "$BASE/api/appointments/$APPT/status" -H "$J" -d '{"status":"DONE"}'
for s in CHECKED_IN IN_CONSULTATION DONE; do
  expect 200 -X POST "$BASE/api/appointments/$APPT/status" -H "$J" -d "{\"status\":\"$s\"}"
done
expect 200 "$BASE/api/dashboard/today"
expect 409 -X DELETE "$BASE/api/patients/$PAT"
curl -s "$BASE/metrics" | grep -q waitingroom_booking_conflicts_total || fail "custom metric missing"
echo "smoke OK"
