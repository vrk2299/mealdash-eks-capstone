#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

region="${AWS_REGION:-ap-south-1}"
account_id="$(aws sts get-caller-identity --query Account --output text)"
bucket="mealdash-terraform-state-${account_id}-${region}"

if ! aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
  if [[ "$region" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$bucket" --region "$region" >/dev/null
  else
    aws s3api create-bucket --bucket "$bucket" --region "$region" \
      --create-bucket-configuration "LocationConstraint=$region" >/dev/null
  fi
fi

aws s3api put-public-access-block --bucket "$bucket" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$bucket" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$bucket" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

terraform -chdir=terraform init -migrate-state \
  -backend-config="bucket=$bucket" \
  -backend-config="key=mealdash/terraform.tfstate" \
  -backend-config="region=$region" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"
