#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
for tool in aws terraform kubectl helm eksctl curl python3 openssl; do command -v "$tool" >/dev/null || { echo "Missing required command: $tool" >&2; exit 2; }; done
if [[ ! -f terraform/terraform.tfvars ]] || grep -q 'REPLACE_WITH' terraform/terraform.tfvars; then
  echo "Create terraform/terraform.tfvars from the example and add the GitHub numeric IDs first." >&2
  exit 2
fi
aws sts get-caller-identity
cd terraform
terraform init
terraform validate
terraform plan -out=mealdash.tfplan
echo "Review the Terraform plan above. This provisions a separate EKS, RDS, ECR and VPC stack and incurs AWS charges."
read -r -p "Type CREATE MEALDASH to apply: " approval
[[ "$approval" == "CREATE MEALDASH" ]] || { echo "No resources created."; exit 1; }
terraform apply mealdash.tfplan
cluster="$(terraform output -raw cluster_name)"
region="$(terraform output -raw aws_region)"
cd "$root"
export AWS_REGION="$region"
aws eks update-kubeconfig --name "$cluster" --region "$region"
kubectl wait --for=condition=Ready nodes --all --timeout=20m
bash scripts/bootstrap-alb-controller.sh "$cluster"
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/rbac.yaml
secret_arn="$(cd terraform && terraform output -raw rds_secret_arn)"
bash scripts/bootstrap-runtime-secrets.sh "$secret_arn"
cat <<EOF

Foundation and classroom prerequisites are ready.
Cluster: $cluster
Region: $region
ECR: $(cd terraform && terraform output -raw ecr_repository_url)
Deploy role: $(cd terraform && terraform output -raw github_deployer_role_arn)
RDS host: $(cd terraform && terraform output -raw rds_endpoint)

Set these GitHub repository variables before deploying:
AWS_REGION=$region
AWS_DEPLOY_ROLE_ARN=$(cd terraform && terraform output -raw github_deployer_role_arn)
EKS_CLUSTER_NAME=$cluster
ECR_REPOSITORY=mealdash
DB_HOST=$(cd terraform && terraform output -raw rds_endpoint)
DB_NAME=mealdash
DB_USER=mealdash_admin
EOF
