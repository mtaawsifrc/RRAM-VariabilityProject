#!/usr/bin/env bash
set -euo pipefail

# Example 1: use your existing step02 representative curve
python3 03_fit_stanford_rram_hspice.py \
  --rep-csv step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv \
  --va /home/hm5701/Documents/PINN/Variability_Project/rram_v_1_0_0_hspice.va \
  --output-dir step03_S1_fit \
  --hspice-bin hspice \
  --compliance-current 0 \
  --pwl-dt 1e-6

# Example 2: shorter debug run
# python3 03_fit_stanford_rram_hspice.py \
#   --rep-csv step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv \
#   --va /home/hm5701/Documents/PINN/Variability_Project/rram_v_1_0_0_hspice.va \
#   --output-dir step03_S1_fit_debug \
#   --hspice-bin hspice \
#   --skip-sensitivity \
#   --stage1-rounds 2 --stage1-candidates 8 \
#   --stage2-rounds 2 --stage2-candidates 8 \
#   --stage3-rounds 2 --stage3-candidates 8 \
#   --joint-rounds 3 --joint-candidates 12
