# PLAN.md — Waiting Room (DevOps Capstone)

> Implementation plan for the implementing model (Sonnet). Save this file as `PLAN.md` at the repo root. Do the phases **in order**. Every phase ends with a verification command that must pass before the next phase starts. Make one or more meaningful commits per phase (see §11).

---

## 0. Context and facts this plan is built on

**Why:** This is the final capstone for the DevOps course. The instructor's reference app, TaskBoard (`./reference/`), shows the expected pipeline: app → tests → Docker → CI → Trivy → GHCR → Terraform/EKS → Helm → Ingress → HPA → Prometheus/Grafana. `reference/GRADING.md` gives **zero for clones**, so Waiting Room must be its own domain. It is a clinic front-desk and queue system with doctors, patients, appointments, a status flow and double-booking prevention. Only the DevOps architecture follows the reference. Target: **100/100** with as little AWS spend as possible.

**Things I verified live on the AWS project (read-only calls, 2026-10-15):**

| Fact | Value | Consequence for the plan |
|---|---|---|
| Account / profile | `802823597889`, profile `agent-toolkit` | All AWS CLI/Terraform calls use `AWS_PROFILE=agent-toolkit` |
| Selected Region | **ap-southeast-2** (confirmed by user) | Every Regional resource goes here; AZs `ap-southeast-2a`, `ap-southeast-2b` |
| Plan type | **FREE**, $100 credits, expires 2027-04-15 | Spend can't go past the credits, but using them up ends the Free plan. **Do not upgrade to Paid.** |
| Free-plan SCP | **Spot denied** (`DenySpotMarketType`), **`iam:*Provider*` denied** | No spot instances. **No IAM OIDC provider**, which rules out IRSA and GitHub-OIDC→AWS. Use **EKS Pod Identity** for the EBS CSI driver and a **short-lived IAM user** for CI deploys |
| Free-plan EC2 types | only `t3.micro, t3.small, t4g.micro, t4g.small, c7i-flex.large, m7i-flex.large` | `t3.medium` is **not allowed**. Use **1 × m7i-flex.large** (2 vCPU / 8 GiB / 29 pods) |
| EKS versions | 1.35–1.37 standard support; ≤1.33 extended | Use **1.35**. The reference's 1.31 is on extended support, which bills $0.60/h instead of $0.10/h |
| Existing budgets / clusters | none / none | Budget is step zero |
| Git | `reference/` is already in `.gitignore`; remote `github.com/mrind3v/waiting-room` is **public** | Never commit `reference/` (plagiarism signal) |
| Local tools | docker 29, kind, kubectl, helm, terraform, node 24, uv, gh present | Everything runs locally first |

**User preferences:** help level **HIGH** (explain each step, suggest alternatives, flag trade-offs, then do what the user picks). Demo is a **recorded walkthrough with a single AWS window**.

---

## 1. Hard rules for the implementing agent (put these in CLAUDE.md, Phase 0)

1. **Never** run `terraform apply`, `terraform destroy`, `eksctl`, or any AWS call that creates, modifies or deletes resources without the user's explicit approval **in that turn**. Before any apply, run `terraform plan -out=tfplan` and show its summary (resource count and list) first. Read-only AWS calls are fine.
2. Use the AWS MCP server (`run_script`) for AWS API calls, not raw `aws` in Bash. Exception: Terraform and `aws eks update-kubeconfig`, which the user runs or approves.
3. All Regional resources go in `ap-southeast-2`. Nothing else in `us-east-1` except Budgets, which is a global API.
4. Never print secrets (DB password, Grafana password, IAM access keys) to the chat or to logs. Pipe them straight into `kubectl create secret` or `gh secret set`.
5. Never commit `reference/`, `.env`, `*.tfstate`, `tfplan`, `kubeconfig`, or `terraform.tfvars`.
6. Pin every dependency to an exact version: pip, npm lockfile, Docker base images (tag + digest), Helm charts (`--version`), GitHub Actions (full commit SHA), Terraform modules and providers. At build time, resolve the **current** latest stable version and record it in `docs/VERSIONS.md`. Do not use `latest`.
7. Before any EKS or Terraform work, load the `aws-containers` AWS skill via `retrieve_skill` and check module inputs against the **pinned** module version's docs. Input names changed between terraform-aws-eks v20 and v21.

---

## 2. Architecture

```text
 Developer laptop (100% of dev/test)            GitHub
 ┌──────────────────────────────────┐   push   ┌───────────────────────────────────────────┐
 │ docker compose (db, migrate,     │ ───────► │ Actions: ci-cd.yml                        │
 │   backend, frontend)             │          │  lint+pytest(PG svc) │ frontend lint+build │
 │ kind cluster (same Helm chart,   │          │  infra-lint (tf validate, helm lint,      │
 │   Traefik, metrics-server,       │          │    kubeconform)                           │
 │   kube-prometheus-stack)         │          │  build → Trivy (fail HIGH/CRIT) → push    │
 └──────────────────────────────────┘          │    ghcr.io/mrind3v/waiting-room-{backend, │
                                               │    frontend}:<git-sha>                    │
                                               │  deploy (only if vars.DEPLOY_ENABLED)     │
                                               └───────────────┬───────────────────────────┘
                                                               │ helm upgrade --install
 AWS ap-southeast-2 (short window only)                        ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ VPC 10.30.0.0/16 — 2 public subnets (2a, 2b), IGW, NO NAT, NO private subnets          │
 │  EKS 1.35 (public endpoint) — addons: vpc-cni, coredns, kube-proxy,                    │
 │   eks-pod-identity-agent, aws-ebs-csi-driver (Pod Identity)                            │
 │  Managed node group: 1 × m7i-flex.large ON_DEMAND (min1/max2), public IP               │
 │  ┌────────────── namespace: waiting-room ───────────────┐  ┌──── ns: monitoring ────┐  │
 │  │ Ingress (Traefik) ─ /api → backend Svc (ClusterIP)   │  │ Prometheus (emptyDir)  │  │
 │  │                   └ /    → frontend Svc (ClusterIP)  │  │ Grafana (port-forward) │  │
 │  │ backend Deploy ×2+ (HPA 2–5) ─ initContainer alembic │◄─┤ ServiceMonitor scrape  │  │
 │  │ frontend Deploy ×2+ (HPA 2–4) nginx-unprivileged     │  └────────────────────────┘  │
 │  │ postgres StatefulSet ×1 + 1Gi gp3 PVC                │                              │
 │  └──────────────────────────────────────────────────────┘                              │
 │  ns traefik: Traefik Service type=LoadBalancer → 1 NLB (the only public entrypoint)    │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

**Key decisions (with reasons):**

- **Ingress controller: Traefik** (Helm), the same on kind and EKS. The reference assumes ingress-nginx, which has been retired upstream and is no longer maintained. Traefik implements standard `networking.k8s.io/v1` Ingress, so the rubric item "Ingress routes `/` and `/api`" is met unchanged. On EKS its Service is annotated `service.beta.kubernetes.io/aws-load-balancer-type: nlb`, so the built-in AWS cloud provider creates **one NLB**. This avoids installing the AWS Load Balancer Controller, which would need IAM plus an OIDC provider that the Free-plan SCP denies.
- **Public subnets only, no NAT:** NAT costs about $0.06/h plus data. Nodes get public IPs, and their security group allows only cluster traffic in. *Trade-off:* this is less isolated than private nodes, which is acceptable for a short demo and is written up in the README.
- **Postgres in-cluster as a StatefulSet** with a 1 Gi gp3 PVC. No RDS.
- **Migrations:** an `initContainer` runs `alembic upgrade head` under a Postgres **advisory lock**, so concurrent replicas are safe. Uvicorn does not run migrations. Compose uses a one-shot `migrate` service.
- **Prometheus/Grafana are not exposed publicly.** Access is via `kubectl port-forward`, so no extra load balancers.
- **CI → EKS auth:** a Terraform-managed IAM user `waiting-room-ci` that only has `eks:DescribeCluster`. It maps through an EKS access entry to a K8s group bound by a **namespace-scoped Role**. It exists only during the AWS window and is destroyed with the stack. (GitHub OIDC is the better pattern but is blocked by the Free-plan SCP; the README explains this.)

---

## 3. Final repo tree

```text
waiting-room/
├── README.md                     # what it does, architecture, quickstart, API, pipeline, cost
├── PLAN.md                       # this file
├── CLAUDE.md                     # AWS guidance + agent hard rules (§1) + help_level: HIGH
├── Makefile                      # up/down/test/lint/kind-*/tf-plan (NO apply/destroy targets)
├── .gitignore  .editorconfig  .pre-commit-config.yaml (ruff, eslint, terraform fmt, gitleaks)
├── .claude/settings.json         # deny: Bash(terraform apply*), Bash(terraform destroy*), Bash(eksctl*)
├── docker-compose.yml
├── .env.example                  # POSTGRES_PASSWORD=change-me etc. (compose reads .env)
├── backend/
│   ├── Dockerfile  .dockerignore
│   ├── requirements.txt          # runtime only, exact pins
│   ├── requirements-dev.txt      # -r requirements.txt + pytest, pytest-cov, httpx, ruff
│   ├── pyproject.toml            # ruff config only
│   ├── pytest.ini  alembic.ini
│   ├── alembic/env.py            # advisory lock; URL from settings
│   ├── alembic/versions/
│   │   ├── 0001_doctors_patients.py
│   │   └── 0002_appointments.py  # btree_gist + EXCLUDE constraint
│   ├── app/
│   │   ├── main.py               # create_app(), lifespan, routers, instrumentator
│   │   ├── config.py             # pydantic-settings; DB_* parts → SQLAlchemy URL
│   │   ├── db.py                 # engine, SessionLocal, Base, get_db
│   │   ├── models.py             # Doctor, Patient, Appointment
│   │   ├── schemas.py
│   │   ├── status_flow.py        # transition table + timestamp side effects
│   │   ├── metrics.py            # custom Prometheus counters
│   │   ├── seed.py               # `python -m app.seed` idempotent fake demo data
│   │   └── routers/{ops,doctors,patients,appointments,dashboard}.py
│   └── tests/
│       ├── conftest.py           # test DB guard, alembic upgrade, truncate per test, factories
│       ├── test_ops.py  test_doctors.py  test_patients.py
│       ├── test_appointments_booking.py   # double-booking rules
│       ├── test_appointments_status.py    # status flow
│       └── test_dashboard.py
├── frontend/
│   ├── Dockerfile  .dockerignore  nginx/default.conf.template
│   ├── package.json  package-lock.json  vite.config.js  eslint.config.js  index.html
│   └── src/
│       ├── main.jsx  App.jsx  api/client.js  hooks/usePolling.js  utils/time.js
│       ├── pages/{BoardPage,SchedulePage,PatientsPage,DoctorsPage}.jsx
│       ├── components/{TopNav,KpiStrip,BoardColumn,AppointmentCard,BookingDialog,
│       │               PatientForm,DoctorForm,StatusBadge,ErrorBanner,EmptyState}.jsx
│       └── styles/{tokens.css,layout.css,components.css}
├── .github/
│   ├── workflows/ci-cd.yml
│   └── dependabot.yml            # github-actions, pip, npm, docker weekly
├── terraform/
│   ├── versions.tf  providers.tf  variables.tf  main.tf (vpc, eks)  iam_ci.tf  outputs.tf
│   ├── terraform.tfvars.example  .terraform.lock.hcl (COMMITTED)  README.md
├── k8s/
│   ├── namespace.yaml            # waiting-room (+ monitoring, traefik)
│   ├── kind-config.yaml          # port mapping 30080 → host 8080
│   ├── storageclass-gp3.yaml     # EKS only, default SC, reclaimPolicy Delete
│   └── rbac-ci-deployer.yaml     # EKS only: Role + RoleBinding for group waiting-room-deployers
├── helm/waiting-room/
│   ├── Chart.yaml  values.yaml  values-kind.yaml  values-eks.yaml  .helmignore
│   ├── dashboards/waiting-room.json
│   └── templates/ _helpers.tpl NOTES.txt
│       backend-deployment.yaml backend-service.yaml backend-hpa.yaml
│       frontend-deployment.yaml frontend-service.yaml frontend-hpa.yaml
│       postgres-statefulset.yaml postgres-service.yaml
│       ingress.yaml servicemonitor.yaml grafana-dashboard-configmap.yaml
├── monitoring/
│   ├── kube-prometheus-stack-values.yaml   # Prometheus + Grafana values (rubric M9)
│   ├── traefik-values-kind.yaml  traefik-values-eks.yaml
│   └── metrics-server-values.yaml
├── scripts/
│   ├── cluster-bootstrap.sh      # <kind|eks>: ns, SC, secrets, metrics-server, traefik, kps
│   ├── smoke-api.sh              # curl walkthrough of every endpoint
│   ├── load-test.sh              # runs fortio Job in-cluster to trigger HPA
│   ├── pre-destroy.sh            # helm uninstall all, delete PVCs, wait for NLB/EBS gone
│   └── verify-teardown.sh        # read-only AWS inventory (ap-southeast-2 + us-east-1 logs)
├── troubleshooting/
│   ├── broken-image.yaml  broken-service.yaml  broken-readiness.yaml
│   └── README.md                 # symptom → commands → root cause → fix
└── docs/
    ├── ARCHITECTURE.md  RUNBOOK-AWS.md  SECURITY-SCAN.md  VERSIONS.md  SUBMISSION.md
    └── screenshots/              # named per §12
