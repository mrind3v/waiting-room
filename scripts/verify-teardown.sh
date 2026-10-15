#!/usr/bin/env bash
# Read-only inventory proving nothing billable is left. Exit code 1 if anything remains.
set -uo pipefail
export AWS_PROFILE="${AWS_PROFILE:-agent-toolkit}"
R=ap-southeast-2
FAIL=0
check() { # description, command-output (should be empty)
  if [ -n "$2" ]; then echo "LEFTOVER  $1: $2"; FAIL=1; else echo "ok        $1"; fi
}
q() { aws "$@" --region "$R" --output text 2>/dev/null; }

check "EKS clusters"          "$(q eks list-clusters --query 'clusters[]')"
check "EC2 instances"         "$(q ec2 describe-instances --filters Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId')"
check "EBS volumes"           "$(q ec2 describe-volumes --query 'Volumes[].VolumeId')"
check "Load balancers (v2)"   "$(q elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerArn')"
check "Load balancers (clb)"  "$(q elb describe-load-balancers --query 'LoadBalancerDescriptions[].LoadBalancerName')"
check "Elastic IPs"           "$(q ec2 describe-addresses --query 'Addresses[].PublicIp')"
check "NAT gateways"          "$(q ec2 describe-nat-gateways --filter Name=state,Values=pending,available --query 'NatGateways[].NatGatewayId')"
check "Non-default VPCs"      "$(q ec2 describe-vpcs --filters Name=is-default,Values=false --query 'Vpcs[].VpcId')"
check "Tagged security groups" "$(q ec2 describe-security-groups --filters Name=tag:Project,Values=waiting-room --query 'SecurityGroups[].GroupId')"
check "IAM CI user"           "$(aws iam list-users --query "Users[?starts_with(UserName,'waiting-room')].UserName" --output text 2>/dev/null)"
check "IAM roles"             "$(aws iam list-roles --query "Roles[?contains(RoleName,'waiting-room')].RoleName" --output text 2>/dev/null)"
for REG in "$R" us-east-1; do
  check "CloudWatch log groups ($REG)" "$(aws logs describe-log-groups --log-group-name-prefix /aws/eks --region "$REG" --query 'logGroups[].logGroupName' --output text 2>/dev/null)"
done
[ "$FAIL" = 0 ] && echo "ALL CLEAN" || { echo "Resources remain: delete them before leaving the account."; exit 1; }
