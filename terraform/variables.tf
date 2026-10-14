variable "name" {
  description = "Unique name prefix for the isolated Project 3 resources."
  type        = string
  default     = "mealdash"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-south-1"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.36"
}

variable "mysql_engine_version" {
  description = "Optional exact MySQL engine version; null uses the regional default."
  type        = string
  default     = null
}

variable "node_instance_type" {
  description = "EC2 type for the classroom worker node."
  type        = string
  default     = "t3.small"
}

variable "db_instance_class" {
  description = "Small single-AZ database class for the classroom."
  type        = string
  default     = "db.t3.micro"
}

variable "ecr_repository" {
  type    = string
  default = "mealdash"
}

variable "github_owner" {
  description = "GitHub user or organization."
  type        = string
  default     = "vrk2299"
}

variable "github_repository" {
  description = "Project 3 GitHub repository."
  type        = string
  default     = "mealdash-eks-capstone"
}

variable "github_owner_id" {
  description = "Immutable numeric GitHub owner ID."
  type        = string
}

variable "github_repository_id" {
  description = "Immutable numeric repository ID."
  type        = string
}
