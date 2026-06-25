# Reconciliation & Implementation Status

Companion to `CODEX_CLAUDE_IMPLEMENTATION_ROADMAP.md`. Records what was
reconciled against the existing work, what was implemented in this pass, the
regenerated numbers, and whether a full pipeline re-run is required.

Canonical manuscript: `Latex_main/main_alt_codex.tex` (+ `Latex_Abstract/build_abstract.py`).
`main.tex` / `main_alt.tex` were treated as archived and **not** edited.

---

## 1. Reconciliation status table (roadmap §3)

Compared against `claude.txt`, `main_alt_codex.tex`, `build_abstract.py`,
`02c`, `06`, `08`, `09`, `results/robustness/`, `results/variability/`,
`results/paper_alt/`.

| Roadmap item | Prior state | Status after this pass |
|---|---|---|
| 2.1 Cycle-level generalization gap (`09` → `generalization_gap.csv`) | already implemented | kept; verified |
| 2.1 C2C vs D2D variance split (`09` → `variance_components.csv`) | already implemented | kept; verified (ICC device frac <0.2) |
| 2.1 **Unseen-DEVICE population validation** | **missing** | **implemented** → `10_population_validation.py`, `results/population/` |
| 2.2 Mechanism classifier common-response BIC + ambiguity | BIC bug (per-transform), eps_r circular | **fixed** in `02c` (common `y=log10|I|`, ΔBIC, `ambiguous`, eps_r as reject-only filter) |
| 2.3 Fisher log-coord double division + SVD/rank | double `/theta`; "10^18–10^66" headline | **fixed** in `stage2_identifiability.m` (no /theta, SVD, numerical rank); `09` reports rank; manuscript reframed |
| 2.4 Profile likelihood vs loss slice | mislabelled "profile likelihood" | **renamed/reframed** → `stage4b_loss_slice.m`, `loss_slice*.csv`, manuscript wording |
| 2.5 Bootstrap CI / bound-pinning consistency (`06`, `ci_consistency.csv`, `bound_railing.csv`) | already implemented | kept; **surfaced in manuscript** (median estimate, 7/192 outside CI, R_s 100% pinned) |
| 2.6 Switching-threshold boundary artifact | 0 V boundary pin (S10 anomaly) | **fixed** in `eval_loss.m` (smooth + margin-exclude + unavailable + dominance warning) |
| §4 Lightweight provenance / fail-loud | partial | **added** fail-loud guards in `08`/`09`/`10`; `run_full_pipeline.sh` tracks failures + runs 08/09/10 |
| §6 Single-model framing (Option A) | implied drop-in model | **stated** (branch-conditioned; compliance post-processed) in Discussion |
| §7 Novelty / prior-art differentiation | thin | **added** "Relation to Prior Work" paragraph |
| §8 Honest/modest claims | several overstated | **corrected** (see §3 below) |
| §5 Hybrid Verilog-A / full simulator / results-dir rearchitecture / big mixed-effects | — | **deferred** (per roadmap); framed as future work |

---

## 2. Files changed

**MATLAB (effective only after a pipeline re-run):**
- `stanford_fit/matlab/stage2_identifiability.m` — Fisher in log coords (no second `/theta`), SVD pseudo-inverse, numerical rank, `ci95_factor`; new fields in `empty_fisher`.
- `stanford_fit/matlab/eval_loss.m` — `detect_threshold` smoothing + boundary-margin exclusion + NaN-when-unavailable; threshold term skipped when unavailable; component logging + dominance warning.
- `stanford_fit/matlab/stage4b_loss_slice.m` — renamed from `stage4b_profile_likelihood.m`; outputs `loss_slice.csv` / `loss_slice_summary.csv`; descriptive `slice_shape` labels; honest docstring.
- `stanford_fit/matlab/main_fit_stanford.m` — calls `stage4b_loss_slice`; `identifiability_report.csv` adds `fisher_ci95_factor`; writes `fisher_rank.csv`.
- `stanford_fit/config/{default,final}_config.yaml` — `run_profile/n_profile` → `run_slice/n_slice` (legacy keys still honored).

