#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/terraform"

role_name="mealdash-github-deployer"

# Recover from an interrupted apply that created the role before saving it in state.
if terraform state show aws_iam_role.github_deployer >/dev/null 2>&1; then
  exit 0
fi
if ! aws iam get-role --role-name "$role_name" >/dev/null 2>&1; then
  exit 0
fi

project_tag="$(aws iam list-role-tags --role-name "$role_name" \
  --query 'Tags[?Key==`Project`].Value | [0]' --output text)"
if [[ "$project_tag" != "mealdash-capstone" ]]; then
  echo "Refusing to import $role_name: Project tag '$project_tag' is not mealdash-capstone." >&2
  exit 1
fi

echo "Importing the existing MealDash deploy role into Terraform state."
terraform import aws_iam_role.github_deployer "$role_name"
