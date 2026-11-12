#!/usr/bin/env bash
# Deploy the prod-release manifests in dependency order.
#
#   scripts/deploy_release.sh <source-org-alias> <target-org-alias> [--validate-only] [--from NN]
#
# For each stage: retrieve from the source org, validate (dry run) against the
# target, then deploy. Stops at the first failure. Each stage depends on the
# ones before it, so later stages cannot be validated until earlier ones are
# deployed; rehearse the full run in a UAT/full-copy sandbox before production.
set -euo pipefail

SRC=${1:?source org alias, e.g. lscqa}
TGT=${2:?target org alias, e.g. prod}
shift 2
VALIDATE_ONLY=false; FROM=00
while [[ $# -gt 0 ]]; do
  case $1 in
    --validate-only) VALIDATE_ONLY=true ;;
    --from) FROM=$2; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

for manifest in "$ROOT"/manifest/prod-release/[0-9][0-9]-*.xml; do
  stage=$(basename "$manifest" .xml)
  [[ $stage == 99-* ]] && continue
  [[ ${stage:0:2} < $FROM ]] && continue
  echo "=== $stage"
  sf project retrieve start -o "$SRC" --manifest "$manifest" \
     --target-metadata-dir "$WORK/$stage" --unzip --wait 30 >/dev/null
  # The retrieve unzips to <dir>/unpackaged/unpackaged with its own package.xml.
  src_dir=$(dirname "$(find "$WORK/$stage" -name package.xml | head -1)")
  # No --test-level: production then runs local tests only if the stage has Apex.
  sf project deploy start -o "$TGT" --metadata-dir "$src_dir" --dry-run --wait 60
  if ! $VALIDATE_ONLY; then
    sf project deploy start -o "$TGT" --metadata-dir "$src_dir" --wait 60
  fi
done
echo "Done."
