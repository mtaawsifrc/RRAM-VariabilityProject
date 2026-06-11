# Suggested Algorithmic Changes — Multi-Mechanism Physics Priors & Journal Readiness

**Status: IMPLEMENTED (2026-06-11).** Mapping:
- Change 1 → `02c_classify_conduction_regimes.py` (named 02c, not 00; runs after step 02)
- Change 2 → `stanford_fit/matlab/stage1_extract_priors.m` (`regime_map_csv` config key)
- Change 3 → `stanford_fit/matlab/eval_loss.m` (`mechanism_weighting`, `nonbulk_weight`)
- Change 4 → `stage2_identifiability.m` (3-level class), new `stage4b_profile_likelihood.m`
  (`run_profile`, `n_profile`), `stage3_bayesopt_driver.m` (`freeze_params`, `auto_active`
  + `identifiability_csv`), `main_fit_stanford.m` writes `identifiability_report.csv`
- Change 5 → `stanford_fit/config/final_config.yaml` + `07_run_final.py` (Fisher+profile)
  and `06_run_variability.py` (bootstrap CIs with ensemble)
- Change 6 → `06_run_variability.py` (regime maps, mechanism stability, dominant-mechanism map)
- Change 7 → not implemented (recommended against, as stated below)
- Full pipeline: `run_full_pipeline.sh`; see `MD Files/RUN_INSTRUCTIONS.md`

Original proposal below, kept for reference.

## Context (read first)

- Pipeline: `01_extract_clean_cycles.py` → `02_select_device_representative_curve.py` (+ `02b_build_cycle_ensemble.py`) → `03_run_stanford_baseline.py` → `stanford_fit/matlab/main_fit_stanford.m` (Stage 1 priors → Stage 2 Fisher → Stage 3 BayesOpt → Stage 4 refine → Stage 5 validate) → `04_publication_summary.py`, `05_run_ablation.py`, `06_run_variability.py`.
- Forward model: Stanford-PKU Verilog-A, single conduction law `I = I0·exp(-gap/g0)·sinh(V/V0)`; gap dynamics `∝ Vel0·exp(-qEa/kT)·sinh(gamma·a0/tox·qV/kT)`.
- Current physics priors (`stanford_fit/matlab/stage1_extract_priors.m`): **only two fits** —
  1. `fit_lrs_sinh` on a hardcoded window (SET return sweep, 0.02 V < V < 0.6 V, below 0.95·Imax) → `I0`, `V0` priors.
  2. `fit_pf_priors`: single Poole-Frenkel regression `ln(I/V)` vs `√V` on a hardcoded window (0.3 V < |V| < 0.9·Vset) → `gamma0`, `Ea` priors.
- **Gap vs. the plan:** `MD Files/**Core Idea**.md` claims the work uses *Ohmic, Schottky, Poole-Frenkel, and Fowler-Nordheim* conduction analysis to guide fitting. Only PF is implemented. `Literature/01.pdf` (our MWSCAS 2025 paper, Chowdhury et al.) shows experimentally that the dominant mechanism **changes with voltage window, resistance state (HRS/LRS), and oxygen partial pressure**: e.g. high-P_O2 HRS = ohmic (0–0.3 V) → FN (0.3–0.625 V); low-P_O2 HRS = PF; LRS = PF/Schottky (low P_O2) or PF/ohmic (high P_O2).
- Key structural fact: **Schottky and FN have no direct mapping onto Stanford model parameters** (the model has one bulk hopping/tunneling current law). So the right adoption is *regime segmentation + regime-conditioned priors + model-validity flags*, NOT four parallel priors.

---

## Change 1 — New Stage 0: automatic conduction-regime classifier (highest priority)

**New file:** `stanford_fit/matlab/stage0_conduction_regimes.m` (or Python `00_classify_conduction_regimes.py` run after step 02 — Python preferred so step 03 baseline can also consume it).

