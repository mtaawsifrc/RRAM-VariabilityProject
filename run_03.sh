#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

python3 "$ROOT/03_run_stanford_baseline.py" \
  --rep-csv "$ROOT/step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv" \
  --va "$ROOT/rram_v_1_0_0_hspice.va" \
  --deck-mode butterfly \
  --output-dir "$ROOT/step03_S1_baseline" \
  --auto-set-compliance-current
