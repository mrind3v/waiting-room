# Submission guide: what to screenshot and record

Save every image in `docs/screenshots/` with exactly these names. Use full-window screenshots
(macOS: `Cmd+Shift+4` then `Space` then click the window; or `Cmd+Shift+5` to record). Keep the terminal
font large and make sure the **command and its output** are both visible. Never show secrets
(Grafana password, AWS keys); blur or crop them.

Do the AWS captures (marked ☁) inside the single window described in `docs/RUNBOOK-AWS.md`. Everything
else can be captured **now, locally**.

## A. Capture locally first (no AWS needed)

| File | Rubric | How to capture it | Must be visible |
|---|---|---|---|
| `m1-board.png` | M1 | `docker compose up --build -d`, seed, open http://localhost:3000 | Board with 4 columns, KPI strip, waiting timers, doctor chips |
| `m1-schedule-409.png` | M1 | Schedule → open a free slot in one tab, book it in another; the second shows "Slot just taken" | The inline red 409 message |
| `m1-mobile.png` | M1 | DevTools → device toolbar → iPhone SE (375px) on the Board | Stacked columns and bottom tab bar |
| `m1-swagger.png` | M1 | http://localhost:8000/docs | All routes expanded or visible |
| `m1-health.png` | M1 | `curl -s localhost:8000/health; curl -s localhost:8000/ready` | `{"status":"ok"}` and `{"status":"ready"}` |
| `m1-psql-tables.png` | M1 | `docker compose exec db psql -U waitingroom -d waitingroom -c '\dt' -c '\d appointments'` | `alembic_version`, 3 tables, the `appointments_no_doctor_overlap` EXCLUDE constraint |
| `m2-pytest.png` | M2 | `cd backend && set -a && . ../.env && set +a && .venv/bin/pytest -v` | All 36 PASSED and the coverage table |
| `m3-commits.png` | M3 | `git log --oneline --decorate \| head -30` (or the GitHub commits page) | ≥10 meaningful messages |
| `m4-compose-up.png` | M4 | `docker compose down -v && docker compose up --build` (let it settle, then `docker compose ps`) | `db` healthy, `migrate` exited 0, `backend` healthy, `frontend` up |
| `m4-localhost-3000.png` | M4 | Browser on http://localhost:3000 | App loaded with data |
| `m4-nonroot.png` | M4 | `docker compose exec backend id -u; docker compose exec frontend id -u` | `10001` and `101` |
| `m5-green-run.png` | M5 | GitHub → Actions → latest green run (graph view) | All jobs green incl. Trivy; run URL in the address bar |
| `m5-red-run.png` | M5 | Open a PR that breaks one test (revert afterwards); screenshot the failed run | `backend-test` red and `build-scan-push` skipped |
| `m5-ghcr-backend.png`, `m5-ghcr-frontend.png` | M5 | github.com/mrind3v?tab=packages → each package → Versions | 40-character SHA tags, no `latest` |
| `m6-trivy.png` | M6 | Actions run → *Trivy scan* step of a matrix job | The Report Summary table and `exit-code: 1` setting |
| `m7-init.png` | M7 | `cd terraform && terraform init` | "Terraform has been successfully initialized!" |
| `m7-plan.png` | M7 | `AWS_PROFILE=agent-toolkit terraform plan` | `Plan: 50 to add, 0 to change, 0 to destroy` |
| `m8-helm-template.png` | M8 | `helm lint helm/waiting-room …` and `helm template … \| head` | Lint passes (optional extra) |
| `m8-kind-pods.png` | M8 (rehearsal proof) | `kubectl -n waiting-room get pods,svc,ingress,hpa` on kind | All Running, ≥2 replicas, ClusterIP services, Ingress |
| `m9-metrics-curl.png` | M9 | `kubectl -n waiting-room port-forward svc/waiting-room-backend 8000:8000` then `curl -s localhost:8000/metrics \| head -40` | `http_requests_total`, `waitingroom_*` counters |
| `m9-prom-targets-up.png` | M9 | `kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090` → Status → Targets | `serviceMonitor/waiting-room/…` **UP** |
| `m9-grafana-dashboard.png` | M9 | `kubectl -n monitoring port-forward svc/kps-grafana 3001:80` → Dashboards → Waiting Room, **while** `./scripts/load-test.sh` runs | Request-rate and replica panels populated |
| `m9-hpa.png` | M9/M8 | `./scripts/load-test.sh` in one terminal, `kubectl get hpa -n waiting-room -w` | REPLICAS rising from 2 to 5, CPU above target |
| `m9-troubleshooting.png` | extra | `kubectl apply -f troubleshooting/broken-image.yaml` then `kubectl describe pod …` | `ImagePullBackOff` and the Events |

