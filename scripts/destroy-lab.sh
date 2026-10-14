#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/terraform"
cluster="$(terraform output -raw cluster_name)"
region="$(terraform output -raw aws_region)"
vpc_id="$(terraform output -raw vpc_id)"
account_id="$(aws sts get-caller-identity --query Account --output text)"
policy_name="AWSLoadBalancerControllerIAMPolicy-${cluster}"
policy_arn="arn:aws:iam::${account_id}:policy/${policy_name}"
echo "This permanently deletes the MealDash VPC, EKS cluster, ECR repository, RDS database and its data."
echo "Confirm the active AWS identity before continuing:"
aws sts get-caller-identity
read -r -p "Type DESTROY MEALDASH to continue: " approval
[[ "$approval" == "DESTROY MEALDASH" ]] || { echo "Cancelled."; exit 1; }
aws eks update-kubeconfig --name "$cluster" --region "$region"
kubectl delete ingress mealdash -n mealdash --ignore-not-found
for attempt in $(seq 1 60); do
  remaining="$(aws elbv2 describe-load-balancers --query "length(LoadBalancers[?VpcId=='${vpc_id}'])" --output text)"
  if [[ "$remaining" == "0" ]]; then break; fi
  echo "Waiting for MealDash ALB cleanup in $vpc_id ($remaining load balancer(s) remain)..."
  sleep 5
done
if [[ "${remaining:-0}" != "0" ]]; then echo "ALB cleanup is incomplete; keep the controller and Terraform stack, inspect Ingress events, and retry." >&2; exit 1; fi
kubectl delete namespace mealdash --wait=true --timeout=5m
helm uninstall "aws-load-balancer-controller-${cluster}" -n kube-system || true
eksctl delete iamserviceaccount --cluster "$cluster" --region "$region" --namespace kube-system --name "aws-load-balancer-controller-${cluster}" --wait || true
if aws iam get-policy --policy-arn "$policy_arn" >/dev/null 2>&1; then aws iam delete-policy --policy-arn "$policy_arn"; fi
terraform destroy
echo "Terraform resources destroyed. Verify there are no remaining MealDash load balancers or project-tagged resources in AWS."
