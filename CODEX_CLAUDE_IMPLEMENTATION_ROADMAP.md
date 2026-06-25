# Agreed Verdict Triage for Codex/Claude Code

This file replaces the earlier broad implementation roadmap. The earlier version was technically useful, but too large and too “rebuild the whole project” for the current situation.

Use this document as a focused instruction brief: keep only the verdict points I agree with, including partial agreement. Defer or remove everything else.

Data constraint:

- Use only the data currently available in this repo.
- Do not assume new temperature sweeps, ramp-rate sweeps, compliance-current sweeps, pulse data, retention data, or new fabrication runs.

Canonical manuscript:

- The submission manuscript is `Latex_main/main_alt_codex.tex`; its title matches `Latex_Abstract/main_abstract.docx`.
- `Latex_main/main.tex` and `Latex_main/main_alt.tex` are older variants that currently duplicate much of the same content (all three now carry the sloppy-spectrum and DOE/variance text).
- When manuscript text must change, edit ONLY `main_alt_codex.tex` and `Latex_Abstract/build_abstract.py`. Do not edit the other two `.tex` files in parallel; treat them as archived.

---

## 1. Core verdict I agree with

The roadmap’s technical diagnoses were mostly correct, but the strategy was miscalibrated. Treat it as a correctness checklist, not a literal multi-phase rebuild.

The revised priority is:

1. Fix the correctness issues that can directly hurt reviewer trust.
2. Add or strengthen the one high-value validation improvement: population/device-level validation.
3. Reconcile the roadmap with work already done in `claude.txt`, `main_alt.tex`, the abstract builder, and robustness scripts.
4. Defer large architectural/model-invention work unless the paper deliberately pivots.

---

## 2. Do now: high-value correctness fixes

These are worth doing because they affect scientific validity and reviewer confidence.

### 2.1 Fix split-safe population validation

Agreed verdict:

- This is the highest-value remaining improvement.
- The paper is most vulnerable if it appears to use only one representative device per condition or only about 4% of available cycles.
- A population/device-level split is more acceptance-moving than large infrastructure cleanup.

Instruction for Codex/Claude:

Already done (verify and cite — do NOT redo):

- Cycle-level, per-condition generalization gap exists: `results/robustness/generalization_gap.csv`, written by `09_robustness_extensions.py`.
- Cycle-to-cycle vs device-to-device variance split from the replicated center points (S9-S12) exists: `results/robustness/variance_components.csv`.

Still missing (this is the actual high-value work):

- True unseen-DEVICE validation across the broader device population. The current test only scores other cycles of the SAME fitted device; it never holds out whole devices. This is what requires a population/device index.

Instruction for Codex/Claude:

- Build a population index over all available devices and cycles (one row per cycle, one per device); the current flow uses ~one device per condition (~4% of cycles).
- Add deterministic, seeded device-level train/validation/test splits per condition. Keep all cycles of a device in one split (no device leakage).
- Ensure representative-cycle/medoid selection uses TRAINING devices/cycles only.
- Ensure held-out validation excludes the selected medoid cycle and all fitted cycles.
- Report TWO distinct numbers: (a) same-device cycle hold-out (already exists) and (b) unseen-device validation (new). Do not conflate them.
- Report per-condition and per-branch gaps, not only averages; discuss outliers such as weak S1 RESET generalization explicitly.

Acceptance checks:

- No `(sample_id, device_id)` appears in more than one split.
- The selected medoid is absent from the held-out files.
- Unseen-device validation contains only devices never used for selection or fitting.

Keep the implementation pragmatic:

- Do not redesign the whole repo.
- Do not add a huge new framework.
- Add the minimum scripts/changes needed to prove no leakage and summarize population-scale validation.

### 2.2 Fix mechanism classification language and statistics

Agreed verdict:

- The current transformed-space BIC comparison is a real methodological weakness.
- Mechanism labels should be cautious because the current dataset is room-temperature DC only.

Instruction for Codex/Claude:

- Compare candidate mechanisms in a common response space, preferably log-current.
- Add ambiguity labels when candidates are close.
- Use dynamic permittivity as a plausibility check, not circular proof.
- Replace language like “confirms Schottky” with:
  - “consistent with Schottky-like behavior”
  - “barrier-limited candidate”
  - “PF-like”
  - “mechanism-aware model-adequacy diagnostic”

