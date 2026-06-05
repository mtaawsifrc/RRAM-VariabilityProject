# Run Instructions

1. Install Python deps: `python3 -m pip install numpy pandas matplotlib pyyaml`
2. Put MATLAB and HSPICE on `PATH`.
3. Extract clean cycles: `bash run_01.sh`
4. Select representative curve: `bash run_02.sh`
5. Run Stanford baseline: `bash run_03.sh`
6. Diagnose one TaO-Fit HSPICE call: `matlab -batch "cd('stanford_fit/matlab'); diagnose_hspice_once('../../step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv','../config/default_config.yaml');"`
7. Run TaO-Fit: `bash stanford_fit/examples/run_S1_proof_of_concept.sh`
8. Check outputs in `step01_S1/`, `step02_S1/`, `step03_S1_baseline/`, and `results/`.
