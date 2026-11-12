#!/usr/bin/env bash
# Export every successful, non-validation deployment in an org and list the
# distinct components it deployed.
#   scripts/export_deploy_history.sh <org-alias> <out-dir>
# Writes <out-dir>/components.json for build_release_manifests.py.
set -euo pipefail
ORG=${1:?org alias}; OUT=${2:?output dir}
mkdir -p "$OUT/reports"
sf data query -o "$ORG" --use-tooling-api --json \
  -q "SELECT Id FROM DeployRequest WHERE Status='Succeeded' AND CheckOnly=false ORDER BY CreatedDate" \
  > "$OUT/deploys.json"
python3 -c 'import json,sys;[print(r["Id"]) for r in json.load(open(sys.argv[1]))["result"]["records"]]' "$OUT/deploys.json" |
  xargs -P 6 -I{} sh -c "sf project deploy report -o '$ORG' --job-id {} --json > '$OUT/reports/{}.json'"
python3 "$(dirname "$0")/aggregate_deploy_reports.py" "$OUT"