```

---

## 4. Data model

### Tables (Alembic-managed; **no** `create_all` anywhere)

**doctors**
| column | type | notes |
|---|---|---|
| id | serial PK | |
| full_name | varchar(120) not null | |
| specialty | varchar(80) not null | e.g. "General Practice", "Paediatrics" |
| room | varchar(20) null | "Room 3" (shown on board) |
| slot_minutes | smallint not null default 15 | CHECK 5–120 |
| work_start / work_end | time not null default 09:00 / 17:00 | CHECK work_end > work_start |
| is_active | bool not null default true | soft-retire instead of delete |
| created_at | timestamptz not null default now() | |

**patients**
| column | type | notes |
|---|---|---|
| id | serial PK | |
| full_name | varchar(120) not null | |
| date_of_birth | date not null | CHECK ≤ current_date |
| phone | varchar(20) not null **UNIQUE** | normalized (digits and +) in schema validator; duplicate → 409 |
| email | varchar(254) null | |
| notes | text not null default '' | |
| created_at | timestamptz not null default now() | |

**appointments**
| column | type | notes |
|---|---|---|
| id | serial PK | |
| patient_id | FK patients ON DELETE RESTRICT | |
| doctor_id | FK doctors ON DELETE RESTRICT | |
| starts_at, ends_at | timestamptz not null | CHECK `ends_at > starts_at`; stored UTC |
| reason | varchar(255) not null default '' | |
| status | varchar(20) not null default 'BOOKED' | CHECK in (BOOKED, CHECKED_IN, IN_CONSULTATION, DONE, CANCELLED) |
| checked_in_at, consultation_started_at, completed_at, cancelled_at | timestamptz null | set by status transitions; used to compute wait time |
| cancel_reason | varchar(255) null | |
| created_at, updated_at | timestamptz not null default now() | updated_at set in app on change |

Indexes: `(doctor_id, starts_at)`, `(starts_at)`, `(patient_id)`.

### Double-booking: an exclusion constraint, decided

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE appointments ADD CONSTRAINT appointments_no_doctor_overlap
  EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
  WHERE (status <> 'CANCELLED');
```

**Why this approach:**
- A unique `(doctor_id, starts_at)` index only catches **identical** start times. It misses 10:00–10:30 vs 10:15–10:30, and misses rescheduling into a partial overlap.
- An application-level "SELECT then INSERT" check is **racy**: two receptionists can book in the same millisecond. The exclusion constraint is enforced by Postgres atomically, so it is race-safe.
- `'[)'` half-open ranges let back-to-back slots (10:00–10:15 and 10:15–10:30) coexist.
- `WHERE status <> 'CANCELLED'` frees the slot as soon as an appointment is cancelled.
- `btree_gist` is a trusted extension, so the DB owner can create it (and the in-cluster postgres user is superuser anyway).

The API catches `IntegrityError` whose `orig.sqlstate == "23P01"` (exclusion_violation) and returns **409** `{"detail": "Dr X already has an appointment overlapping 10:15–10:30", "code": "SLOT_TAKEN"}`. It also increments `waitingroom_booking_conflicts_total`.

The client sends `starts_at` and an optional `duration_minutes` (defaults to `doctor.slot_minutes`); the server computes `ends_at`. Further validations, each returning 422 with a clear message: the doctor is active, the slot lies inside the doctor's working hours in the clinic timezone, and `starts_at` is not in the past (creation only).

### Status flow (`app/status_flow.py`, a single source of truth)

```text
BOOKED ──► CHECKED_IN ──► IN_CONSULTATION ──► DONE
   │            │
   └──► CANCELLED ◄─┘          (DONE and CANCELLED are terminal)
```
| to | sets | allowed from |
|---|---|---|
| CHECKED_IN | checked_in_at | BOOKED |
| IN_CONSULTATION | consultation_started_at | CHECKED_IN |
| DONE | completed_at | IN_CONSULTATION |
| CANCELLED | cancelled_at, cancel_reason | BOOKED, CHECKED_IN |

An illegal transition returns 409 `code: INVALID_TRANSITION` with the allowed targets in the body. Every successful transition increments `waitingroom_appointment_transitions_total{to_status}`.

`CLINIC_TZ` (env, default `Australia/Sydney`; change it if the clinic is elsewhere) defines "today" and working hours. Timestamps are stored in UTC.

---

## 5. API design

Base path `/api`. JSON in and out, Pydantic v2 schemas, `response_model` everywhere, OpenAPI at `/docs`.

