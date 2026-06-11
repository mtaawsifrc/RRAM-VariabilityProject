# Run Instructions

## Setup
1. Install Python deps: `python3 -m pip install numpy pandas scipy matplotlib pyyaml`
2. Put MATLAB and HSPICE on `PATH`.

## Per-condition data preparation (already done for S1-S12)
3. Extract clean cycles: `bash run_01.sh` (edit paths for other conditions)
4. Select representative curve: `bash run_02.sh`
5. (Optional) Stanford baseline sanity check: `bash run_03.sh`

## Full and final (publication) results
6. `bash run_full_pipeline.sh` — runs, for all 12 conditions:
   - `07_run_final.py`: per-cycle ensemble (02b) + conduction-regime
     classification (02c) + final TaO-Fit with regime-conditioned priors,
     mechanism-aware loss weighting, Fisher identifiability at the optimum,
     and Stage-4b profile likelihood → `results/<cond>_taofit/`
     (`identifiability_report.csv` is the headline extractability table)
   - `04_publication_summary.py`: parameter tables + figures →
     `results/publication/`
   - `05_run_ablation.py`: 4-arm ablation (plain BO / legacy physics /
     physics+regime / no-BO) → `results/ablation/`
   - `06_run_variability.py`: cluster-bootstrap 95% CIs, regime maps,
     cycle-to-cycle mechanism stability, dominant-mechanism map →
     `results/variability/`
   Subsets: `bash run_full_pipeline.sh S1 S2`.

## Individual tools
- Regime classifier only:
  `python3 02c_classify_conduction_regimes.py --rep-csv step02_S1/..._representative_curve_FIXED.csv --output-dir step02_S1 [--ensemble-csv step02_S1/S1_cycle_ensemble.csv]`
- One-off TaO-Fit: `bash stanford_fit/examples/run_S1_proof_of_concept.sh`
  (uses `stanford_fit/config/default_config.yaml`; set `regime_map_csv`,
  `run_profile` etc. there or use `config/final_config.yaml`)
- Diagnose one HSPICE call:
  `matlab -batch "cd('stanford_fit/matlab'); diagnose_hspice_once('../../step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv','../config/default_config.yaml');"`
- Two-pass refit with non-identifiable parameters frozen: set
  `auto_active: 1` and `identifiability_csv: results/S1_taofit/identifiability_report.csv`
  in the config and re-run the fit.
