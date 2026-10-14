#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: $0 <RDS-managed-secret-arn>" >&2; exit 2; fi
command -v aws >/dev/null && command -v kubectl >/dev/null || { echo "Install AWS CLI and kubectl first." >&2; exit 2; }
tmpdir="$(mktemp -d)"; chmod 700 "$tmpdir"
trap 'rm -rf "$tmpdir"; unset db_password staff_password app_key' EXIT
secret_text="$(aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text)"
python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["password"])' <<<"$secret_text" > "$tmpdir/db-password"
unset secret_text; chmod 600 "$tmpdir/db-password"
read -r -s -p "Choose the demo kitchen staff password: " staff_password; echo
if [[ ${#staff_password} -lt 12 ]]; then echo "Use at least 12 characters." >&2; exit 2; fi
openssl rand -hex 32 > "$tmpdir/app-key"
printf %s "$staff_password" > "$tmpdir/staff-password"
chmod 600 "$tmpdir/app-key" "$tmpdir/staff-password"
kubectl create namespace mealdash --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic mealdash-db -n mealdash --from-file=password="$tmpdir/db-password" --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic mealdash-app -n mealdash --from-file=staff-password="$tmpdir/staff-password" --from-file=secret-key="$tmpdir/app-key" --dry-run=client -o yaml | kubectl apply -f -
echo "Runtime secrets applied to namespace mealdash. Values were not printed."