| # | Method & path | Purpose | Codes |
|---|---|---|---|
| 1 | `GET /api/doctors?active=true` | list doctors | 200 |
| 2 | `POST /api/doctors` | create doctor | 201, 422 |
| 3 | `PUT /api/doctors/{id}` | full update (incl. `is_active`) | 200, 404, 422 |
| 4 | `GET /api/doctors/{id}/availability?date=YYYY-MM-DD` | free slots for the day (working hours minus non-cancelled appointments) | 200, 404 |
| 5 | `GET /api/patients?q=` | search by name or phone (ILIKE), limit 50 | 200 |
| 6 | `GET /api/patients/{id}` | patient + upcoming appointments | 200, 404 |
| 7 | `POST /api/patients` | register patient | 201, 409 duplicate phone, 422 |
| 8 | `PUT /api/patients/{id}` | update patient | 200, 404, 409 |
| 9 | `DELETE /api/patients/{id}` | delete patient with no appointments | 204, 404, 409 `HAS_APPOINTMENTS` |
| 10 | `GET /api/appointments?date=&doctor_id=&status=` | day list (board + schedule), ordered by starts_at | 200 |
| 11 | `GET /api/appointments/{id}` | detail incl. patient and doctor names | 200, 404 |
| 12 | `POST /api/appointments` | book | 201, **409 SLOT_TAKEN**, 422 |
| 13 | `PUT /api/appointments/{id}` | reschedule / change doctor / reason (only while BOOKED) | 200, 404, 409, 422 |
| 14 | `POST /api/appointments/{id}/status` `{status, cancel_reason?}` | status transition | 200, 404, **409 INVALID_TRANSITION** |
| 15 | `DELETE /api/appointments/{id}` | remove a **CANCELLED** record (data cleanup) | 204, 404, 409 |
| 16 | `GET /api/dashboard/today?doctor_id=` | counts per status, avg wait (checked_in→consultation) minutes, next 5 up | 200 |

Ops endpoints (root, **not** routed by Ingress):
- `GET /health`: liveness, no DB → `{"status":"ok"}`.
- `GET /ready`: runs `SELECT 1` and checks that the alembic version equals head. Returns 200 `{"status":"ready"}` or **503** on any failure, never 500.
- `GET /metrics`: Prometheus format via `prometheus-fastapi-instrumentator`, with `/metrics`, `/health` and `/ready` excluded from instrumentation, plus custom counters.
- `GET /`: `{"service":"waiting-room-api","version":<GIT_SHA env>}`.

Error shape everywhere: `{"detail": str, "code": str}`, via a small `AppError(HTTPException)` helper.

---

## 6. UI screens (deliberately unlike TaskBoard)

TaskBoard is a dark sidebar, task table and fake activity feed. Waiting Room is a **light clinical theme** (teal/white tokens), a **top navigation bar** (a bottom tab bar under 640px), and a **queue board** as its centrepiece.

1. **Waiting Room board** (`/`, default). Doctor filter chips, a KPI strip (Booked / Waiting / In consultation / Done / Avg wait) and **four columns**: *Booked → Waiting (checked in) → With doctor → Done*. Each card shows time, patient, doctor and room, plus a **live "waiting 12 min" timer** for checked-in patients. A primary action button advances the card ("Check in", "Call in", "Complete"); a kebab menu offers "Cancel…". The board polls every 15 s and shows "updated hh:mm:ss". Columns stack vertically on mobile.
2. **Schedule** (`/schedule`). A date picker and a per-doctor day timeline showing booked blocks and free slots from `/availability`. Clicking a free slot opens the **Book appointment** dialog (patient search-select, doctor, time, duration, reason). A 409 is shown **inline** on the dialog as "Slot just taken — pick another", and the slots refresh.
3. **Patients** (`/patients`). Search box, responsive table/cards, add/edit drawer and delete. A 409 on delete shows "has appointments".
4. **Doctors** (`/doctors`). Cards with specialty, room, hours and slot length; add/edit; an active toggle instead of delete.

On every page: loading skeletons, an `ErrorBanner` when the backend is unreachable, empty states, and a footer showing **build SHA** (`VITE_APP_VERSION` build arg). That footer makes "the deployment updated" visible in the M10 demo.

The frontend calls only relative `/api/...`. In dev, Vite proxies `/api` → `http://localhost:8000`.

---

## 7. Phased build order

Every phase lists: files, key decisions, pitfalls (including **reference mistakes not to copy**), verification, and a suggested commit message.

### Phase 0: Guardrails and cost safety (step zero, before any code)

**Do:**
1. **AWS Budget.** The user runs this, or the agent runs it via MCP **with approval**. Create a monthly COST budget `waiting-room-guard` of **$15**:
   - Set `CostTypes.IncludeCredit=false` and `IncludeRefund=false`. Otherwise the $100 credits make spend show as $0 and alerts never fire.
   - Notifications: ACTUAL > 20% ($3), ACTUAL > 50%, ACTUAL > 100%, FORECASTED > 100%, all emailed to the user's address.
   - Show the user the exact `CreateBudget` payload first.
