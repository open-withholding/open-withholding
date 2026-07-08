#!/usr/bin/env bash
# One-time GitHub setup once the repo has a remote:
#   ./tools/setup_branch_protection.sh <owner>/<repo>
#
# Makes direct pushes to main impossible even for admins, requires the CI
# checks, and forbids force pushes — every data change must arrive as a
# reviewable PR with green CI (the trust model in DESIGN.md §8.3).
#
# Note: required reviewer approval is NOT set — with a single maintainer,
# GitHub cannot require a second approver (you can't approve your own PR).
# Add "required_pull_request_reviews" once a second maintainer exists.
set -euo pipefail

REPO=${1:?usage: setup_branch_protection.sh <owner>/<repo>}

gh api -X PUT "repos/${REPO}/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      { "context": "test" },
      { "context": "data-golden-guard" }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
JSON

echo "Branch protection applied to ${REPO}:main"
