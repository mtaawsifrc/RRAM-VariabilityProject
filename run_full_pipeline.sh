#!/usr/bin/env bash
# Full publication pipeline (final results).
#
# Prerequisites: MATLAB + HSPICE on PATH; step01_*/step02_* already built from
# raw_data (run_01.sh / run_02.sh per condition -- they exist for S1-S12).
#
# Usage:
#   bash run_full_pipeline.sh             # all 12 conditions
#   bash run_full_pipeline.sh S1 S2       # a subset
#
# Stages:
#   07_run_final.py     ensemble (02b) + regime classification (02c) + final
#                       TaO-Fit per condition: regime-conditioned priors,
#                       mechanism-aware loss, Fisher CRLB, profile likelihood
#                       -> results/<cond>_taofit/identifiability_report.csv
#   04_publication_summary.py  parameter tables, identifiability heatmap, figures
#   05_run_ablation.py  4-arm ablation (plain / physics / physics+regime / no-BO)
#   06_run_variability.py  cluster-bootstrap 95% CIs + cycle-to-cycle mechanism
#                       stability + dominant-mechanism map across conditions
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CONDS=("$@")

echo "=== [1/4] Final fits (07_run_final.py) ==="
python3 07_run_final.py "${CONDS[@]}" || echo "WARN: some final fits failed"

echo "=== [2/4] Publication summary (04_publication_summary.py) ==="
python3 04_publication_summary.py || echo "WARN: publication summary failed"

echo "=== [3/4] Ablation (05_run_ablation.py) ==="
python3 05_run_ablation.py "${CONDS[@]}" || echo "WARN: ablation failed"

echo "=== [4/4] Variability + bootstrap CIs (06_run_variability.py) ==="
python3 06_run_variability.py "${CONDS[@]}" || echo "WARN: variability failed"

echo "Done. See results/ (per-condition *_taofit, publication/, ablation/, variability/)"
