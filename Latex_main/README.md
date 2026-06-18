# Latex_main — IEEE TNANO manuscript draft

`main.tex` is a self-contained IEEEtran journal manuscript built from the
archived pipeline results. Compile from inside this folder so the relative
figure paths resolve (`\graphicspath{{../}}`):

```bash
cd Latex_main
pdflatex main.tex && pdflatex main.tex
```

Figures are referenced in place (no copies):

- `../step02_S1/S1_B6-01-4um-12_regime_overview.png` (regime classification)
- `../results/S1_taofit/fit_quality.png` (example fit + residuals)
- `../results/publication/identifiability_heatmap.png` (Fisher heatmap)

## Red `\todo{}` items that block submission

1. **Bootstrap CIs (Sec. IV-E).** `results/variability/parameter_cis.csv` is
   invalid: `stage3_bayesopt_driver.m:52` resets `rng(0)` on every call, so
   all bootstrap resamples after the first draw identical cycle sets
   (200 draws → 2 unique parameter vectors on every condition, which is also
   why `ci_lo == ci_hi`). Fix the seeding (per-draw seed, or save/restore RNG
   state around the BO call), rerun `06_run_variability.py`, then fill the CI
   table.
2. **`physics_regime_bo` ablation row (Table V).** The archived
   `results/ablation/ablation_summary.csv` predates the regime-conditioned
   variant; rerun `05_run_ablation.py`.
3. **Regime maps / stability for S6–S12 (Table II).** Background run in
   progress; extend the table when `step02_S6..S12` regime files appear.
4. **tox correction (affects everything).** All archived results were run
   with `tox = 5 nm`; the device oxide is **7 nm**. Configs and code defaults
   are now corrected (`stanford_fit/config/*.yaml`,
   `02c_classify_conduction_regimes.py`, MATLAB fallbacks). Any background
   run started before this correction is still using 5 nm and should be
   restarted; refresh every quoted number from the 7 nm rerun. Delete or
   regenerate existing `step02_*/*_regime_map.csv` (07 rebuilds them; 05 now
   rebuilds unconditionally).
5. Author list, affiliations, funding, acknowledgments.

Numbers already in the draft are traceable to:
`results/publication/fit_quality.csv`, `results/ablation/ablation_summary.csv`,
`results/publication/parameter_table.csv`,
`results/S{1..4}_taofit/{identifiability_report,profile_summary}.csv`, and
`step02_S{1..5}/*_regime_{map,stability}.csv`.