Grafana login: user `admin`, password via
`kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d`.
Do not include the password in a screenshot.

## B. Capture during the AWS window ☁ (kind versions above are rehearsal only)

| File | Rubric | How | Must be visible |
|---|---|---|---|
| `m7-apply.png` | M7 | End of `terraform apply tfplan` | `Apply complete! Resources: 50 added` |
| `m7-console-vpc.png` | M7 | AWS Console → VPC (region **ap-southeast-2** in the top bar) | VPC `waiting-room-eks-vpc` with 2 public subnets |
| `m7-console-eks.png` | M7 | Console → EKS → cluster → Compute | Cluster Active, node group with 1 node, region visible |
| `m8-pods.png` | M8 | `kubectl get pods -n waiting-room` on EKS | All `Running`, 2 backend + 2 frontend + postgres |
| `m8-svc.png` | M8 | `kubectl get svc,ingress,hpa -n waiting-room` | ClusterIP services, Ingress, HPA |
| `m8-helm-list.png` | M8 | `helm list -A` | `waiting-room` deployed, kps, traefik |
| `m8-ingress-browser.png` | M8 | Browser on `http://<NLB hostname>/` | App loaded through the Ingress; hostname in the address bar |
| `m9-eks-prom-targets.png`, `m9-eks-grafana.png` | M9 | same as local, on the EKS cluster | UP target; populated panel |
| `m7-destroy.png` | M7 | End of `terraform apply destroy.tfplan` | `Destroy complete! Resources: 50 destroyed` |
| `m7-teardown-clean.png` | M7 | `./scripts/verify-teardown.sh` | `ALL CLEAN` |

## C. Screen recordings

Record at 1080p with microphone on (`Cmd+Shift+5` → Record Entire Screen → Options → Microphone). Keep
each clip under 10 minutes; cut dead waiting time. Upload as unlisted video and put the links in the form.

**Recording 1: the M10 live demo (required, about 6–8 min).** Script:
1. (30 s) Show the running app on the EKS NLB hostname; the footer shows the current build SHA (note it).
2. (30 s) In the editor, change one visible string (for example the Board subtitle).
3. (30 s) `git commit -m "feat(frontend): …"` and `git push`; say what each pipeline stage does.
4. (2 min) GitHub Actions: show `backend-test` → `frontend-build` → `infra-lint` → build/Trivy/push → `deploy`
   all going green. Sped-up footage is fine.
5. (1 min) GHCR: the new SHA tag. Terminal: `kubectl rollout status` and
   `kubectl get pods -n waiting-room -o jsonpath='{..image}'` showing the new SHA.
6. (30 s) Refresh the browser: new text and the **new SHA in the footer**.
7. (1 min) Book the same slot twice to show the 409, then move a patient Booked → Waiting → With doctor → Done.

**Recording 2: observability and scaling (about 3 min).** Run `./scripts/load-test.sh`; show Grafana request
rate rising, `kubectl get hpa -w` scaling 2 → 5, Prometheus Targets UP.

**Recording 3: troubleshooting (about 3 min).** Apply `troubleshooting/broken-service.yaml`, diagnose with
`get endpointslices` and `get pods --show-labels`, patch the selector, confirm. Narrate "no matching labels,
no endpoints, no traffic".

**Recording 4: teardown (about 2 min).** `./scripts/pre-destroy.sh`, `terraform apply destroy.tfplan`,
`./scripts/verify-teardown.sh` ending in `ALL CLEAN`.

## D. Written items for the form
- Repository: https://github.com/mrind3v/waiting-room (public)
- Green Actions run URL (copy from the browser on the green run) and GHCR package URLs
- Trivy explanation: paste the 2–3 sentences from `docs/SECURITY-SCAN.md`
- One-line cost note: ~$0.26/h, one ~5 h window, verified teardown (`ALL CLEAN`)

## E. Final checklist
```text
[ ] Repo URL                              [ ] ≥10 meaningful commits
[ ] m1-* screenshots                      [ ] m2-pytest
[ ] m4-compose-up, m4-localhost-3000, m4-nonroot
[ ] m5 green + red run, GHCR SHA tags     [ ] m6-trivy + explanation
[ ] m7 init/plan/apply/console/destroy/teardown-clean
[ ] m8 pods/svc/helm list/ingress browser [ ] m9 metrics/targets/grafana/hpa
[ ] README.md present                     [ ] Recording 1 (live demo) uploaded
[ ] No secrets in history: git log -p | grep -iE 'AKIA|secret' → nothing
[ ] GitHub AWS secrets deleted, DEPLOY_ENABLED=false after the window
```