**Python (re-analysis; runnable without MATLAB):**
- `02c_classify_conduction_regimes.py` — common-response fit, ΔBIC/ambiguity, eps_r reject-only filter; new map columns.
- `09_robustness_extensions.py` — Fisher numerical rank + `fisher_rank.csv`; A4 reads `loss_slice_summary.csv`; fail-loud guard.
- `08_paper_alt_figures.py` — fail-loud provenance guards.
- `10_population_validation.py` — **new**: population index, leakage-free device splits, unseen-device validation, acceptance checks.
- `05/06/07_*.py` — `run_profile` → `run_slice`.
- `run_full_pipeline.sh` — stage-failure tracking, adds 08/09/10.

**Manuscript / abstract:**
- `Latex_main/main_alt_codex.tex` — abstract, contributions, mechanism methods, loss/threshold, Fisher methods, generalization results (false IQR claim removed), new §"Unseen-Device Population Validation", bound-pinning, DOE multiplicity, Schottky→barrier-limited wording, framing/compliance caveats, "Relation to Prior Work", conclusion. Compiles clean (0 undefined refs).
- `Latex_Abstract/build_abstract.py` — same honesty fixes; title `TaOₓ` (was literal `TaO$_x$`); added Fig. 11 (population).

---

## 3. Regenerated numbers (re-analysis only; consistent with current fits)

- **Unseen-device validation (NEW):** 545 device records, 10,871 good cycles; 2,180 unseen SET + 2,180 unseen RESET cycles. Unseen-device median 0.580 (SET) / 0.861 (RESET) vs same-device 0.542 / 0.800 → gap +0.038 / +0.061 decade. All acceptance checks pass (no leakage; fitted device train-only; ≥1 unseen test device per condition).
- **Generalization (corrected claim):** in-sample inside held-out IQR only ~49% (SET) / ~25% (RESET) of conditions — NOT "every condition". S1 RESET outlier: +0.31 decade (+45%), 18% within IQR.
- **Bound-pinning:** R_s 100% pinned; Vel0_set/res ≈21–24%. Full-budget optimum outside bootstrap CI for 7/192.
- **Fisher:** numerical rank ≈ 8–14 of 16 (rank deficient); resolvable range ~10^7–10^14 — reported as rank, not "10^18–10^66".
- **Mechanism (corrected):** LRS ohmic-dominant (12/12). HRS barrier-limited but ambiguous: pre-SET HRS Schottky-dominant 9/12; post-RESET HRS full-window near-ohmic in 8/12, Schottky-like in 4/12; 33/141 windows flagged `ambiguous`. Schottky-window cycle-median εr 5.3–23.1 in the 10 conditions where a credible window appears.
- **DOE:** only V0_SET significant (O2, power; R²≈0.75); V0_RESET R²≈0.61, Rs R²≈0.24 (none significant); lack-of-fit only "failed to detect".

> These refresh again after a full MATLAB/HSPICE re-run, because the underlying
> fits change with the `eval_loss.m` threshold fix and the new regime weighting.

---

## 4. Do I need to run the full pipeline? **YES.**

The MATLAB fixes (`eval_loss.m` switching threshold, `stage2_identifiability.m`
Fisher, `stage4b_loss_slice.m`) change the archived fits / identifiability and
must be regenerated with MATLAB + HSPICE; this is also required to confirm the
S10 objective is no longer anomalous.

```bash
bash run_full_pipeline.sh        # 07 (incl. 02c) → 04 → 05 → 06 → 08 → 09 → 10
cd Latex_main && pdflatex main_alt_codex.tex && pdflatex main_alt_codex.tex
cd ../Latex_Abstract && python3 build_abstract.py
```

**Re-analysis only (no MATLAB; already run in this pass to produce the §3 numbers):**

```bash
for c in S1 S2 S3 S4 S5 S6 S7 S8 S9 S10 S11 S12; do \
  python3 02c_classify_conduction_regimes.py \
    --rep-csv "$(ls step02_$c/*_representative_curve_FIXED.csv)" \
    --output-dir step02_$c --ensemble-csv step02_$c/${c}_cycle_ensemble.csv; done
python3 06_run_variability.py --reanalyze
python3 08_paper_alt_figures.py
python3 09_robustness_extensions.py
python3 10_population_validation.py
```

After the full pipeline run, refresh the manuscript's fit-dependent numbers
(Table II RMSE/DW, generalization medians, mechanism percentages, εr range,
Fisher rank) from the regenerated CSVs.