2. Note: on the Free plan, credits are a hard ceiling. If they are exhausted, the plan ends, the account must be upgraded, and resources may be lost. Check remaining credits any time with `freetier:GetAccountPlanState`.
3. Update `CLAUDE.md`: add an "Agent hard rules" section (§1) and save `help_level: HIGH`.
4. `.claude/settings.json`: `permissions.deny` for `Bash(terraform apply*)`, `Bash(terraform destroy*)`, `Bash(eksctl*)`; `permissions.ask` for `Bash(helm uninstall*)`, `Bash(kubectl delete*)`.
5. Root `.gitignore`: `reference/`, `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `node_modules/`, `dist/`, `.terraform/`, `*.tfstate*`, `tfplan`, `terraform.tfvars`, `*.kubeconfig`, `.DS_Store`, `.idea/`, `.vscode/`. **Do not** ignore `.terraform.lock.hcl`; the reference ignores it, which is wrong.
6. Copy this plan to `PLAN.md`. Add a pre-commit config with `gitleaks`.

**Verify:** `aws budgets describe-budgets --account-id 802823597889 --profile agent-toolkit` (or the MCP equivalent) shows `waiting-room-guard`. `git check-ignore reference .env` prints both paths. `git status` shows no `reference/` files.
**Commit:** `chore: add cost guardrails, agent rules and gitignore`

### Phase 1: Backend skeleton, config, models, migrations

**Files:** `backend/{requirements*.txt,pyproject.toml,alembic.ini,alembic/env.py,alembic/versions/0001_*,0002_*,app/{config,db,models,main}.py}`, `docker-compose.yml` (only the `db` service for now), `.env.example`.

**Decisions:**
- Python 3.12; FastAPI, SQLAlchemy 2.x (typed `Mapped`), psycopg 3, Alembic, pydantic-settings, prometheus-fastapi-instrumentator. Exact pins.
- `config.py` reads `DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD` (optionally a full `DATABASE_URL` override) and builds the URL with `sqlalchemy.URL.create`, so special characters in passwords are safe and the password never sits inside a plain-text URL env var.
- `main.py` uses `create_app()` with a **`lifespan`** context manager. No `@app.on_event`, no `create_all`. CORS middleware is added **only** if `CORS_ORIGINS` is set (comma-separated allowlist). There is no wildcard.
- `alembic/env.py`: on Postgres, acquire `SELECT pg_advisory_lock(727274)` before `run_migrations` and release it after, so multiple init containers serialize. Set `compare_type=True`.
- Migrations are hand-written, reviewed and reversible. `0002` creates the extension, table, CHECKs and EXCLUDE constraint; its downgrade drops them.
- Compose `db`: `postgres:17-alpine` (tag + digest). Password comes from `.env` (`POSTGRES_PASSWORD`; `.env.example` holds a placeholder). Healthcheck uses `pg_isready`. The port is published on `127.0.0.1:5432:5432` only, so local pytest can reach it and nothing else can. Mount `./backend/scripts/init-test-db.sql` into `/docker-entrypoint-initdb.d/` to create the `waitingroom_test` database.

**Reference mistakes not to copy:** CORS `*`; `on_event("startup")`; `create_all` alongside Alembic (it hides missing migrations and causes drift); the DB password baked into a default URL in `config.py`; pytest/httpx in runtime requirements; `"latest"`-style unpinned deps.

**Verify:**
```bash
docker compose up -d db
cd backend && uv venv && uv pip install -r requirements-dev.txt
alembic upgrade head && alembic downgrade base && alembic upgrade head
docker compose exec db psql -U waitingroom -d waitingroom -c '\d appointments' | grep appointments_no_doctor_overlap
```
**Commits:** `feat(backend): add settings, db session and SQLAlchemy models`, `feat(db): add alembic migrations with no-overlap exclusion constraint`

### Phase 2: API and domain logic

**Files:** `app/{schemas,status_flow,metrics,seed}.py`, `app/routers/*.py`, `scripts/smoke-api.sh`.

**Decisions:** Thin routers with logic in small functions (`book_appointment`, `transition`, `availability_for`). Map 23P01 → 409 SLOT_TAKEN and 23505 on phone → 409 DUPLICATE_PHONE. `/ready` returns 503 on exception. Instrumentator: `Instrumentator(excluded_handlers=["/metrics","/health","/ready"]).instrument(app).expose(app, include_in_schema=False)`. Custom counters live in `metrics.py`. `seed.py` is idempotent: it exits if any doctor exists, and creates 4 doctors, 15 fake patients and today's appointments spread across all statuses.

**Pitfalls:** Use `select(...).where(...)` 2.0 style. Use `db.get` for single records. Always `db.rollback()` after an IntegrityError before raising. Use timezone-aware datetimes only. The reference's `/ready` lets exceptions turn into a 500; don't copy that.

**Verify:** `uvicorn app.main:app --port 8000 &` then `python -m app.seed && ./scripts/smoke-api.sh`. The script must hit every endpoint and assert codes, including that booking the same slot twice gives 409. Also `curl -s localhost:8000/metrics | grep waitingroom_`.
**Commits:** `feat(api): doctors and patients CRUD endpoints`, `feat(api): appointment booking with 409 on overlapping slots`, `feat(api): appointment status flow, dashboard and custom metrics`

### Phase 3: Tests (§8 details)

**Files:** `backend/pytest.ini`, `backend/tests/conftest.py`, `tests/test_*.py`.
**Verify:** `docker compose up -d db && cd backend && TEST_DATABASE_URL=postgresql+psycopg://waitingroom:<pw>@127.0.0.1:5432/waitingroom_test pytest -v` → all pass, coverage ≥ 85%. Also `ruff check . && ruff format --check .`
**Commit:** `test: add pytest suite against isolated postgres test database`

### Phase 4: Frontend

**Files:** everything under `frontend/` (§3, §6).
**Decisions:**
- React + Vite (current majors) and `react-router-dom`. No UI framework; plain CSS with design tokens. `api/client.js` wraps fetch, parses `{detail, code}`, and throws a typed error.
- `usePolling(fn, 15000)` pauses when the tab is hidden.
- Commit `package-lock.json`. CI and Docker use `npm ci`. ESLint flat config with react-hooks rules.
- `vite.config.js` proxies `/api` → `http://localhost:8000`. The reference proxies to 8080, which is wrong.

**Pitfalls:** The reference packs the entire UI into one minified file with a hard-coded user name and a fake activity feed. Build real components and show only real data.
**Verify:** `cd frontend && npm ci && npm run lint && npm run build`, then `npm run dev` with the backend running. Book an appointment, try the same slot again (the inline 409 appears), walk it through the board to DONE, and check at 375px width in devtools.
**Commits:** `feat(frontend): app shell, routing and api client`, `feat(frontend): waiting room queue board with live wait timers`, `feat(frontend): schedule view and booking dialog`, `feat(frontend): patients and doctors management`

### Phase 5: Docker and Compose

**backend/Dockerfile** (multi-stage):
- builder: `python:3.12-slim@sha256:…`, `pip install --no-cache-dir --prefix=/install -r requirements.txt`
- runtime: same base. Copy `/install`, `app/`, `alembic/`, `alembic.ini`. `useradd -u 10001 -r app`, `USER 10001`, `EXPOSE 8000`. `ARG GIT_SHA` → `ENV GIT_SHA`.
- `HEALTHCHECK` uses Python urllib, because slim has no curl.
- `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=*"]`. **No migrations in CMD.**

**frontend/Dockerfile** (multi-stage, rubric M4):
- build: `node:22-alpine@sha256:…`, `npm ci`, `ARG VITE_APP_VERSION`, `npm run build`
- runtime: **`nginxinc/nginx-unprivileged:<stable>-alpine@sha256:…`**, which runs as uid 101 and listens on **8080**. Copy `dist/` and `nginx/default.conf.template`.
- The template uses `${API_UPSTREAM}` (default `http://backend:8000`) for `location /api/`, handled by the image's envsubst templating. Add `try_files $uri /index.html`, gzip, cache headers for `/assets/`, and `server_tokens off`.

**docker-compose.yml:**
- `db` (healthcheck)
- `migrate` (backend image, `command: alembic upgrade head`, depends_on db `service_healthy`)
- `backend` (depends_on migrate `service_completed_successfully`, ports `8000:8000`, healthcheck)
- `frontend` (ports `3000:8080`, env `API_UPSTREAM=http://backend:8000`)
- All secrets come from `.env` via `${POSTGRES_PASSWORD:?set in .env}`. Named volume `db-data`.

**Reference mistakes not to copy:**
- `nginx:alpine` runs its master process as root, which **loses M4's non-root points**.
- Migrations in the container CMD race when there are several replicas.
- Hard-coded `taskboard:taskboard` credentials in compose.
- Postgres published on 0.0.0.0.
- `depends_on` with no health conditions.
- `npm install` without a lockfile.

**Verify:**
```bash
cp .env.example .env   # set a real password
docker compose up --build -d && docker compose ps          # all healthy, migrate exited 0
curl -fs localhost:3000/api/dashboard/today && curl -fs localhost:8000/health
docker compose exec backend id -u    # 10001
docker compose exec frontend id -u   # 101
docker compose exec backend python -m app.seed   # then open http://localhost:3000
```
**Commit:** `build: multi-stage non-root Dockerfiles and compose stack with migrate job`

### Phase 6: CI/CD (§9 details), without deploy at first

**Verify:** push to `main` and run `gh run watch`. All jobs are green. `gh api /users/mrind3v/packages/container/waiting-room-backend/versions | jq '.[0].metadata.container.tags'` shows the 40-char SHA. Then make **both GHCR packages public** (Package settings → Change visibility), so kind/EKS can pull without an imagePullSecret. Also do a deliberate red run: break one test on a branch PR, confirm the pipeline fails and nothing is pushed, then revert. Screenshot it; this proves "fails the build on test failure".
**Commit:** `ci: add test, build, trivy scan and ghcr push pipeline`

### Phase 7: Helm chart and local kind cluster

**Chart decisions:**
- `_helpers.tpl`: `waiting-room.fullname`, standard `app.kubernetes.io/{name,instance,component,version}` labels, and release-scoped `selectorLabels`. Service names and Ingress backends **both** use the helpers, so they can't drift apart.
- `values.yaml`:
  - `image.registry: ghcr.io/mrind3v`, `backend.image.tag` / `frontend.image.tag` **required** (`{{ required }}`, no `latest` default)
  - `backend.replicas: 2`, `frontend.replicas: 2`
  - `hpa.backend {enabled, min 2, max 5, cpu 60}`, `hpa.frontend {min 2, max 4, cpu 70}`
  - `postgres.existingSecret: waiting-room-db` (key `password`), `postgres.storageClass: ""`, `postgres.size: 1Gi`
  - `ingress {enabled, className: traefik, host: ""}`
  - `monitoring.serviceMonitor.enabled`, `monitoring.dashboard.enabled`
  - `clinicTz`
- Deployments render `replicas:` **only when the HPA is disabled**, so `helm upgrade` doesn't fight the HPA.
- Pod `securityContext`: `runAsNonRoot`, `seccompProfile: RuntimeDefault`. Containers: `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `readOnlyRootFilesystem: true` with `emptyDir` mounts at `/tmp` (both apps) and `/var/cache/nginx` + `/tmp` (frontend).
- Resources: backend requests 100m/192Mi, limits 500m/384Mi. Frontend 25m/32Mi, limits 200m/96Mi. Requests are what make the HPA work.
- Backend: `initContainers: migrate` (same image, `alembic upgrade head`, retries until the DB is reachable). Liveness `/health`, readiness `/ready`, startupProbe `/health`. Env `DB_*` from values plus `DB_PASSWORD` from `secretKeyRef`, and `GIT_SHA` = image tag.
- Frontend env `API_UPSTREAM=http://{{fullname}}-backend:8000`.
- Postgres: **StatefulSet** with `volumeClaimTemplates`, `PGDATA=/var/lib/postgresql/data/pgdata` (an EBS volume's `lost+found` breaks initdb otherwise), `runAsUser/fsGroup: 70`, `pg_isready` probes, and `persistentVolumeClaimRetentionPolicy: {whenDeleted: Delete, whenScaled: Delete}`. Headless + ClusterIP service.
- Ingress: `ingressClassName: traefik`; `/api` Prefix → backend:8000; `/` Prefix → frontend:8080. The `host` rule is rendered only if set.
- ServiceMonitor and dashboard ConfigMap are wrapped in `{{- if .Capabilities.APIVersions.Has "monitoring.coreos.com/v1" }}`. The ServiceMonitor selects the backend Service port named `http`, path `/metrics`, interval 15s. The ConfigMap has label `grafana_dashboard: "1"` and is loaded with `.Files.Get "dashboards/waiting-room.json"`.
- `NOTES.txt` prints the URL and port-forward commands.
- `values-kind.yaml`: `ingress.host: waiting-room.localtest.me`, `image.tag` overridable, `postgres.storageClass: standard`.
- `values-eks.yaml`: `ingress.host: ""` (the NLB hostname matches any host), `postgres.storageClass: gp3`.

**kind and bootstrap:**
- `k8s/kind-config.yaml`: 1 control-plane + 1 worker. `extraPortMappings` containerPort 30080 → hostPort 8080. Use the kind node image matching K8s **1.35**, for parity with EKS.
- `scripts/cluster-bootstrap.sh <kind|eks>`, idempotent, `set -euo pipefail`:
  1. `kubectl apply -f k8s/namespace.yaml`; on eks also `storageclass-gp3.yaml` and `rbac-ci-deployer.yaml`.
  2. Create `waiting-room-db` with `openssl rand -hex 24` **only if absent** (never echoed). Create `grafana-admin` in `monitoring` the same way.
  3. `helm upgrade --install` pinned versions of: metrics-server (`--kubelet-insecure-tls` on kind only), traefik (values-kind: NodePort 30080; values-eks: LoadBalancer + NLB annotation, 1 replica), and kube-prometheus-stack (monitoring values, release name `kps`).

**Reference mistakes not to copy:**
- The Ingress points at a nonexistent service `taskboard-backend:8080` (the real one is `<release>-taskboard-backend:8000`), so `/api` is broken.
- Hard-coded, non-release-scoped names and selectors.
- DB password in `values.yaml`, and `DATABASE_URL` with the password in plain env.
- Postgres as a Deployment with no PGDATA subdir.
- `tag: latest` and `YOUR_ORG` placeholders.
- `replicaCount` shared between apps and fighting the HPA.
- A ServiceMonitor that hard-fails without the CRD.
- No securityContext.
- The nginx proxy hard-coded to `backend:8000`.

**Verify:**
```bash
helm lint helm/waiting-room -f helm/waiting-room/values-kind.yaml --set backend.image.tag=x --set frontend.image.tag=x
helm template t helm/waiting-room -f helm/waiting-room/values-kind.yaml --set backend.image.tag=x,frontend.image.tag=x | kubeconform -strict -ignore-missing-schemas -summary
kind create cluster --name waiting-room --config k8s/kind-config.yaml
./scripts/cluster-bootstrap.sh kind
helm upgrade --install waiting-room helm/waiting-room -n waiting-room -f helm/waiting-room/values-kind.yaml \
  --set backend.image.tag=<sha> --set frontend.image.tag=<sha> --wait --timeout 10m
kubectl get pods,svc,ingress,hpa -n waiting-room      # ≥2 backend, ≥2 frontend Running; ClusterIP svcs
curl -fs http://waiting-room.localtest.me:8080/api/dashboard/today && open http://waiting-room.localtest.me:8080
kubectl -n waiting-room exec deploy/waiting-room-backend -- python -m app.seed
```
Images come from GHCR (Phase 6 SHA). Offline alternative: `docker build` + `kind load docker-image`.
**Commits:** `feat(helm): waiting-room chart with statefulset postgres, ingress and hpa`, `chore(k8s): kind config and idempotent cluster bootstrap script`

### Phase 8: Monitoring and HPA on kind

**`monitoring/kube-prometheus-stack-values.yaml`:**
- `alertmanager.enabled: false`
- Prometheus: `serviceMonitorSelectorNilUsesHelmValues: false`, `serviceMonitorNamespaceSelector: {}`, `retention: 12h`, **no storageSpec** (emptyDir, so no PVC is left orphaned), resources 200m/600Mi, limit 1Gi
- Grafana: `admin.existingSecret: grafana-admin`, `persistence.enabled: false`, `sidecar.dashboards.enabled: true`, `searchNamespace: ALL`
- Disable scraping of components EKS hides (`kubeEtcd`, `kubeControllerManager`, `kubeScheduler`, `kubeProxy`), so Targets show no false DOWN entries.
- The reference values leave Grafana on its default admin password and keep alertmanager and persistence on; don't copy that.

**`helm/waiting-room/dashboards/waiting-room.json`** panels: request rate by handler (`sum by (handler)(rate(http_requests_total{namespace="waiting-room"}[1m]))`), p95 latency (`histogram_quantile(0.95, sum by (le,handler)(rate(http_request_duration_seconds_bucket[5m])))`), 5xx ratio, appointment transitions by status, booking conflicts (409s), backend replica count (`kube_deployment_status_replicas`), and backend pod CPU vs request.

**`scripts/load-test.sh`:** applies a `Job` running `fortio/fortio:<pinned>` with `load -c 20 -qps 0 -t 4m http://waiting-room-backend.waiting-room:8000/api/appointments?date=<today>`. That endpoint does real DB work. Then `kubectl get hpa -w`. The reference's script hits `/api/health`, which doesn't exist, and runs sequential curls that generate no CPU load.

**Verify:**
- `kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090` → Targets page shows `serviceMonitor/waiting-room/...` **UP**.
- `kubectl -n monitoring port-forward svc/kps-grafana 3001:80` → the "Waiting Room" dashboard is populated.
- `./scripts/load-test.sh` → `kubectl get hpa -n waiting-room` shows replicas rising above 2, then scaling down after about 5 minutes.
- `kubectl -n waiting-room port-forward svc/waiting-room-backend 8000` then `curl localhost:8000/metrics | head -40`.

**Commit:** `feat(observability): servicemonitor, grafana dashboard and hpa load test`

### Phase 9: Troubleshooting lab

Own manifests in `troubleshooting/`:
- `broken-image.yaml`: tag `does-not-exist` → ImagePullBackOff.
- `broken-service.yaml`: selector `app.kubernetes.io/component: api` vs actual `backend` → empty Endpoints.
- `broken-readiness.yaml`: backend with `DB_HOST=postgres-typo` → Running but 0/1 Ready, `/ready` returns 503.

`troubleshooting/README.md` covers each one: symptom → commands (`describe`, `get events --sort-by=.lastTimestamp`, `get endpointslices`, `logs`) → root cause → fix → cleanup.
**Verify:** apply each on kind, reproduce the symptom, apply the fix, then `kubectl delete -f troubleshooting/`.
**Commit:** `docs: add kubernetes troubleshooting lab with three failure scenarios`

### Phase 10: Terraform (author + `plan` only; **no apply**)

**Files:** `terraform/{versions,providers,variables,main,iam_ci,outputs}.tf`, `terraform.tfvars.example`, `README.md`, committed `.terraform.lock.hcl`.

**Decisions:**
- `versions.tf`: `required_version >= 1.9`, `hashicorp/aws ~> 6.x` (exact minor pinned in the lock file). Modules pinned exactly: `terraform-aws-modules/vpc/aws` (current 6.x) and `terraform-aws-modules/eks/aws` (**current 21.x**; check input names against v21 docs).
- `providers.tf`: `region = var.region` (default `ap-southeast-2`). `default_tags { Project = "waiting-room", Owner = "mrind3v", ManagedBy = "terraform", Ephemeral = "true" }`. The profile comes from env `AWS_PROFILE`, not hard-coded.
- **VPC:** `cidr 10.30.0.0/16`, `azs = ["ap-southeast-2a","ap-southeast-2b"]`, `public_subnets = ["10.30.0.0/20","10.30.16.0/20"]`, `private_subnets = []`, `enable_nat_gateway = false`, `map_public_ip_on_launch = true`, `public_subnet_tags = {"kubernetes.io/role/elb" = 1}`.
- **EKS (v21 names):**
  - `name = "waiting-room-eks"`, `kubernetes_version = "1.35"`
  - `endpoint_public_access = true`. Trade-off: GitHub runners need it; auth is still IAM-gated.
  - `enable_irsa = false` (**creating the OIDC provider is denied by the Free-plan SCP**)
  - `create_kms_key = false`, `encryption_config = null` (avoids $1/mo and a 7–30 day pending-deletion leftover)
  - `enabled_log_types = []`, `create_cloudwatch_log_group = false` (no orphaned log group)
  - `enable_cluster_creator_admin_permissions = true`
  - `addons`: `vpc-cni` (before_compute), `eks-pod-identity-agent` (before_compute), `kube-proxy`, `coredns`, and `aws-ebs-csi-driver` with a `pod_identity_association` to a role from `terraform-aws-modules/eks-pod-identity/aws` (`attach_aws_ebs_csi_policy = true`)
  - `eks_managed_node_groups.default`: `ami_type = "AL2023_x86_64_STANDARD"`, `instance_types = ["m7i-flex.large"]`, `capacity_type = "ON_DEMAND"`, `min 1 / desired 1 / max 2`, `disk_size 20`, `subnet_ids = module.vpc.public_subnets`
  - `access_entries.ci = { principal_arn = aws_iam_user.ci.arn, kubernetes_groups = ["waiting-room-deployers"] }` (no cluster-wide policy; the Role in `k8s/rbac-ci-deployer.yaml` grants namespace-only rights)
- `iam_ci.tf`: `aws_iam_user.ci` (`waiting-room-ci`) with an inline policy allowing `eks:DescribeCluster` on the cluster ARN only, plus `aws_iam_access_key.ci`. Outputs `ci_access_key_id` and `ci_secret_access_key` are `sensitive = true`. State is local and git-ignored; the keys die at destroy.
- `outputs.tf`: cluster_name, region, vpc_id, public_subnet_ids, `kubeconfig_command = "aws eks update-kubeconfig --region ap-southeast-2 --name waiting-room-eks --profile agent-toolkit"`.
- `terraform.tfvars.example`: `region`, `cluster_name`, `kubernetes_version`, `node_instance_type`. No credentials.
- `k8s/rbac-ci-deployer.yaml`: Role in `waiting-room` allowing get/list/watch/create/update/patch/delete on:
  - deployments, statefulsets, replicasets
  - services, configmaps, secrets (Helm stores releases in secrets), pods, pods/log, PVCs, events (read)
  - ingresses, HPAs, jobs
  - `monitoring.coreos.com/servicemonitors`
  
  Bound to the group `waiting-room-deployers`.

**Reference mistakes not to copy:**
- NAT gateway and private subnets.
- EKS 1.31 (extended-support pricing).
- 2 × t3.medium (not allowed on the Free plan, and double the nodes).
- AZs for a different Region.
- No tfvars example.
- Ignored lock file.
- Single-line HCL.
- Implicit KMS key and log group.
- No EBS CSI driver: on EKS ≥1.23 PVCs stay **Pending** without it.
- No default StorageClass.
- No tags.

**Verify (no AWS writes):**
```bash
cd terraform && terraform fmt -check -recursive && terraform init && terraform validate
AWS_PROFILE=agent-toolkit terraform plan -out=tfplan   # read-only API calls; screenshot for M7
terraform show -no-color tfplan | grep -E '^Plan:'      # expect roughly 40–60 to add, 0 change, 0 destroy
```
The plan must contain **no** `aws_nat_gateway`, `aws_eip`, `aws_kms_key`, `aws_cloudwatch_log_group` or `aws_iam_openid_connect_provider`. Grep for them and fail if found. Delete `tfplan` after the screenshot; it's git-ignored.
**Commit:** `feat(infra): terraform for minimal-cost VPC and EKS in ap-southeast-2`

### Phase 11: Documentation

- `README.md`: what Waiting Room does (front desk + queue), screenshots, architecture diagram, local quickstart (compose, kind), API table, status-flow diagram, double-booking explanation, CI/CD stages, security notes (non-root, Trivy, no secrets, SCP trade-offs), cost section, and links to the docs.
- `docs/SECURITY-SCAN.md`: 2–3 sentences filled in after a real CI run (see §9), plus how to read a Trivy row.
- `docs/RUNBOOK-AWS.md`: §10, copied verbatim.
- `docs/SUBMISSION.md`: §12.
- `docs/VERSIONS.md`: every pinned version.

**Commit:** `docs: readme, architecture, aws runbook and submission checklist`

### Phase 12: AWS window (user-approved; §10)

### Phase 13: Final submission (§12)

---

## 8. Test plan (pytest, real Postgres test DB)

**Why a real Postgres and not SQLite (as the reference uses):** the exclusion constraint, `tstzrange` and `btree_gist` only exist in Postgres. Testing on SQLite would silently skip the most important rule. The rubric requires "a test database or mock, not the production database", which this meets.

**`pytest.ini`:**
```ini
[pytest]
pythonpath = .
testpaths = tests
addopts = -ra --strict-markers --cov=app --cov-report=term-missing --cov-fail-under=85
markers = concurrency: concurrent booking race test
```

**`tests/conftest.py`:**
- Reads `TEST_DATABASE_URL`. If the database name does not end in `_test`, call `pytest.exit` (a guard against the dev/prod DB).
- Sets `DATABASE_URL` before importing the app.
- Session fixture: `alembic.command.upgrade(cfg, "head")`, so tests also exercise migrations. At teardown, `downgrade(cfg, "base")`.
- Autouse fixture: `TRUNCATE appointments, patients, doctors RESTART IDENTITY CASCADE` after each test.
- A `client` fixture (`TestClient(create_app())`) and factories `make_doctor()`, `make_patient()`, `book(...)`.
- Freeze "now" through a `clock` dependency (`app.deps.now`) overridden in tests, so working-hours and past-time rules are deterministic.

**Test cases** (21 tests across 12+ endpoints; rubric needs ≥5 across ≥3):

| File | Test | Endpoint(s) |
|---|---|---|
| test_ops | `test_health_ok` | GET /health |
| | `test_ready_reports_ready_when_db_up` | GET /ready |
| | `test_metrics_exposes_prometheus_and_custom_counters` | GET /metrics |
| test_doctors | `test_create_and_list_doctors` | POST, GET /api/doctors |
| | `test_update_doctor_put_and_404` | PUT /api/doctors/{id} |
| | `test_availability_excludes_booked_and_includes_cancelled_slots` | GET …/availability |
| test_patients | `test_register_patient_and_duplicate_phone_409` | POST /api/patients |
| | `test_update_patient_put` | PUT /api/patients/{id} |
| | `test_delete_patient_204_and_409_when_has_appointments` | DELETE /api/patients/{id} |
| test_appointments_booking | `test_book_appointment_computes_ends_at` | POST /api/appointments |
| | **`test_same_slot_double_booking_409`** | POST |
| | **`test_partial_overlap_409`** (10:00+30 vs 10:15+15) | POST |
| | **`test_back_to_back_slots_allowed`** (10:00–10:15, 10:15–10:30) | POST |
| | **`test_same_time_different_doctor_allowed`** | POST |
| | **`test_cancelled_appointment_frees_slot`** | POST /status, POST |
| | **`test_reschedule_into_overlap_409_and_only_when_booked`** | PUT /api/appointments/{id} |
| | `test_outside_working_hours_or_inactive_doctor_422` | POST |
| | **`test_concurrent_booking_only_one_wins`** (`@pytest.mark.concurrency`: 2 threads, 2 sessions, same slot → exactly one 201, one 409) | POST |
| test_appointments_status | `test_full_status_flow_sets_timestamps` | POST /status |
| | `test_invalid_transition_409` (BOOKED→DONE, DONE→CANCELLED) | POST /status |
| test_dashboard | `test_today_counts_and_avg_wait` | GET /api/dashboard/today |

**Local:** compose `db` provides the `waitingroom_test` DB (init SQL). **CI:** a `services: postgres` container with `POSTGRES_DB=waitingroom_test`.

---

## 9. CI/CD design (`.github/workflows/ci-cd.yml`)

```yaml
on: { push: { branches: [main] }, pull_request: { branches: [main] }, workflow_dispatch: {} }
permissions: { contents: read }
concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
env: { REGISTRY: ghcr.io, IMAGE_PREFIX: ghcr.io/mrind3v/waiting-room }   # lowercase literal
```

| Job | Needs | Steps |
|---|---|---|
| `backend-test` | — | services: postgres (`waitingroom_test`, health-cmd pg_isready). setup-python 3.12 (pip cache) → `pip install -r requirements-dev.txt` → `ruff check` + `ruff format --check` → `pytest -v --junitxml=report.xml` (non-zero exit **fails the build**) → upload junit artifact |
| `frontend-build` | — | setup-node 22 (npm cache) → `npm ci` → `npm run lint` → `npm run build` → upload `dist` artifact |
| `infra-lint` | — | setup-terraform → `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`. azure/setup-helm → `helm lint`; `helm template … \| kubeconform -strict -ignore-missing-schemas` |
| `build-scan-push` | backend-test, frontend-build, infra-lint | matrix `component: [backend, frontend]`. `permissions: {contents: read, packages: write, security-events: write}`. setup-buildx → `docker/login-action` (GITHUB_TOKEN; **only on push to main**) → `docker/build-push-action` with `load: true`, tag `${IMAGE_PREFIX}-${component}:${{ github.sha }}`, build-args `GIT_SHA` / `VITE_APP_VERSION=${{ github.sha }}`, GHA cache → **Trivy** (`aquasecurity/trivy-action@<full SHA>`, `severity: HIGH,CRITICAL`, `ignore-unfixed: true`, `exit-code: '1'`, `format: table`) → second Trivy run with `format: sarif`, `exit-code: 0` → `github/codeql-action/upload-sarif` (findings visible in the Security tab) → `docker push` **only if** `github.event_name == 'push'`. **No `latest` tag.** |
| `deploy` | build-scan-push | `if: github.event_name == 'push' && github.ref == 'refs/heads/main' && vars.DEPLOY_ENABLED == 'true'`. `environment: production`, `concurrency: deploy-eks`. `aws-actions/configure-aws-credentials` (secrets, `vars.AWS_REGION`) → `aws eks update-kubeconfig --name ${{ vars.EKS_CLUSTER_NAME }}` → `helm upgrade --install waiting-room helm/waiting-room -n waiting-room -f helm/waiting-room/values-eks.yaml --set backend.image.tag=$SHA --set frontend.image.tag=$SHA --wait --atomic --timeout 10m` → `kubectl rollout status` → smoke `curl -fs http://$LB/api/dashboard/today` where LB = the traefik svc hostname |

**All third-party actions are pinned by full commit SHA** with a `# vX.Y.Z` comment. Dependabot keeps them updated. Mutable tags have been hijacked in real supply-chain incidents, so pin even security tools.

**GitHub secrets and variables:**

| Name | Kind | When | Source |
|---|---|---|---|
| `GITHUB_TOKEN` | automatic | always | `packages: write` in build job |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | **secret** | AWS window only | `terraform output -raw ci_access_key_id \| gh secret set AWS_ACCESS_KEY_ID` (piped, never printed); **deleted at teardown** |
| `AWS_REGION` = `ap-southeast-2`, `EKS_CLUSTER_NAME` = `waiting-room-eks` | variable | set once | `gh variable set` |
| `DEPLOY_ENABLED` | variable | `true` only during the AWS window, else `false` | keeps `main` green while no cluster exists |

DB and Grafana passwords **never** go to GitHub; they're generated in-cluster by the bootstrap script.

**Trivy explanation (M6):** After the first real run, fill in `docs/SECURITY-SCAN.md`. Cover: what was scanned (OS packages of the Debian-slim/Alpine base layers and the Python/npm dependencies baked into each image), that the gate is HIGH/CRITICAL with a fix available, and the result. If the run is clean, explain what that means and its limits. If it found something, pick one CVE: name the package, explain the fix (bump the base image digest or dependency), and add a `.trivyignore` entry with a justification only for an unfixable false positive.

---

## 10. AWS window runbook (`docs/RUNBOOK-AWS.md`): apply → demo → teardown

Target: **one sitting of about 4–5 hours**. Rehearse everything on kind first. Pre-write the commands into a checklist and tick them off. **The agent asks for approval before every write step marked ⚠.**

**T-1 day:** check remaining credits (`freetier get-account-plan-state`), budget `waiting-room-guard` exists, the `main` pipeline is green, GHCR packages are public, and the kind rehearsal passed.

**Apply (about 25 min):**
1. `aws sts get-caller-identity --profile agent-toolkit` → account 802823597889.
2. `cd terraform && terraform init && terraform plan -out=tfplan`. Show the summary; confirm there is no NAT/KMS/log group/OIDC.
3. ⚠ **User approves**, then runs `terraform apply tfplan` (EKS takes about 12–15 min). Screenshot the end of apply.
4. Run `$(terraform output -raw kubeconfig_command)` and then `kubectl get nodes`: 1 node Ready.
5. ⚠ `./scripts/cluster-bootstrap.sh eks` (namespaces, gp3 SC, RBAC, secrets, metrics-server, traefik → NLB, kps). Wait for the NLB: `kubectl -n traefik get svc traefik -w` until EXTERNAL-IP is a hostname.
6. ⚠ Set GitHub CI creds: `terraform output -raw ci_access_key_id | gh secret set AWS_ACCESS_KEY_ID` (and the same for the secret key), then `gh variable set DEPLOY_ENABLED --body true`.

**Deploy and demo (about 2 h, all recorded):**
7. Trigger the first deploy: `gh workflow run ci-cd.yml --ref main` (or push a commit). Watch it go green.
8. `kubectl -n waiting-room exec deploy/waiting-room-backend -- python -m app.seed`
9. Screenshots (§12): AWS Console VPC + EKS in ap-southeast-2, `kubectl get pods/svc/ingress/hpa`, `helm list -A`, the app via `http://<nlb-hostname>/`, `/metrics` via port-forward, Prometheus Targets UP, Grafana dashboard, HPA during `./scripts/load-test.sh`.
10. **M10 demo (recorded):** change a visible string (e.g. the board subtitle), commit `feat(frontend): show clinic name on board header`, and push. Record the pipeline running test → build → Trivy → push → deploy, then refresh the browser to show the new text and the **new SHA in the footer**. Then `kubectl -n waiting-room get pods -o jsonpath='{..image}'` shows the new tag.
11. Troubleshooting demo: apply `troubleshooting/broken-service.yaml` on EKS, diagnose it, delete it.

**Pre-destroy cleanup (about 10 min; `scripts/pre-destroy.sh`, ⚠ approval):**
12. `gh variable set DEPLOY_ENABLED --body false`, then `gh secret delete AWS_ACCESS_KEY_ID` and `gh secret delete AWS_SECRET_ACCESS_KEY`.
13. `kubectl delete -f troubleshooting/ --ignore-not-found`
14. `helm uninstall waiting-room -n waiting-room --wait`, then `kubectl -n waiting-room delete pvc --all --wait`. The StatefulSet retention policy also does this; deleting explicitly is belt and braces.
15. `helm uninstall kps -n monitoring --wait`; `helm uninstall traefik -n traefik --wait` (**this deletes the NLB**); `helm uninstall metrics-server -n kube-system`.
16. Delete the namespaces `waiting-room`, `monitoring` and `traefik`, and wait.
17. Verify via MCP (read-only, region ap-southeast-2) that the following all return **empty** before continuing:
    - `elbv2:DescribeLoadBalancers` and `elb:DescribeLoadBalancers`
    - `ec2:DescribeVolumes` filtered by `tag:kubernetes.io/created-for/pvc/namespace`
    - `kubectl get pv`

    Leftover load balancers keep ENIs and security groups alive, so `terraform destroy` would hang on the VPC.

**Destroy (about 15 min):**
18. `terraform plan -destroy -out=destroy.tfplan`, show the summary, then ⚠ **user approves**, then `terraform apply destroy.tfplan` (equivalent to `terraform destroy`). Screenshot "Destroy complete! Resources: N destroyed."
19. Run `rm -f tfplan destroy.tfplan` and remove the cluster entry from `~/.kube/config` (`kubectl config delete-context …`).

**Post-destroy verification (`scripts/verify-teardown.sh`, read-only MCP script). All must be empty or default:**
- [ ] EKS `ListClusters` (ap-southeast-2) → `[]`
- [ ] EC2 `DescribeInstances` (state ≠ terminated) → none
- [ ] EC2 `DescribeVolumes` → none tagged `Project=waiting-room` or `kubernetes.io/*`
- [ ] ELBv2 + Classic `DescribeLoadBalancers` → none
- [ ] EC2 `DescribeAddresses` (Elastic IPs) → none
- [ ] EC2 `DescribeNatGateways` (state available) → none
- [ ] EC2 `DescribeVpcs` → only the default VPC (none tagged waiting-room)
- [ ] EC2 `DescribeNetworkInterfaces` with VPC filter → none
- [ ] EC2 `DescribeSecurityGroups` tagged `kubernetes.io/cluster/waiting-room-eks` → none
- [ ] IAM: user `waiting-room-ci` gone; roles with `waiting-room` prefix gone
- [ ] CloudWatch Logs `/aws/eks/waiting-room-eks/*` in **ap-southeast-2 and us-east-1** → none
- [ ] `terraform state list` → empty
- [ ] Next day: Billing → Cost Explorer daily cost back to about $0; credits remaining ≈ $100 − estimate

---

## 11. Cost estimate and cost-control checklist

Approximate ap-southeast-2 on-demand prices. **Before apply, confirm them with the Pricing API (`pricing:GetProducts`) via MCP.** Everything is paid from the $100 Free-plan credits.

| Item | Rate (approx) | 5 h window |
|---|---|---|
| EKS control plane (1.35, standard support) | $0.10/h | $0.50 |
| 1 × m7i-flex.large on-demand | ≈ $0.12/h | $0.60 |
| NLB (Traefik) + minimal LCU | ≈ $0.03/h | $0.15 |
| Public IPv4 (node + 2 NLB) | 3 × $0.005/h | $0.08 |
| EBS gp3 (20 GiB root + 1 GiB PVC) | ≈ $0.003/h | $0.02 |
| Data transfer / GHCR pulls (inbound free) | ~ | < $0.10 |
| **Total** | **≈ $0.26/h** | **≈ $1.50** (budget $5 with a retry) |

Forgetting teardown costs ≈ **$6/day** (≈ $190/month), which would burn all the credits in about 2 weeks. Hence the budget alerts and the post-destroy checklist.

**Cost controls:** budget alert at $3/$7.5/$15 actual + forecast (credits excluded) · Free plan kept (spend ceiling) · no NAT · no RDS · no private subnets · 1 on-demand node · K8s 1.35 (avoids the $0.60/h extended-support price) · no KMS key or CloudWatch logs · Prometheus/Grafana via port-forward (no extra LBs) · Prometheus on emptyDir · PVCs deleted before destroy · all resources tagged `Project=waiting-room` · `Ephemeral=true` · one window, pre-rehearsed on kind · the deploy job is gated by `DEPLOY_ENABLED` · agent cannot run apply/destroy (settings deny + rule).

---

## 12. Rubric → deliverable map and submission checklist

| Module / criterion | pts | Deliverable / evidence |
|---|---|---|
| **M1** `/health` responds | 2 | `app/routers/ops.py`; `docs/screenshots/m1-health.png` |
| ≥4 REST endpoints GET/POST/PUT/DELETE | 3 | 16 endpoints (§5); `/docs` screenshot `m1-swagger.png` |
| PG table via Alembic | 2 | `alembic/versions/0001,0002`; `m1-psql-tables.png` (`\dt` + `\d appointments`) |
| Frontend renders + calls API | 2 | `frontend/src`; `m1-board.png` with seeded data |
| Responsive, usable UI | 1 | `m1-mobile.png` (375px) + `m1-schedule-409.png` |
| **M2** pytest runs clean | 3 | `pytest -v` → `m2-pytest.png` |
| ≥5 tests, ≥3 endpoints | 4 | 21 tests / 12+ endpoints (§8) |
| test DB/mock, not prod | 2 | `conftest.py` `_test` guard + CI postgres service |
| pytest.ini / conftest | 1 | both present |
| **M3** public repo | 2 | github.com/mrind3v/waiting-room (public) |
| meaningful commits | 2 | ≥20 conventional commits (phase list); `m3-commits.png` (`git log --oneline`) |
| .gitignore entries | 1 | `.env`, `__pycache__`, `node_modules`, `.venv` present |
| **M4** backend Dockerfile builds | 2 | `backend/Dockerfile` |
| frontend multi-stage Node→Nginx | 3 | `frontend/Dockerfile` (node build → nginx-unprivileged) |
| non-root images | 2 | uid 10001 / 101; `m4-nonroot.png` (`id -u` in both) |
| `docker compose up --build` 3 services | 3 | `m4-compose-up.png` + `m4-localhost-3000.png` |
| **M5** workflow file | 1 | `.github/workflows/ci-cd.yml` |
| triggers on push to main | 1 | `on.push.branches: [main]` |
| pytest job fails build | 3 | `backend-test`; red PR run screenshot `m5-red-run.png` |
| frontend built | 2 | `frontend-build` |
| images for both | 3 | matrix build |
| pushed to GHCR | 3 | `m5-ghcr-backend.png`, `m5-ghcr-frontend.png` |
| SHA tags, not latest | 2 | tag `${{ github.sha }}`; visible in GHCR screenshot; Actions run URL in SUBMISSION.md |
| **M6** Trivy on both images | 3 | matrix Trivy step; `m6-trivy.png` |
| fail on HIGH/CRITICAL | 1 | `exit-code: '1'`, `severity: HIGH,CRITICAL` |
| explain CVE/clean | 1 | `docs/SECURITY-SCAN.md` |
| **M7** valid HCL | 2 | `terraform/*.tf`; CI `infra-lint` |
| init OK | 1 | `m7-init.png` |
| plan non-empty, no errors | 2 | `m7-plan.png` |
| VPC ≥2 public subnets | 3 | `m7-console-vpc.png` (ap-southeast-2) |
| EKS + node group | 4 | `m7-console-eks.png` + `kubectl get nodes` |
| destroy clean | 2 | `m7-destroy.png` + `verify-teardown` output |
| tfvars.example, no creds | 1 | `terraform/terraform.tfvars.example`; gitleaks clean |
| **M8** namespace.yaml | 1 | `k8s/namespace.yaml` |
| Helm chart structure | 3 | `helm/waiting-room/` |
| `helm upgrade --install` OK | 3 | CI deploy log + `m8-helm-list.png` |
| ≥2 replicas each | 2 | HPA min 2 for both; `m8-pods.png` |
| ClusterIP Services | 2 | `m8-svc.png` |
| Ingress `/`→fe, `/api`→be | 2 | `ingress.yaml`; `m8-ingress-browser.png` (NLB hostname) |
| all pods Running | 2 | `m8-pods.png` |
| **M9** `/metrics` format | 2 | `m9-metrics-curl.png` |
| Prometheus scraping | 3 | `m9-prom-targets-up.png` |
| Grafana accessible | 2 | `m9-grafana-login.png` |
| live panel | 3 | `m9-grafana-dashboard.png` (request rate, p95, HPA replicas during load) |
| **M10** README | 2 | root `README.md` |
| commit → pipeline → deploy demo | 3 | recorded video (§10 step 10); link in SUBMISSION.md |

**Submission checklist (`docs/SUBMISSION.md`):**
```text
[ ] Repo URL submitted (public)          [ ] ≥10 meaningful commits (git log screenshot)
[ ] docker compose up --build screenshot [ ] localhost:3000 screenshot
[ ] pytest -v all green screenshot       [ ] Alembic migration files present
[ ] Green Actions run URL                [ ] Red run (failing test) screenshot
[ ] GHCR packages with SHA tags          [ ] Trivy output screenshot + SECURITY-SCAN.md
[ ] terraform plan screenshot            [ ] Console VPC + EKS (ap-southeast-2) screenshots
[ ] terraform destroy screenshot         [ ] verify-teardown output (all empty)
[ ] kubectl get pods / svc / hpa / ingress  [ ] helm list
[ ] App via Ingress (NLB hostname)       [ ] /metrics curl
[ ] Prometheus Targets UP                [ ] Grafana dashboard populated
[ ] HPA scaling screenshot               [ ] Troubleshooting demo
[ ] Recorded walkthrough (commit→pipeline→deploy, new SHA in footer)
[ ] No secrets in history (gitleaks detect --log-opts=--all)  [ ] GitHub AWS secrets deleted
```

**Suggested commit sequence (≥20):** the per-phase commits listed above, plus small follow-ups such as `fix(frontend): stack board columns on narrow screens` and `chore(deps): pin base images by digest`. Never use "update", "fix" or "test" alone.

---

## 13. Reference issues: consolidated "do not copy" list

1. `CORSMiddleware(allow_origins=["*"])` → env allowlist, off by default (same-origin via proxy/Ingress).
2. `@app.on_event("startup")` (deprecated) → `lifespan`.
3. `Base.metadata.create_all` alongside Alembic → Alembic only.
4. Tests on a SQLite file (`test.db`), 3 tests, no conftest and no isolation → Postgres test DB, truncation, 21 tests.
5. pytest/httpx in production `requirements.txt` → split dev requirements.
6. `alembic upgrade head && uvicorn` in CMD → initContainer with advisory lock / compose migrate job.
7. Compose: plaintext creds, 0.0.0.0:5432, no healthchecks → `.env`, localhost-only, health-gated `depends_on`.
8. `package.json` all `"latest"`, no lockfile, `npm install`; Vite proxy to the wrong port 8080 → exact pins + lockfile + `npm ci`, proxy to 8000.
9. `nginx:alpine` running as root (fails M4) and proxy hard-coded to `backend:8000` → `nginx-unprivileged` on 8080 with templated `API_UPSTREAM`.
10. Helm Ingress → `taskboard-backend:8080`, which doesn't exist (the real one is `<release>-taskboard-backend:8000`); hard-coded names and selectors → helper-generated names everywhere.
11. DB password in `values.yaml` + password inside plain env URL → pre-created Secret + `secretKeyRef`.
12. Postgres Deployment, no PGDATA subdir, no resources → StatefulSet, PGDATA subdir, retention policy.
13. `tag: latest`, `YOUR_ORG` → `required` SHA tags.
14. Shared `replicaCount` + HPA → replicas omitted when the HPA is on.
15. ServiceMonitor without a CRD check → `.Capabilities` guard.
16. `/ready` 500 on DB failure → 503.
17. No pod/container securityContext → restricted profile.
18. CI: tag-pinned actions, no top-level permissions, pushes from PRs, static `KUBE_CONFIG_DATA` (can't auth to EKS without AWS creds), no `--atomic/--wait`, no concurrency → fixed in §9.
19. Terraform: NAT, private subnets, EKS 1.31 extended support, t3.medium ×2, wrong-Region AZs, no tfvars example, ignored lock file, implicit KMS and log group, IRSA/OIDC (SCP-denied), no EBS CSI driver or StorageClass, no tags.
20. `load-test.sh` hits a nonexistent `/api/health` sequentially → in-cluster fortio Job on a DB-backed endpoint.
21. Monitoring values: default Grafana password, alertmanager + persistence on → hardened values.
22. Reliance on ingress-nginx, which is retired upstream → Traefik.

---

## 14. Open questions (only true blockers; everything else is decided)

None block Phases 0–11. Before Phase 12, the user confirms:
1. **AWS window date/time.** The user schedules it, and the agent will not start it on its own initiative.
2. **Clinic timezone** for `CLINIC_TZ` (default `Australia/Sydney`, since the project Region is Sydney). Change it in one value if needed.

---

## 15. End-to-end verification summary

- **Local (every phase):** `make lint test` · `docker compose up --build` + `scripts/smoke-api.sh` · kind: `make kind-up kind-deploy` → browser at `http://waiting-room.localtest.me:8080`, Prometheus target UP, Grafana populated, `scripts/load-test.sh` scales the HPA, troubleshooting scenarios reproduce.
- **CI:** green run on `main`, a red PR run with a failing test, GHCR SHA tags, Trivy table in the logs.
- **AWS (once):** §10 runbook; finishes with `scripts/verify-teardown.sh` all empty and Cost Explorer back to ~$0.