**Input:** representative curve CSV (and optionally the per-cycle ensemble from `02b`).
**Algorithm:**
1. Split the butterfly curve into the four state segments (reuse logic of `split_butterfly_sweeps()` at `03_run_stanford_baseline.py:473`): `SET_HRS_PRE`, `SET_LRS_POST`, `RESET_LRS_PRE`, `RESET_HRS_POST`.
2. For each segment, on sliding voltage windows (e.g. minimum 8 points, expand/contract by R² plateau), run the four standard linearization regressions:
   - **Ohmic:** `ln I` vs `ln V`, accept if slope ∈ [0.9, 1.1].
   - **Poole-Frenkel:** `ln(I/V)` vs `√V`, slope > 0.
   - **Schottky:** `ln I` vs `√V`, slope > 0.
   - **Fowler-Nordheim:** `ln(I/V²)` vs `1/V`, slope < 0.
3. Select dominant mechanism per window by **BIC** (not raw R² — PF and Schottky are nearly collinear; BIC + the physical-slope check below breaks ties).
4. **Physical sanity check (this is what makes it a *physics* prior, not curve shape):** from the PF slope `s = q/(kT)·√(q/(π·ε_r·ε0·t_ox))`, invert for dynamic permittivity `ε_r,dyn`; accept PF only if `1 < ε_r,dyn ≤ ε_r,optical²` plausible range for TaOx (≈ 4–30). Same trick distinguishes Schottky (slope formula differs by factor 2 inside the sqrt). This is exactly the discriminator used in the conduction-mechanism literature (Chiu 2014, ref [20] of 01.pdf).
5. **Output:** `regime_map.csv` with columns `branch, state, v_lo, v_hi, mechanism, slope, intercept, r2, bic, eps_r_dyn, n_points` + a publication plot that auto-reproduces Fig. 4/5 of the MWSCAS paper per sample.

**Why:** turns the MWSCAS analysis (done manually per device) into an automated, per-sample (S1–S12) front-end. This alone is a paper figure and the novelty hook.

## Change 2 — Regime-conditioned priors in `stage1_extract_priors.m`

Replace the **hardcoded** voltage windows with windows from `regime_map.csv`:
- `fit_lrs_sinh` window ← the segment classified **ohmic** in LRS (sinh ≈ linear there; current hardcode 0.02–0.6 V can straddle non-ohmic data).
- `fit_pf_priors` window ← the segment classified **PF** in HRS (currently fixed 0.3–0.9·Vset regardless of whether PF actually dominates there). Fit `gamma0`/`Ea` priors per branch from its own PF window.
- If **no PF window exists** for a branch (e.g. high-P_O2 HRS is ohmic→FN): fall back to config prior `gamma0_prior` with **inflated sigma** (e.g. ×2) and set a flag `pf_prior_available = false` in the priors struct. Do NOT silently fit PF to FN data (that is what can happen now).
- Add to the priors struct: `priors.regimes` (the map) and `priors.model_validity` flags per branch/state: `true` where dominant mechanism ∈ {ohmic, PF} (representable by the Stanford current law), `false` where Schottky/FN dominate.

## Change 3 — Mechanism-aware loss weighting in `eval_loss.m`

- Add per-point weights `w_i`: `1.0` inside ohmic/PF-classified windows, `w_low` (config key `nonbulk_weight`, default `0.3`) inside Schottky/FN-classified windows; multiply the variance-scaled residuals `rS`, `rR` by `w_i`.
- Report **both** weighted and unweighted MAE/RMSE in Stage 5 so the paper can state: "the compact model is fitted on its physically valid domain; residuals outside it are reported, not hidden."
- Config switch `mechanism_weighting: 1|0` so the ablation script can quantify its effect (3-way ablation: plain priors / physics priors / physics priors + regime weighting).

## Change 4 — Make identifiability *operational* (the claimed key novelty)

Currently Stage 2 Fisher (`stage2_identifiability.m`, now `run_fisher: 1`) is informational; active parameters are config-driven. Change:
1. After Fisher, classify each parameter: `rel_sigma < 0.5` → identifiable; `0.5–2` → weakly identifiable; `> 2` → non-identifiable.
2. **Auto-freeze non-identifiable parameters at their prior mean** and drop them from `active_names` in `stage3_bayesopt_driver.m` (`resolve_active_names()` reads the Fisher report when `auto_active: 1`). Keep manual `active_params` override.
3. Add **profile likelihood** for the surviving parameters after Stage 4 (1-D scan ±2σ around the optimum, refit nothing, just re-evaluate loss; ~15 HSPICE calls/parameter): Fisher is local/linearized and misses practical non-identifiability; profile likelihood is the journal-grade evidence. Output `profile_likelihood.csv` + flat-vs-curved plots.
4. **Cross-link with Change 1:** for a device whose HRS is FN-dominated, expect `gamma0`/`Ea` to lose identifiability → the paper's headline table becomes *mechanism-dependent identifiability*: "which Stanford parameters are extractable depends on the deposition stoichiometry." That is a genuinely novel, defensible claim no curve-fitting paper makes.

