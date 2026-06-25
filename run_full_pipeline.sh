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
#   07_run_final.py     ensemble (02b) + regime classification (02c, common
#                       log-current response + ambiguity) + final TaO-Fit per
#                       condition: regime-conditioned priors, mechanism-aware
#                       loss (smoothed/margin-excluded switching threshold),
#                       SVD/rank Fisher, 1-D loss slice
#   04_publication_summary.py  parameter tables, identifiability heatmap, figures
#   05_run_ablation.py  4-arm ablation (plain / physics / physics+regime / no-BO)
#   06_run_variability.py  cluster-bootstrap 95% CIs (median + bound-pinning)
#   08_paper_alt_figures.py  reframed-paper figures (held-out, trends, eps_r)
#   09_robustness_extensions.py  sloppy spectrum + Fisher rank, DOE, variance
#   10_population_validation.py  split-safe unseen-DEVICE validation
#
# Each stage's exit status is tracked; the script reports which stages failed
# and exits non-zero if any did (no more silent "Done" after failures).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CONDS=("$@")
FAILED=()

run_stage() {  # run_stage "label" cmd...
    local label="$1"; shift
    echo "=== ${label} ==="
    if "$@"; then
        echo "    [ok] ${label}"
    else
        echo "    [FAIL] ${label} (exit $?)"
        FAILED+=("${label}")
    fi
}

run_stage "[1/7] Final fits (07_run_final.py)"            python3 07_run_final.py "${CONDS[@]}"
run_stage "[2/7] Publication summary (04)"                python3 04_publication_summary.py
run_stage "[3/7] Ablation (05_run_ablation.py)"           python3 05_run_ablation.py "${CONDS[@]}"
run_stage "[4/7] Variability + bootstrap CIs (06)"        python3 06_run_variability.py "${CONDS[@]}"
run_stage "[5/7] Reframed-paper figures (08)"             python3 08_paper_alt_figures.py
run_stage "[6/7] Robustness + sloppiness (09)"            python3 09_robustness_extensions.py
run_stage "[7/7] Population validation (10)"              python3 10_population_validation.py "${CONDS[@]}"

if [ "${#FAILED[@]}" -ne 0 ]; then
    echo "PIPELINE INCOMPLETE -- failed stages: ${FAILED[*]}"
    exit 1
fi
echo "Done. See results/ (per-condition *_taofit, publication/, ablation/, variability/, robustness/, population/, paper_alt/)"
