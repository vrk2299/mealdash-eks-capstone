#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then echo "Usage: $0 <github-owner> <repository-name>" >&2; exit 2; fi
owner="$1"; repo="$2"
owner_json="$(curl -fsSL -H 'Accept: application/vnd.github+json' "https://api.github.com/users/${owner}")"
repo_json="$(curl -fsSL -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/${owner}/${repo}")"
python3 -c 'import json,sys; print("github_owner_id = \"%s\"" % json.loads(sys.argv[1])["id"]); print("github_repository_id = \"%s\"" % json.loads(sys.argv[2])["id"])' "$owner_json" "$repo_json"