Concrete fix (`02c_classify_conduction_regimes.py`, currently lines ~62-68):

- The bug: each candidate is regressed on a DIFFERENT response (`ln I`, `ln(I/V)`, `ln(I/V^2)`), so their BIC values are not directly comparable.
- Fit ALL candidates to one common response `y = log10(|I| + I_floor)` on the SAME point set in each voltage window:
  - ohmic / power law: `y = a + n*log10(|V|)`
  - Schottky-like:    `y = a + b*sqrt(|V|)`
  - PF-like:          `y = a + log10(|V|) + b*sqrt(|V|)`
  - FN-like:          `y = a + 2*log10(|V|) - b/|V|`
- Use `abs(V)`, exclude points with `abs(V) < V_min` and compliance plateaus, require a minimum number of points per window.
- Compute AIC/BIC on that common `y`; add `delta_bic` and a `mechanism_second` column. If `delta_bic` is below a configurable threshold (e.g. 6), label the window `ambiguous`.

Do not claim microscopic mechanism certainty from this dataset.

### 2.3 Fix Fisher/identifiability reporting

Agreed verdict:

- The Fisher scaling issue is real.
- Exact “37 orders of magnitude” language is strategically risky because such spectra indicate numerical rank deficiency/sloppiness, not a precise measurable span.

Instruction for Codex/Claude:

- Compute Fisher uncertainty in log-parameter coordinates correctly.
- Use SVD/rank reporting.
- Report “rank deficient,” “sloppy,” “one/few stiff directions,” and identifiable combinations.
- Retire exact headline language such as “37 orders of magnitude” unless carefully framed as an approximate numerical sloppiness indicator.

Concrete fix (`stanford_fit/matlab/stage2_identifiability.m`, currently ~line 56):

- The bug: sensitivities `S_ij = d r_i / d log(theta_j)` are already in log-parameter coordinates, then the code divides AGAIN: `rel_sigma = eff_sigma ./ theta0`. Remove that division.
- Correct sequence (with `z_j = log(theta_j)`):
  - `F = S' * W * S`
  - `Cov_z = pinv(F)` (via SVD)
  - `sigma_logtheta = sqrt(diag(Cov_z))`  ← this IS the relative uncertainty; do NOT divide by `theta`.
  - approximate 95% multiplicative CI factor = `exp(1.96 * sigma_logtheta)`
- Report numerical rank and the singular-value spectrum. A singular value below ~1e-16 of the top one is numerical noise, not a measurable range — so report rank deficiency, not an exact order count.

Coordinate with Section 3 (reconciliation): the "37 orders" / sloppy-spectrum figure (`results/robustness/sloppy_spectrum.*`) was recently ADDED as novelty and currently appears in all three manuscript variants. Softening it here means also editing that figure's caption/text in the canonical `main_alt_codex.tex` so the figure and the cautious wording do not contradict each other.

Preferred manuscript framing:

- Keep the qualitative sloppiness result.
- Keep the stiff-direction/eigenvector interpretation.
- Do not overstate exact condition-number magnitudes.

### 2.4 Fix or rename profile likelihood

Agreed verdict:

- If nuisance parameters are not reoptimized, it is not a true profile likelihood.

Instruction for Codex/Claude:

- Either implement true profile likelihood with nuisance reoptimization, or rename the current output to `loss_slice`.
- Do not use formal profile-likelihood confidence thresholds on a fixed-parameter loss slice.
- If only S1-S4 have profiles, state that clearly.

### 2.5 Reconcile bootstrap CIs, bound pinning, and plotted estimates

Agreed verdict:

- Bootstrap intervals and plotted point estimates must be internally consistent.
- Bound pinning is not a nuisance detail; it is evidence of weak/non-identifiability.

Already done (verify — do NOT redo): `06_run_variability.py` now reports the bootstrap median + 2.5/97.5 percentile CIs and the bound-pinned fraction (`results/robustness/ci_consistency.csv`, `results/robustness/bound_railing.csv`). The remaining task is mainly to confirm the plotted estimate matches the reported interval and to surface bound-pinning in the canonical manuscript's tables.

Instruction for Codex/Claude:

- Report full-budget point estimate and bootstrap median separately if they differ.
- Do not hide cases where the full optimum falls outside the bootstrap interval.
- Report the fraction of bootstrap draws pinned to lower/upper bounds.
- Treat heavily bound-pinned parameters as weakly data-supported.

