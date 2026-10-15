# Troubleshooting lab

Three deliberately broken manifests. For each: apply, observe the symptom, diagnose with the
commands, fix, then clean up. All run in the `waiting-room` namespace.

```bash
kubectl apply -f troubleshooting/broken-image.yaml
kubectl apply -f troubleshooting/broken-service.yaml
SHA=$(git rev-parse HEAD) envsubst < troubleshooting/broken-readiness.yaml | kubectl apply -f -
```

| # | Manifest | Symptom | Diagnose | Root cause | Fix |
|---|---|---|---|---|---|
| 1 | `broken-image.yaml` | Pod `ImagePullBackOff` / `ErrImagePull` | `kubectl get pods`; `kubectl describe pod -l app=wr-broken-image` (Events); `kubectl get events --sort-by=.lastTimestamp` | Image tag `this-tag-does-not-exist` is not in GHCR | `kubectl set image deploy/wr-broken-image backend=ghcr.io/mrind3v/waiting-room-backend:<real-sha>` |
| 2 | `broken-service.yaml` | Service exists but `curl` hangs; no traffic | `kubectl get endpointslices -l kubernetes.io/service-name=wr-broken-service` (empty); `kubectl get pods --show-labels`; `kubectl describe svc wr-broken-service` | Selector `component=api` matches no Pod; real label is `component=backend` | `kubectl patch svc wr-broken-service -p '{"spec":{"selector":{"app.kubernetes.io/component":"backend"}}}'` |
| 3 | `broken-readiness.yaml` | Pod `Running` but `0/1` Ready; Service has no ready endpoints | `kubectl get pods`; `kubectl describe pod` (Readiness probe failed: HTTP 503); `kubectl logs deploy/wr-broken-readiness`; `kubectl exec ... -- python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/ready'))"` | `DB_HOST=postgres-typo` does not resolve, so `/ready` returns 503 | `kubectl set env deploy/wr-broken-readiness DB_HOST=waiting-room-postgres` |

Key lessons: *events first*, *labels connect Services to Pods*, and *liveness (`/health`) differs from
readiness (`/ready`)*: the app is alive but must not receive traffic until it can reach the database.

Clean up: `kubectl delete -f troubleshooting/ --ignore-not-found`
