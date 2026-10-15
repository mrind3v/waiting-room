# Architecture and decisions

## Application
- **FastAPI + SQLAlchemy 2 + Alembic.** Migrations are the only way the schema changes (no `create_all`).
  `/ready` checks both the database and that the schema is at the Alembic head, returning 503 otherwise.
- **Times are stored in UTC**; the clinic's timezone (`CLINIC_TZ`, default `Australia/Sydney`) defines
  "today" and working hours.
- **Overlap rule lives in the database**, not in application code, because a "check then insert" race
  cannot be closed in Python (see README).
- **React + Vite**, plain CSS design tokens, polling every 15 s (paused while the tab is hidden).

## Containers
- Backend: multi-stage, digest-pinned `python:3.12-slim`, uid 10001, no migrations in `CMD`.
- Frontend: Node build stage, `nginx-unprivileged` runtime (uid 101, port 8080), API upstream injected
  via `API_UPSTREAM` so the same image works in Compose and Kubernetes.
- Migrations: a one-shot `migrate` service in Compose; an `initContainer` in Kubernetes. Both take a
  Postgres advisory lock so concurrent starts are safe.

## Kubernetes
- Helm chart with helper-generated names so Services, Ingress and probes cannot drift apart.
- PostgreSQL is a single-replica StatefulSet with a PVC (`PGDATA` in a subdirectory because EBS volumes
  contain `lost+found`). Retention policy deletes the PVC with the release so nothing is orphaned.
- HPA on CPU for both tiers; Deployments omit `replicas` while HPA is enabled.
- **Traefik** is the Ingress controller (ingress-nginx is retired upstream); on EKS its Service creates
  the single NLB, avoiding the AWS Load Balancer Controller (which needs an IAM OIDC provider).

## AWS and the Free plan
The account is on the AWS Free plan, whose service control policy blocks Spot instances and IAM OIDC
providers and allows only a handful of instance types. Consequences:

| Constraint | Decision |
|---|---|
| `t3.medium` not allowed | one `m7i-flex.large` (2 vCPU / 8 GiB) |
| No IAM OIDC provider | EBS CSI via EKS Pod Identity; CI deploys with a short-lived IAM user + namespace-scoped RBAC |
| Cost | public subnets, no NAT, no RDS, no KMS key, no control-plane logs, Kubernetes 1.35 (standard support) |

Trade-off: public subnets with public node IPs are less isolated than private nodes behind NAT. For a
few-hour demo with security groups closed to the internet, the saving outweighs it.

## Observability
- `prometheus-fastapi-instrumentator` for HTTP metrics (probe and metrics endpoints excluded) plus
  domain counters: bookings, conflicts and status transitions.
- A `ServiceMonitor` and a Grafana dashboard ConfigMap ship inside the chart; Prometheus uses `emptyDir`
  (no PVC) and Grafana/Prometheus are reached by `kubectl port-forward` (no extra load balancers).
