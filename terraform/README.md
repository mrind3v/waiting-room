# Terraform: minimal-cost VPC + EKS (ap-southeast-2)

Creates ~50 resources: a VPC with two public subnets and an internet gateway (no NAT gateway, no
private subnets), an EKS 1.35 control plane with the VPC CNI, CoreDNS, kube-proxy, Pod Identity agent
and EBS CSI add-ons, one `m7i-flex.large` on-demand managed node, and a short-lived CI IAM user.

**Cost: about $0.26/hour while it exists** (EKS control plane $0.10 + node + NLB). It is meant to exist
for one short window. Never leave it running.

## Why these choices (Free-plan service control policy)

| Choice | Reason |
|---|---|
| `m7i-flex.large`, on-demand | Free plan only allows t3.micro/small, t4g.micro/small, c7i-flex.large, m7i-flex.large; Spot is denied |
| No IRSA / OIDC provider | `iam:*Provider*` is denied; the EBS CSI driver uses EKS Pod Identity |
| Public subnets, no NAT | A NAT gateway costs ~$0.06/h plus data; nodes get public IPs, protected by security groups |
| Kubernetes 1.35 | Versions on extended support cost $0.60/h for the control plane |
| No KMS key, no log group | Avoids a $1/mo key (with a pending-deletion tail) and an orphaned log group |
| IAM user for CI | GitHub OIDC is blocked by the same SCP; the user has only `eks:DescribeCluster` and a namespace-scoped Role |

## Usage

```bash
export AWS_PROFILE=agent-toolkit
cp terraform.tfvars.example terraform.tfvars   # optional
terraform init
terraform fmt -recursive && terraform validate
terraform plan -out=tfplan                     # read-only; review it
terraform apply tfplan                         # only during the AWS window (see docs/RUNBOOK-AWS.md)
$(terraform output -raw kubeconfig_command)
# ... demo ...  run scripts/pre-destroy.sh FIRST (load balancers + volumes), then:
terraform destroy
```

State is local and git-ignored. The CI access key lives only in state and is destroyed with the stack.
