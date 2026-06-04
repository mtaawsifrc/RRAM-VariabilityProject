#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
INPUT="$ROOT/step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv"
CFG="$ROOT/stanford_fit/config/default_config.yaml"
OUT="$ROOT/results/S1_taofit_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT"
echo "[run] input=$INPUT"
echo "[run] outdir=$OUT"
matlab -batch "cd('$ROOT/stanford_fit/matlab');main_fit_stanford('$INPUT','$CFG','$OUT')"
echo "[run] done"

