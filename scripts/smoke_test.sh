#!/usr/bin/env bash
# End-to-end smoke test of the Locus CLI. Exercises every command against a
# temporary registry + workspace so it never pollutes your real ~/.locus.
#
# Usage:  bash scripts/smoke_test.sh
# Requires: a built/installed `locus` (e.g. `uv run` or `pip install locus-etl`).
set -euo pipefail

LOCUS="${LOCUS_BIN:-uv run locus}"
TMP="$(mktemp -d)"
export LOCUS_HOME="$TMP/.locus"   # isolate registry/cache if honored
trap 'rm -rf "$TMP"' EXIT

say() { printf "\n\033[1;36m== %s ==\033[0m\n" "$1"; }

say "version"
$LOCUS version

say "catalog list"
$LOCUS catalog list

say "prepare sample data + locusfile"
mkdir -p "$TMP/data"
printf 'invoice_number,vendor,total\nINV-1,Acme Corp,100.50\nINV-2,Globex,2200.00\n' > "$TMP/data/invoices.csv"
cat > "$TMP/locusfile.yaml" <<EOF
image: doc-to-tables
source:
  type: files
  path: $TMP/data/invoices.csv
EOF

say "validate"
$LOCUS validate "$TMP/locusfile.yaml"

say "run (single image) + export"
$LOCUS run "$TMP/locusfile.yaml" --export "$TMP/out.csv"
test -f "$TMP/out.csv" && echo "export OK"

say "run (multi-stage pipeline: extract -> redact -> drop-flagged)"
cat > "$TMP/pipeline.yaml" <<EOF
source:
  type: files
  path: $TMP/data/invoices.csv
pipeline:
  - id: extract
    image: doc-to-tables
  - id: redact
    image: pii-redactor
    needs: [extract]
  - id: clean
    image: drop-flagged
    needs: [redact]
EOF
$LOCUS run "$TMP/pipeline.yaml"

say "catalog seed (into temp registry)"
$LOCUS catalog seed

say "search"
$LOCUS search

say "inspect"
$LOCUS inspect doc-to-tables

say "pull"
$LOCUS pull pii-redactor

say "ALL COMMANDS PASSED"
