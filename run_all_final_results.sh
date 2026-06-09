#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

RAW_DIR="${RAW_DIR:-$ROOT/raw_data}"
VA_FILE="${VA_FILE:-$ROOT/rram_v_1_0_0_hspice.va}"
CONFIG="${CONFIG:-$ROOT/stanford_fit/config/default_config.yaml}"
HSPICE_CMD="${HSPICE_CMD:-hspice}"
MATLAB_BIN="${MATLAB_BIN:-matlab}"

# HSPICE FlexLM: the first server in the site list (waynelic01) is unresponsive,
# so every hspice call waits ~20s for it to time out before falling back -- that
# alone turns each eval from ~0.4s into ~40s. Pin the live server(s) first and
# cap the dead-server connect timeout to 0.3s so a future outage costs little.
export SNPSLMD_LICENSE_FILE="${SNPSLMD_LICENSE_FILE:-27020@waynelic02.ad.wayne.edu,27020@waynelic03.ad.wayne.edu}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE:-$SNPSLMD_LICENSE_FILE}"
export FLEXLM_TIMEOUT="${FLEXLM_TIMEOUT:-300000}"

RUN_BASELINE="${RUN_BASELINE:-1}"
RUN_TAOFIT="${RUN_TAOFIT:-1}"

MIN_GOOD_CYCLES="${MIN_GOOD_CYCLES:-5}"
MIN_OVERLAP_CYCLES="${MIN_OVERLAP_CYCLES:-5}"
REPRESENTATIVE_MODE="${REPRESENTATIVE_MODE:-medoid-cycle}"

if [[ "$#" -gt 0 ]]; then
  CONDITIONS=("$@")
else
  CONDITIONS=(S1 S2 S3 S4 S5 S6 S7 S8 S9 S10 S11 S12)
fi

echo "=== Deleting previous results ==="
rm -rf "$ROOT"/results "$ROOT"/step01_* "$ROOT"/step02_* "$ROOT"/step03_*

SUMMARY_DIR="$ROOT/results"
SUMMARY="$SUMMARY_DIR/final_results_summary.csv"
mkdir -p "$SUMMARY_DIR"
printf "condition,representative_csv,baseline_dir,baseline_metrics,taofit_dir,taofit_parameters\n" > "$SUMMARY"

for CONDITION in "${CONDITIONS[@]}"; do
  INPUT_DIR="$RAW_DIR/$CONDITION"
  STEP01_DIR="$ROOT/step01_$CONDITION"
  STEP02_DIR="$ROOT/step02_$CONDITION"
  BASELINE_DIR="$ROOT/step03_${CONDITION}_baseline"
  TAOFIT_DIR="$ROOT/results/${CONDITION}_taofit"

  if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Missing input folder: $INPUT_DIR" >&2
    exit 1
  fi

  echo
  echo "=== $CONDITION: extract clean cycles ==="
  python3 "$ROOT/01_extract_clean_cycles.py" \
    "$INPUT_DIR" \
    --output-dir "$STEP01_DIR"

  echo "=== $CONDITION: select best representative device/curve ==="
  python3 "$ROOT/02_select_device_representative_curve.py" \
    --step01-dir "$STEP01_DIR" \
    --output-dir "$STEP02_DIR" \
    --representative-mode "$REPRESENTATIVE_MODE" \
    --min-good-cycles "$MIN_GOOD_CYCLES" \
    --min-overlap-cycles "$MIN_OVERLAP_CYCLES"

  REP_CSV="$(find "$STEP02_DIR" -maxdepth 1 -name '*_representative_curve_FIXED.csv' -print -quit)"
  if [[ -z "$REP_CSV" ]]; then
    echo "No representative curve found in $STEP02_DIR" >&2
    exit 1
  fi

  BASELINE_METRICS=""
  if [[ "$RUN_BASELINE" == "1" ]]; then
    echo "=== $CONDITION: run Stanford baseline HSPICE fit ==="
    python3 "$ROOT/03_run_stanford_baseline.py" \
      --rep-csv "$REP_CSV" \
      --va "$VA_FILE" \
      --deck-mode butterfly \
      --output-dir "$BASELINE_DIR" \
      --hspice-cmd "$HSPICE_CMD" \
      --auto-set-compliance-current
    BASELINE_METRICS="$BASELINE_DIR/03_fit_metrics.csv"
  fi

  TAOFIT_PARAMETERS=""
  if [[ "$RUN_TAOFIT" == "1" ]]; then
    echo "=== $CONDITION: run final TaO-Fit optimization ==="
    python3 "$ROOT/stanford_fit/python/03_run_stanford_fit.py" \
      --input "$REP_CSV" \
      --config "$CONFIG" \
      --outdir "$TAOFIT_DIR" \
      --matlab-bin "$MATLAB_BIN"
    TAOFIT_PARAMETERS="$TAOFIT_DIR/refined.mat"
  fi

  printf "%s,%s,%s,%s,%s,%s\n" \
    "$CONDITION" "$REP_CSV" "$BASELINE_DIR" "$BASELINE_METRICS" "$TAOFIT_DIR" "$TAOFIT_PARAMETERS" \
    >> "$SUMMARY"
done

echo
echo "All requested conditions completed."
echo "Summary: $SUMMARY"

echo
echo "=== Publication tables + figures ==="
python3 "$ROOT/04_publication_summary.py"

echo "=== Ablation harness ==="
python3 "$ROOT/05_run_ablation.py" "${CONDITIONS[@]}"

echo "=== Cross-cycle variability (bootstrap CIs) ==="
python3 "$ROOT/06_run_variability.py" --bootstrap-n 200 "${CONDITIONS[@]}"

echo
echo "Publication pipeline complete. Artefacts in $ROOT/results/{publication,ablation,variability}"