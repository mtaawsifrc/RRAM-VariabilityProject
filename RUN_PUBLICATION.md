# Publication pipeline — runbook

End-to-end steps to produce the final, publication-grade results (point
estimates + identifiability + cross-cycle CIs + ablation) for all 12 conditions.

## 0. Prerequisites (once)
- `hspice`, `matlab`, `python3` on `PATH` (verified present).
- Python: `numpy pandas scipy matplotlib`.
- Run everything from the project root.

> **Runtime reality (read first).** Each HSPICE call recompiles the Verilog-A
> model (~15–20 s); a fit makes hundreds of calls, so wall-time is dominated by
> that, not the math. Your earlier 8-min/12-condition run had a *warm compiled
> model cache* — restore that (don't clear it between runs) or the times below
> balloon ~100×. Verify with a single condition before launching all 12.

---

## 1. Core fit — point estimates + Fisher identifiability
Fits the representative curve per condition and (now) computes the Fisher /
Cramér–Rao bound **at the fitted optimum** → `results/<cond>_taofit/`.

```bash
RUN_BASELINE=1 RUN_TAOFIT=1 ./run_all_final_results.sh         # all 12
./run_all_final_results.sh S1                                  # one condition (test first)
```
Outputs per condition: `refined.mat` (θ), `fisher_matrix.csv` + `fisher_report.mat`
(`F`, `eigvals`, `eff_sigma`, `rel_sigma`, `well_idx`/`nonid_idx`), `validation.mat`,
`fit_quality.png`. `run_fisher: 1` is set in the config.

## 2. Aggregate → publication tables + figures
Pure post-processing of step 1 (no HSPICE).

```bash
python3 04_publication_summary.py
```
Writes `results/publication/`: `parameter_table.csv` (θ ± Fisher rel. uncertainty,
identifiable flag, Fisher condition number), `fit_quality.csv`,
`identifiability_heatmap.{png,pdf}` (the centrepiece novelty figure),
`fit_quality.{png,pdf}`, `key_parameters.{png,pdf}` — all PNG **and** vector PDF.

## 3. Ablation — value of physics-guided BO
Refits each condition 3 ways (physics+BO, plain+BO, physics-no-BO).

```bash
python3 05_run_ablation.py            # all 12   (3 × full fits each)
python3 05_run_ablation.py S1 S2      # subset
```
Writes `results/ablation/ablation_summary.csv` and `ablation_rmse.{png,pdf}`.

## 4. Cross-cycle variability — bootstrap parameter CIs
Builds each device's per-cycle ensemble and runs a cluster bootstrap over cycles
→ empirical 95% CIs on the extracted parameters (the "variability" result).

```bash
python3 06_run_variability.py S1                    # one condition first (recommended)
python3 06_run_variability.py --bootstrap-n 200     # all 12, 200 resamples
python3 06_run_variability.py --with-loco S1        # also leave-one-cycle-out (slow)
```
Writes `results/variability/parameter_cis.csv` (θ, CI lo/hi, CV per param/condition)
and `parameter_cv.{png,pdf}`. **Slowest stage:** `bootstrap_n × (8+24)` fits per
condition — start with one condition / `--bootstrap-n 100`.

---

## Config flags ( `stanford_fit/config/default_config.yaml` )
| Flag | Default | Meaning |
|------|---------|---------|
| `run_fisher` | 1 | Fisher/CRLB at the fitted optimum (step 1) |
| `prior_mode` | physics | `plain` = uninformative priors (ablation) |
| `defaults_only` | 0 | 1 = skip BO/refine, return prior mean (ablation) |
| `run_bootstrap` / `run_loco` | 0 | enabled by `06_run_variability.py`; need the ensemble CSV |
| `bootstrap_n` | 120 | bootstrap resamples for CIs |
| `bootstrap_bo_n_init/iter`, `loco_bo_n_init/iter` | 8 / 24 | reduced budget per resample |

The ablation/variability runners write their own temp configs — you normally
edit nothing here.

## Paper-ready artefacts
- **Fig (identifiability):** `results/publication/identifiability_heatmap.pdf`
- **Fig (parameters vs condition):** `results/publication/key_parameters.pdf`
- **Fig (fit quality + Durbin–Watson):** `results/publication/fit_quality.pdf`
- **Fig (ablation):** `results/ablation/ablation_rmse.pdf`
- **Fig (cross-cycle CV):** `results/variability/parameter_cv.pdf`
- **Tables:** `parameter_table.csv`, `ablation_summary.csv`, `parameter_cis.csv`

## Known limitations to disclose in the paper
- Fit error is ~0.5 (SET) / ~0.7 (RESET) decades with Durbin–Watson ≪ 2
  (systematic RESET-branch lack-of-fit) — report it; it's a single-polarity
  Stanford-model limitation, not a bug.
- Bootstrap is a *cluster bootstrap over cycles of the representative device*;
  it captures cycle-to-cycle, not device-to-device, variability.
