# stanford_fit - TaO-Fit reference implementation

## Setup
- MATLAB R2023a+ with Statistics and Machine Learning Toolbox (`bayesopt`)
- HSPICE on `PATH`
- Python 3.10+ with `numpy`, `pandas`, `matplotlib`, `pyyaml`
- Stanford Verilog-A model in `stanford_fit/templates/rram_v_1_0_0_hspice.va`

## Run
Diagnose one HSPICE call first:

```bash
matlab -batch "cd('stanford_fit/matlab'); diagnose_hspice_once('../../step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv','../config/default_config.yaml');"
```

Then run TaO-Fit:

```bash
python stanford_fit/python/03_run_stanford_fit.py \
  --input step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv \
  --config stanford_fit/config/default_config.yaml \
  --outdir results/S1_taofit
```

or:

```bash
cd stanford_fit/matlab
matlab -batch "main_fit_stanford('../../step02_S1/S1_B6-01-4um-12_representative_curve_FIXED.csv','../config/default_config.yaml','../../results/S1_taofit')"
```

## Outputs
- `priors.mat`
- `fisher_matrix.csv`
- `fisher_report.mat`
- `bo_result.mat`
- `refined.mat`
- `validation.mat`
- `fit_quality.png`