### 2.6 Fix the switching-threshold objective (cheap correctness)

Agreed verdict:

- The derivative-based threshold detector selects the 0 V sweep boundary as the switching point in most archived conditions. S10 is the outlier, with an objective near 793 vs ~20-47 elsewhere. This is a boundary artifact, not physics.

Instruction for Codex/Claude:

- In `stanford_fit/matlab/eval_loss.m`, smooth the current before the derivative-based threshold extraction and exclude a small voltage margin at both sweep boundaries.
- If no reliable interior threshold exists, mark the threshold metric unavailable instead of assigning 0 V, and do not let it dominate the loss.
- Add a warning if one threshold penalty dominates the total loss; report component-wise loss terms.
- Re-check that S10 no longer shows an anomalous objective after the fix.

---

## 3. Do now: reconcile with work already completed

Agreed verdict:

- The earlier roadmap was stale relative to `claude.txt`.
- Some robustness work may already exist in `main_alt.tex`, `Latex_Abstract/build_abstract.py`, `08_paper_alt_figures.py`, `09_robustness_extensions.py`, and `results/robustness/`.
- Avoid redoing completed work.

Instruction for Codex/Claude:

Before implementing anything, compare this triage list against:

- `claude.txt`
- `Latex_main/main_alt.tex`
- `Latex_main/main_alt_codex.tex`
- `Latex_Abstract/build_abstract.py`
- `02c_classify_conduction_regimes.py`
- `06_run_variability.py`
- `08_paper_alt_figures.py`
- `09_robustness_extensions.py`
- `results/robustness/`
- `results/variability/`
- `results/paper_alt/`

Then produce a short status table:

- already implemented
- partially implemented
- still needed
- should be deferred

Do not blindly implement old roadmap items.

---

## 4. Keep lightweight reproducibility only

Partial agreement with the verdict:

- A full manifest/results-run rearchitecture is too much for this paper revision.
- But some lightweight provenance is still useful because the repo already has mixed/stale artifacts.

Instruction for Codex/Claude:

Do not do a major `results/runs/` architecture rewrite now.

Instead, keep this lightweight:

- Add or maintain a simple run summary file only if needed.
- Ensure paper figures/tables are generated from a known set of CSV/JSON files.
- Make scripts fail loudly when required inputs are missing.
- Avoid mixed artifacts from multiple runs.

Reviewer-visible science comes first; infrastructure should stay minimal.

---

## 5. Defer for now: large model/repo rebuilds

Agreed verdict:

- These are real issues, but implementing them now may turn a paper revision into a new project.

Defer these unless the paper deliberately pivots:

- full repo results-directory rearchitecture;
- complete test-suite buildout;
- full-sweep single-state MATLAB/HSPICE simulator as a required replacement;
- in-circuit compliance model as a required replacement;
- hybrid Verilog-A model as a required replacement;
- large mixed-effects framework if simpler population/bootstrap summaries are sufficient.

Important nuance:

- Do not ignore these scientifically.
- Instead, adjust claims so the current paper does not overpromise.

For example:

- If the model still uses branch-specific SET/RESET parameters, do not call it a single drop-in circuit model.
- If compliance is post-processed, do not imply the internal state evolved under physical current limiting.
- If a hybrid barrier model is not implemented, describe it as future work or a follow-up contribution.

---

## 6. Resolve the “single compact model” framing

Agreed verdict:

- Forcing one continuous Stanford-PKU model may degrade the fit because polarity asymmetry is real.
- This is not a checkbox fix; it is a strategic framing decision.

Instruction for Codex/Claude:

Choose one honest framing:

### Option A — Current-paper framing

Present the work as:

> polarity-conditioned calibration and identifiability analysis of a Stanford-family RRAM compact model across a deposition DOE.

Then clearly state:

- SET and RESET are branch-conditioned.
- This improves empirical calibration but is not a single unmodified drop-in compact model.
- A single-instance polarity-extended or hybrid model is future work.

### Option B — New-model framing

If a polarity-extended or hybrid model is actually implemented and validated, present the work as:

> a new or extended compact model motivated by Stanford-PKU but modified for polarity-asymmetric TaOx switching.

This is a larger contribution and should be treated as separate-paper-scale unless already implemented cleanly.

Recommended for now:

- Use Option A.
- Do not force Option B during this revision.

---

## 7. Strengthen novelty positioning

Agreed verdict:

