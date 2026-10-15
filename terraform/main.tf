# Minimal-cost network: two public subnets, an internet gateway, NO NAT gateway, NO private subnets.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.7.3"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = var.azs

  public_subnets          = var.public_subnet_cidrs
  map_public_ip_on_launch = true
  enable_dns_hostnames    = true
  enable_dns_support      = true
  enable_nat_gateway      = false

  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = 1
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# EBS CSI driver role via EKS Pod Identity. IRSA would need an IAM OIDC provider, which the
# Free-plan service control policy denies (iam:*Provider*).
module "ebs_csi_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "2.9.0"

  name                      = "${var.cluster_name}-ebs-csi"
  attach_aws_ebs_csi_policy = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.29.0"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  # Public API endpoint (IAM-authenticated) so GitHub-hosted runners can deploy.
  endpoint_public_access = true

  enable_cluster_creator_admin_permissions = true

  # No OIDC provider (denied by SCP), no KMS key ($1/mo + pending deletion), no log group.
  enable_irsa                 = false
  create_kms_key              = false
  encryption_config           = null
  enabled_log_types           = []
  create_cloudwatch_log_group = false

  addons = {
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
    kube-proxy             = {}
    coredns                = {}
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = module.ebs_csi_pod_identity.iam_role_arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND" # Spot is denied on the Free plan.
      min_size       = 1
      desired_size   = 1
      max_size       = 2
      disk_size      = 20
    }
  }

  # CI deploys as an IAM user mapped to a Kubernetes group; the namespace-scoped Role in
  # k8s/rbac-ci-deployer.yaml grants the rights. No cluster-wide access policy.
  access_entries = {
    ci = {
      principal_arn     = aws_iam_user.ci.arn
      kubernetes_groups = ["waiting-room-deployers"]
    }
  }
}
