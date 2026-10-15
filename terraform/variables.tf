variable "region" {
  description = "Project Region. All Regional resources must live here."
  type        = string
  default     = "ap-southeast-2"
}

variable "azs" {
  description = "Two Availability Zones in the Region."
  type        = list(string)
  default     = ["ap-southeast-2a", "ap-southeast-2b"]
}

variable "cluster_name" {
  type    = string
  default = "waiting-room-eks"
}

variable "kubernetes_version" {
  description = "Standard-support version (older versions cost $0.60/h extended support)."
  type        = string
  default     = "1.35"
}

variable "node_instance_type" {
  description = "Must be Free-plan eligible: t3.micro/small, t4g.micro/small, c7i-flex.large, m7i-flex.large."
  type        = string
  default     = "m7i-flex.large"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.30.0.0/20", "10.30.16.0/20"]
}
