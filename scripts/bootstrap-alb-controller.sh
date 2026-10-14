#!/usr/bin/env bash
set -euo pipefail
cluster="${1:-mealdash}"
region="${AWS_REGION:-ap-south-1}"
account_id="$(aws sts get-caller-identity --query Account --output text)"
policy_name="AWSLoadBalancerControllerIAMPolicy-${cluster}"
role_name="${cluster}-aws-load-balancer-controller"
policy_arn="arn:aws:iam::${account_id}:policy/${policy_name}"
tmp_policy="$(mktemp)"
trap 'rm -f "$tmp_policy"' EXIT
aws eks update-kubeconfig --name "$cluster" --region "$region"
eksctl utils associate-iam-oidc-provider --cluster "$cluster" --region "$region" --approve
curl -fsSL https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.14.1/docs/install/iam_policy.json -o "$tmp_policy"
if ! aws iam get-policy --policy-arn "$policy_arn" >/dev/null 2>&1; then aws iam create-policy --policy-name "$policy_name" --policy-document "file://$tmp_policy" >/dev/null; fi
eksctl create iamserviceaccount --cluster "$cluster" --region "$region" --namespace kube-system --name "aws-load-balancer-controller-${cluster}" --role-name "$role_name" --attach-policy-arn "$policy_arn" --approve --override-existing-serviceaccounts
helm repo add eks https://aws.github.io/eks-charts >/dev/null
helm repo update eks >/dev/null
helm upgrade --install "aws-load-balancer-controller-${cluster}" eks/aws-load-balancer-controller --namespace kube-system --version 1.14.0 --set "clusterName=$cluster" --set "serviceAccount.create=false" --set "serviceAccount.name=aws-load-balancer-controller-${cluster}" --set "fullnameOverride=${cluster}-aws-load-balancer-controller" --wait --timeout 5m
kubectl rollout status deployment/"${cluster}-aws-load-balancer-controller" -n kube-system --timeout=5m