## Change 5 — Turn on the uncertainty machinery for headline results

- Final runs must use the per-cycle ensemble (`02b_build_cycle_ensemble.py`) with `run_loco: 1`, `run_bootstrap: 1` (config currently defaults 0/0 → CIs are NaN). The Core Idea promises "confidence/uncertainty for extracted parameters" — currently only delivered if these are flipped on.
- Headline table per sample: parameter, posterior/best value, bootstrap 95% CI, Fisher rel_sigma, profile-likelihood verdict, identifiable (Y/N).

## Change 6 — Variability/stoichiometry trend analysis (ties to `06_run_variability.py`)

- Extend the cross-sample summary: plot extracted (identifiable-only) parameters and the **regime map** vs sample/deposition condition (S1–S12). Expected story per MWSCAS: oxygen-rich → FN/ohmic HRS, broader C2C spread; oxygen-poor → PF HRS.
- Add mechanism-map agreement across cycles (classify each cycle in the ensemble, report mechanism stability %) — a new variability metric that no Stanford-fitting paper reports.

## Change 7 (optional, only if reviewers demand model extension)

Parallel-conduction Verilog-A extension: add Schottky `I_sch ∝ exp(√V·c1)` and FN `I_fn ∝ V²·exp(-c2/V)` branches in parallel with the filament law, gated by gap state. High effort, high HSPICE-convergence risk, and dilutes the "Stanford-compatible parameter extraction" selling point. **Recommend against for this paper**; mention as future work.

---

## Honest answers to "are we doing what we planned?"

| Core Idea claim | Status |
|---|---|
| Ohmic/Schottky/PF/FN guide the fitting | **Not implemented** — only PF (+ implicit ohmic via sinh). Changes 1–3 fix this. |
| Identifiability checked before optimizing | Partially — Fisher computed (`run_fisher: 1`) but **does not influence** the active set. Change 4 fixes this. |
| Confidence/uncertainty reported | Machinery exists (bootstrap/LOCO) but **off by default**; CIs NaN unless ensemble path used. Change 5. |
| Physics priors beat black-box | Ablation hook exists (`prior_mode: plain`, `05_run_ablation.py`) — keep; add regime-weighting arm. |
| Validation across cycles | LOCO exists, off by default. Change 5. |

## Known pitfalls to respect while implementing

- Verilog-A RESET caveat: negative bias forces `gamma_ini = 16`, so `gamma0_res` does not act symmetrically to `gamma0_set` (see ALGORITHM_WALKTHROUGH “Stanford Verilog-A Model Logic”). Any RESET-side PF prior must acknowledge this.
- Exclude the SET compliance plateau (current pinned at ~5e-4 A) from **all** regime regressions, as `fit_lrs_sinh` already does (`< 0.95·Imax`).
- PF vs Schottky regressions are nearly collinear on narrow windows — always apply the ε_r,dyn physical check (Change 1 step 4) before claiming either.
- `MD Files/ALGORITHM_WALKTHROUGH.md` is stale where it says `run_fisher: 0` (config now `1`) and omits scripts 02b/04/05/06 — update docs after implementing.

## Suggested implementation order

1. Change 1 (regime classifier, standalone, testable against MWSCAS Fig. 4/5).
2. Change 2 (rewire stage1 windows) + rerun one sample end-to-end.
3. Change 4 (auto-active from Fisher + profile likelihood).
4. Change 5 (ensemble + bootstrap/LOCO on all 12 samples — long compute, queue early).
5. Change 3 (loss weighting) + extended ablation.
6. Change 6 (cross-sample trends, paper figures).
