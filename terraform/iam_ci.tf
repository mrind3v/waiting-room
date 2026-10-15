# Short-lived CI identity. Exists only for the AWS window and is destroyed with the stack.
resource "aws_iam_user" "ci" {
  name          = "${var.cluster_name}-ci"
  force_destroy = true
}

resource "aws_iam_user_policy" "ci_describe_cluster" {
  name = "describe-cluster"
  user = aws_iam_user.ci.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["eks:DescribeCluster"]
      Resource = module.eks.cluster_arn
    }]
  })
}

resource "aws_iam_access_key" "ci" {
  user = aws_iam_user.ci.name
}