- “Population-validated, identifiability-aware framework” is reasonable but not enough by itself.
- The manuscript must explicitly differentiate from prior Stanford extraction, D2D/C2C calibration, stochastic compact modeling, and ML extraction papers.

Instruction for Codex/Claude:

Add a related-work/novelty paragraph that distinguishes this paper by the combination of:

- deposition-DOE-linked compact-model calibration;
- split-safe population validation across available devices/cycles;
- identifiability/sloppiness analysis of compact-model parameters;
- reporting identifiable combinations instead of only raw parameters;
- mechanism-aware model-adequacy diagnostics;
- formal or semi-formal DOE statistics on identifiable quantities;
- explicit reporting of bound-pinned/non-identifiable parameters.

Avoid claiming that automated Stanford extraction alone is novel.

---

## 8. Accept the strategic consequence

Agreed verdict:

- The honest version of the paper may become more modest.
- Some fits may look worse under cleaner validation.
- Some DOE effects may not survive correction.
- Some mechanism claims may need to be downgraded.

That is acceptable.

Instruction for Codex/Claude:

Do not optimize the story by hiding weaker results. Instead:

- report limitations explicitly;
- preserve strong results that survive validation;
- frame negative/weak findings as useful model-adequacy evidence;
- state what is supported by data and what remains future work.

A defensible paper is better than a smoother but fragile one.

---

## 9. Practical priority order

This is dependency/effort order (cheap correctness first, then the expensive population work), NOT value order. Section 2.1 (population/device-level validation) remains the single highest-value item; it appears mid-list only because the cheap fixes are faster and unblock it.

1. Reconcile current repo/manuscript state against `claude.txt`, and confirm the canonical manuscript is `main_alt_codex.tex`.
2. Fix mechanism-classifier statistical comparison and language.
3. Fix Fisher/log-coordinate/SVD reporting and retire exact “37 orders” headline.
4. Fix or rename profile-likelihood outputs.
5. Ensure bootstrap CI, plotted estimate, and bound-pinning reports are internally consistent.
6. Add split-safe population/device-level validation if not already present.
7. Update manuscript/abstract language to match the honest scope.
8. Add only lightweight provenance checks needed to avoid stale/mixed artifacts.

Do not start with:

- hybrid Verilog-A;
- full simulator rewrite;
- full results architecture rewrite;
- large test-suite buildout.

---

## 10. Summary table

| Verdict item | Agreement level | Keep in plan? | Action |
|---|---:|---:|---|
| Roadmap diagnoses are mostly accurate | Agree | Yes | Use as correctness checklist, not work order. |
| Original roadmap scope is too large | Agree | Yes | Replace broad rebuild with triage. |
| Population/device-level validation is highest value | Strongly agree | Yes | Prioritize split-safe population validation. |
| Mechanism classifier/BIC issue is real | Strongly agree | Yes | Use common response space and ambiguity labels. |
| Mechanism claims must be cautious | Strongly agree | Yes | Say “consistent with,” not “confirmed.” |
| Fisher log-coordinate issue is real | Strongly agree | Yes | Fix scaling and report SVD/rank. |
| Exact “37 orders” headline is risky | Strongly agree | Yes | Reframe as sloppiness/rank deficiency. |
| Profile likelihood may be only loss slice | Agree | Yes | Reoptimize nuisance params or rename. |
| Bootstrap/bound-pinning consistency matters | Strongly agree | Yes | Report median/full estimate/bound fractions honestly. |
| Roadmap is stale vs prior `claude.txt` work | Agree | Yes | Reconcile before coding. |
| Full manifest/results rearchitecture is overkill | Partly agree | Partial | Keep only lightweight provenance. |
| Full single-state Stanford simulation is immediate priority | Mostly agree with deferral | No, defer | Fix manuscript framing instead. |
| Hybrid Verilog-A model is immediate priority | Mostly agree with deferral | No, defer | Treat as follow-up unless paper pivots. |
| Novelty framing needs prior-art differentiation | Agree | Yes | Add explicit differentiation paragraph. |
| Honest fixes may make claims more modest | Agree | Yes | Accept and present transparently. |
| Three parallel manuscript variants exist | New | Yes | Edit only canonical `main_alt_codex.tex`; archive the other two. |
| Switching-threshold 0 V boundary artifact | Agree | Yes | Smooth + margin-exclude in `eval_loss.m`; mark unavailable if none. |
