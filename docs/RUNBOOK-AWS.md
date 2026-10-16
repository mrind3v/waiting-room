# AWS window runbook: apply, demo, teardown

One sitting of about 4–5 hours (about $0.26/h, roughly $1.50 total). Rehearse everything on kind first.
Every step marked ⚠ creates, changes or deletes AWS resources and needs your explicit go-ahead.

## T-1 day checklist
- [ ] Budget `waiting-room-guard` exists (Billing → Budgets, or `describe-budgets`)
- [ ] `main` pipeline is green; both GHCR packages are **public**
- [ ] Rehearsal on kind passed (`make kind-up && make kind-deploy SHA=…`)
- [ ] Remaining credits OK: `aws freetier get-account-plan-state --profile agent-toolkit`
- [ ] `aws sts get-caller-identity --profile agent-toolkit` → account `802823597889`
- [ ] Screen recorder ready (see docs/SUBMISSION.md)

## 1. Apply (about 25 min)
```bash
export AWS_PROFILE=agent-toolkit
cd terraform && terraform init && terraform plan -out=tfplan     # screenshot: m7-plan
terraform show -no-color tfplan | grep -E 'nat_gateway|aws_eip|kms_key|log_group|openid' || echo clean
```
⚠ After reviewing "Plan: 50 to add":
```bash
terraform apply tfplan                      # ~12-15 min (EKS)         # screenshot: m7-apply
$(terraform output -raw kubeconfig_command)
kubectl get nodes                           # 1 node Ready
cd .. && ./scripts/cluster-bootstrap.sh eks # ⚠ namespaces, gp3, RBAC, secrets, Traefik(NLB), Prometheus/Grafana
kubectl -n traefik get svc traefik -w       # wait for EXTERNAL-IP hostname
```
⚠ Give CI access to the cluster (keys are piped, never printed):
```bash
terraform -chdir=terraform output -raw ci_access_key_id        | gh secret set AWS_ACCESS_KEY_ID
terraform -chdir=terraform output -raw ci_secret_access_key    | gh secret set AWS_SECRET_ACCESS_KEY
gh variable set AWS_REGION --body ap-southeast-2
gh variable set EKS_CLUSTER_NAME --body waiting-room-eks
gh variable set DEPLOY_ENABLED --body true
```

## 2. Deploy and demo (about 2 h, recorded)
```bash
git commit --allow-empty -m "chore: trigger first EKS deploy" && git push && gh run watch   # deploy only runs on push events
kubectl -n waiting-room exec deploy/waiting-room-backend -- python -m app.seed
kubectl -n waiting-room get pods,svc,ingress,hpa ; helm list -A
```
Take the screenshots and recordings listed in `docs/SUBMISSION.md`. The live-change demo is a one-line UI
change committed and pushed while recording; the footer build SHA changes after the rollout.

## 3. Pre-destroy cleanup (about 10 min) ⚠
```bash
./scripts/pre-destroy.sh    # removes CI secrets, helm releases, PVCs, namespaces; the NLB goes with Traefik
kubectl get pv; kubectl get svc -A | grep LoadBalancer     # both must be empty
```
Orphaned load balancers keep ENIs and security groups alive and make `terraform destroy` hang on the VPC.

## 4. Destroy (about 15 min) ⚠
```bash
cd terraform
terraform plan -destroy -out=destroy.tfplan     # review
terraform apply destroy.tfplan                  # screenshot: m7-destroy ("Destroy complete!")
rm -f tfplan destroy.tfplan
kubectl config delete-context <eks-context>
```

## 5. Post-destroy verification (must all be empty)
```bash
./scripts/verify-teardown.sh        # exits 1 and lists leftovers; screenshot: m7-teardown-clean
terraform state list                # empty
```
Next day: Cost Explorer daily cost back to about $0 and credits ≈ $100 minus the estimate.
Checked: EKS clusters, EC2 instances, EBS volumes, load balancers (v2 + classic), Elastic IPs, NAT
gateways, non-default VPCs, tagged security groups, IAM user/roles, CloudWatch log groups in
ap-southeast-2 **and** us-east-1.

## If something goes wrong
- `terraform destroy` fails on the IAM user with `iam:DeleteLoginProfile ... explicit deny in a service control policy` → the user was created with `force_destroy = true`, which the Free plan blocks. The code now sets `false`; if you hit it on an older state, run `terraform apply -target=aws_iam_user.ci` (state-only update), then `terraform destroy`.
- `terraform destroy` hangs on the VPC → an orphaned NLB/ENI/volume: run `verify-teardown.sh`, delete the
  leftover in the console (EC2 → Load Balancers / Volumes), re-run destroy.
- Pods Pending on EKS → node full (the node has 29 pod slots and 8 GiB); check `kubectl describe pod`.
- PVC Pending → the EBS CSI add-on or the `gp3` StorageClass is missing; `kubectl get sc`, `kubectl -n kube-system get pods | grep ebs`.
- Deploy job `Unauthorized` → access entry/RBAC: `kubectl -n waiting-room get rolebinding`.
