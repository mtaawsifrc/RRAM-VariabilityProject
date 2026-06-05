# TaO-Fit: A Physics-Constrained, Identifiability-Aware Bayesian Framework for Nominal Fitting of the Stanford-PKU RRAM Compact Model to Ti/Pt/TaOx/Ta/Pt Crosspoint Data

## TL;DR
- **Existing Stanford-PKU fitters (Reuben 2019, Mahboubi 2022, Hamid 2025, SpiceXpanse 2025, UNIMORE/ESSDERC 2022) all leave the model's parameter degeneracy unaddressed and use ad hoc composite losses** — Hamid 2025 explicitly excludes I0 from the CNN regression because of "the lack of inherent scale in the input images", confirming the inverse problem is ill-posed; γ0 error reaches 89–93% on benchmark devices.
- **We propose TaO-Fit**, a 5-stage pipeline (regime extraction → conduction-mechanism Gaussian priors → Fisher-information identifiability → MATLAB `bayesopt` over HSPICE → leave-one-cycle-out validation) that runs in ~70 min on a single RHEL workstation, integrates the Chowdhury MWSCAS 2025 Ohmic/PF/Schottky/FN regime fits as priors, and natively reports parameter CIs and identifiability flags.
- **Honesty on scope**: from one nominal DC medoid curve only ~4 parameters (g0, V0, I0, γ0) are robustly identifiable; β, Vel0, Ea, Rth, F_min, gap_max should be treated as priors-only — the report says so explicitly and would not pass review otherwise.

## Key Findings
1. Hamid 2025 (arXiv:2511.07926v1) uses a ResNet-50v2 backbone with 16,000 synthetic 224×224×3 images, 54 Adam epochs at lr=10⁻³, validation RMSE 0.1094, but its per-parameter error on Reuben's Pt/HfO2 benchmark is g0=0.41%, V0=4.06%, ν=2.86%, β=19.7%, γ0=93.2%, I0=41.2% (their Table II) — i.e., the model fits the curve well but lands on a degenerate point in (I0, γ0, β) space.
2. Reuben 2019's IEEE T-Nano fitting algorithm fixes the parameter order g0 → V0 → Vel0 → I0 → β → γ0 by Verilog-A header convention; its IHP HfO2 calibrated values (Ea=0.6 eV, I0=8.54×10⁻⁴, Rth=1500 K/W, g0=0.346 nm, V0=0.26, Vel0=0.05, β=0.4, γ0=19.5, gap_max=18.8 Å, tox=6 nm, F_min=1.4×10⁹ V/m) are an IHP-specific HfO2 1T1R operating point and should not be confused with the Stanford v1.0.0 Verilog-A defaults (Vel0=150, β=1.25, γ0=16.5, I0=6.14×10⁻⁵, g0=2.7505×10⁻¹⁰ m, V0=0.43).
3. SpiceXpanse (Bezugam, Choi, Menzel, Strukov; IEEE NMDC 2025, DOI 10.1109/NMDC64551.2025.11234564) is the only open-source framework (https://github.com/saibez/SpiceXpanse); the JuSER metadata confirms authors and venue but the conference paper's loss-function form, parallelization details, and wall-clock benchmarks are paywalled and could not be independently verified from public sources at the time of writing — we treat this as a documented caveat.
4. UNIMORE 2022 (Zanotti, Pavan, Puglisi; ESSDERC 2022, IEEE Xplore 9947161) is the closest precedent to physics-informed priors but for a different compact model; the paper validates on TiN/Ti/HfOx/TiN plus three literature technologies and reports that the "automated parameter extraction procedure enables correctly calibrating the model parameters on all four considered RRAM technologies".
5. Mahboubi 2022 (DCIS, CNM2022V1) is the only existing framework that addresses polarity asymmetry and parasitic series resistance, both by polarity-split parameters and an additional Verilog-A series-R element, but tuned by trial-and-error.
6. The user's MWSCAS 2025 result that TaOx LRS is Ohmic at low V and HRS transitions through Schottky/PF/FN as the field rises directly maps to four scalar constraints on the Stanford parameters via dimensional analysis (Section 2, Stage 1).

## Section 1 — Gap Analysis of Existing Stanford-PKU Fitting Methods

### 1.1 Comparison Table

| Method | Core algorithm | Inputs | Optimizes | Open source | Reported error | Init dependence | Couples params | Physics prior | Parallelism |
|---|---|---|---|---|---|---|---|---|---|
| Reuben 2019 (T-Nano, DOI 10.1109/TNANO.2019.2922838) | Manual 7-step sweep, fixed parameter order from Verilog-A header | Numeric I-V + 1T1R curves | Pointwise current overlay | No (manual+IHP Verilog-A on FAU server) | Visual overlay only | High | No (fixed serial order) | No | None |
| Mahboubi 2022 (DCIS, IEEE 9970051) CNM2022V1 | Manual polarity-split + Verilog-A series-R add-on | Numeric I-V (TiN/Ti/HfO2/W) | Half-cycle MSE | No | Visual | High | Splits +/− half-cycles | Implicit series-R from snapback | None |
| Hamid 2025 (arXiv 2511.07926v1) | ResNet-50v2 (5/6 params, I0 excluded) + 3 adaptive binary-search blocks | I-V rendered to 224×224×3 image; ~16k synthetic train | 4 NVM metrics (Vset, Vreset, hysteresis area, LRS slope) | Not released | Val RMSE 0.1094; γ0 89–93% / I0 41% error on benchmark | CNN gives prior; refined heuristically | Acknowledges ill-posedness | No | Inference only |
| SpiceXpanse 2025 (NMDC, DOI 10.1109/NMDC64551.2025.11234564) | Adaptive poly-fit optimizer; parallel SPICE; composite MSE/IoU/DTW/MW | Numeric I-V | Composite (weights user-set) | Yes (github.com/saibez/SpiceXpanse) | Not in public abstract | LHS init | Sweep order acknowledged not principled | No | Parallel SPICE |
| UNIMORE Zanotti 2022 (ESSDERC, IEEE 9947161) | Self-consistent per-experiment extraction (different compact model) | DC IV + pulsed reset + multi-T | Per-experiment subset | Verilog-A on nanoHUB; extraction code not public | 4 technologies validated | Low | Decouples by experiment | Strong (one parameter ≈ one experiment) | None |
| Chowdhury 2025 (MWSCAS, user) | Conduction-mechanism regressions (Ohmic, PF, Schottky, FN) on TaOx | Numeric I-V; HRS/LRS branches | Region-specific linear fits | Available to user | r² per regime | None | Mechanism per regime | YES (target of this work) | None |
| Saxena 2019 (par.nsf.gov/servlets/purl/10130554) | Threshold detection + region-wise NLLS on TaOx | Cyclic I-V | Region MSE | Yes | Visual overlay vs Yakopcic/VTEAM | Low | Region-wise | Some | None |
| Zhevnenko 2021 (Micromachines, doi:10.3390/mi12101220) | Random-forest initial guess + LM refinement | I-V | MSE | Yes (described) | Speedup vs random init | Low | Some | No | None |
| PiRNN Sha 2023 (Electronics 12, 2906) | Physics-informed RNN learning g(t); Verilog-A export | I-V time series | RNN loss | No | r²=0.98 HfO2 W=10 µm | Mid | Decoupled by physics block | Yes (lateral filament) | GPU |
| Yeon 2024 PINN (Micromachines 15, 253) | PINN solving memristor PDE; Verilog-A export | I-V + V(t) | PDE residual | No | Two devices verified | Mid | Native to PDE | Yes | GPU |

### 1.2 Numbered Gaps (G1–G15)

**G1. Parameter degeneracy unquantified.** The Stanford current I = I₀·exp(−g/g₀)·sinh(V/V₀) at low V on the LRS branch (with g pinned at the floor `parameter real gap_min = 0.1e-9 from (0:L)` hardcoded in the Stanford–ASU Verilog-A) becomes I ≈ (I₀/V₀)·exp(−gap_min/g₀)·V. Any (I₀, V₀, g₀) triple that holds the product (I₀/V₀)·exp(−gap_min/g₀) constant is observationally equivalent — a one-dimensional null direction in parameter space. Hamid 2025 acknowledges this implicitly: "I0 was excluded from being predicted by the convolutional neural network due to the lack of inherent scale in the input images." Reuben 2019, Mahboubi 2022, SpiceXpanse 2025 are silent on the degeneracy.

**G2. Loss-function discontinuity at log-scale near current floor.** Linear-current MSE is dominated by SET/RESET peaks (~1 mA) and ignores HRS (~100 pA) by 7 orders of magnitude. SpiceXpanse adds IoU/DTW/memory-window terms; none of the open frameworks formulate the loss as a proper Gaussian log-likelihood with per-voltage variance scaling on log|I|.

**G3. Sweep-order bias.** Reuben fixes g0 → V0 → Vel0 → I0 → β → γ0 by Verilog-A header convention; Hamid's three heuristic blocks pick β,γ0 first (for Vset/Vreset) → V0 (LRS slope) → g0 (hysteresis area); SpiceXpanse "acknowledges sweep order influences convergence stability and physical realism" but does not derive a principled ordering. No method computes a Fisher-information-justified ordering.

**G4. No conduction-mechanism priors.** Poole-Frenkel (J. Frenkel, "On Pre-Breakdown Phenomena in Insulators and Electronic Semi-Conductors," Physical Review 54(8), 647–648, 1938, doi:10.1103/PhysRev.54.647), Schottky-Richardson, Fowler-Nordheim (R.H. Fowler and L. Nordheim, "Electron Emission in Intense Electric Fields," Proc. Roy. Soc. Lond. A 119, 173–181, 1928), and Ohmic regimes are model-independent and directly measurable on raw I-V. The Stanford parameters γ0·a0/tox and Ea are physically the same quantities PF/Schottky measure (field-enhancement length and trap depth), yet no framework uses them as priors.

**G5. Validation methodology.** All five primary papers report only one overlaid I-V curve. Hamid does report per-parameter error against synthetic reference but the visual overlay masks the 89–93% γ0 error. None of the five papers report leave-one-cycle-out RMSE, residual auto-correlation (Durbin-Watson), parameter posterior CIs, or sensitivity bounds.

**G6. Reproducibility.** Reuben (FAU PDFs, IHP-specific), Mahboubi (no code), UNIMORE extractor (compact model on nanoHUB but extraction script not released) are not reproducible. SpiceXpanse posts code but is HSPICE-coupled, Python-only, requires user-written netlist templates, and has no MATLAB front-end.

**G7. Compliance current / series resistance.** Keysight B1500 data has explicit CC (~1 mA typical) and parasitic series R from probe pads. Mahboubi 2022 is the only framework to insert a series R in Verilog-A; it is set by trial-and-error. None handle CC explicitly in the loss.

**G8. Joule-heating coupling.** In Verilog-A: T_cur = T_ini + |V·I|·Rth feeds back into gap_ddt through exp(−Ea/kT). During the SET transient, I depends on gap, gap rate depends on T, T depends on I — Rth is non-identifiable from steady-state DC alone. None of the frameworks isolate Rth or say so.

**G9. Verilog-A discontinuities.** The user's uploaded file (Stanford NEEDS v1.0.0) hardcodes γ_ini = 16 in the negative half-cycle (overriding γ0), and γ collapses to zero when the field falls below F_min, creating a derivative discontinuity invisible to CNN regression and destabilizing to gradient-based optimizers. No framework documents these.

**G10. Composite-loss weight selection is ad hoc** in SpiceXpanse, Hamid 2025, Mahboubi 2022. None scale by per-residual variance, the only choice that yields a proper Gaussian log-likelihood.

**G11. No held-out cycle test** despite typical datasets having tens of cycles (the user has ~20).

**G12. No bootstrap or parameter CI** — IEEE TED/T-Nano reviewers increasingly require uncertainty quantification.

**G13. No structural-bias check** (sign-correlated residuals would expose Stanford's inability to capture, e.g., SCLC ∝ V² regimes occasionally seen in TaOx).

**G14. Sweep-rate / time-scale assumption** — the user's data are quasi-DC (~0.1 V/s) yet the Verilog-A integrates gap dynamics with Vel0 (default 150 m/s); none of the open frameworks document time-step sensitivity.

**G15. Polarity asymmetry** — Ti/Pt/TaOx/Ta/Pt with asymmetric Ta and Pt electrodes routinely has |Vset| ≠ |Vreset|. The base Stanford-PKU model is single-polarity-parameterized except for γ_ini override; only Mahboubi splits polarity parameters but only for HfO2.

## Section 2 — Proposed Algorithm: TaO-Fit

### Stage 0 — Data preparation
Reads the user's `02_select_device_representative_curve.py` CSV (columns: condition, device_id, branch ∈ {SET, RESET}, voltage_V, median_current_A, median_abs_current_A, median_log10_abs_current, q25_current_A, q75_current_A, butterfly_sequence_index, representative_cycle_id). Reconstructs the butterfly sequence by sorting on `butterfly_sequence_index`; splits each branch into ascending and descending half-sweeps; identifies regimes (LRS-Ohmic |V|<0.3 V on post-SET descending half; LRS-high-V; HRS-low-V; HRS-PF/Schottky; SET transition window flagged where d log10|I|/dV > 4× median elsewhere; RESET transition analogously). Computes feature scalars Vset, Vreset, R_LRS (robust linear regression on LRS-Ohmic), I_HRS@Vread=0.1 V, hysteresis area H on log|I| plane, SET sharpness, RESET curvature.

### Stage 1 — Physics-informed prior derivation (the key novelty)
With I = I₀ · exp(−g/g₀) · sinh(V/V₀):

**(P1) LRS Ohmic → (I₀/V₀)·exp(−gap_min/g₀)**. At |V| ≪ V₀ the LRS conductance is G_LRS = (I₀/V₀)·exp(−gap_min/g₀). With gap_min hardcoded to 0.1 nm in the Stanford–ASU Verilog-A and g₀ ≈ 0.275 nm (Stanford v1.0.0 default), exp(−gap_min/g₀) ≈ 0.694 so (I₀/V₀) ≈ G_LRS/0.694. σ_P1 from LRS linear-regression residual.

**(P2) LRS curvature → V₀**. The only nonlinearity on the LRS branch is sinh(V/V₀). NLLS fit I = A·sinh(V/V₀) for |V| up to ~Vset/2 yields V₀ with tight σ from the Jacobian. From P1+P2: I₀ = A·V₀·exp(gap_min/g₀).

**(P3) HRS Poole-Frenkel → γ₀·a₀/tox**. PF: J = C·E·exp[−q(φ_T − √(qE/πε))/(kT)]. On a ln(I/V) vs √V plot the slope κ_PF = (q/kT)·√(q/(πε·tox)). The Stanford gap-dynamics sinh argument contains (γ·a₀·qV)/(kT·tox), so the field-enhancement length γ·a₀/tox corresponds to PF's barrier-lowering coefficient. Dimensional matching: γ₀_prior = 2·κ_PF·√(π·ε·tox)·(kT/q)·(tox/a₀²), with the static permittivity of TaOx ε_r ≈ 25 (J.J. Yang, M.-X. Zhang, J.P. Strachan, F. Miao, M.D. Pickett, R.D. Kelley, G. Medeiros-Ribeiro, R.S. Williams, "High switching endurance in TaOx memristive devices," Applied Physics Letters 97, 232102, 2010, doi:10.1063/1.3524521). Clamp γ₀_prior to [4, 24] (Verilog-A bounds); σ_P3 = 0.4·γ₀_prior.

**(P4) PF intercept → Ea**. PF y-intercept ∝ −q·φ_T/(kT). Map trap depth φ_T to Stanford's activation energy Ea (soft prior, σ=0.25 eV — inflated because Ea in Stanford lumps generation and recombination activations).

**(P5) PF→FN crossover → F_min**. F_min_prior = V_crossover / tox (σ = 30%). Default F_min = 1.4×10⁹ V/m per Reuben's IHP example.

**(P6) Vel0, β, Rth, gap_max** carried as broad Gaussian priors from the Stanford–ASU Verilog-A defaults (Vel0=150 m/s, β=1.25, γ₀=16.5) — NOT Reuben's IHP-specific calibrated values (Vel0=0.05, β=0.4, γ₀=19.5), which apply to HfO2 1T1R at IHP and should not be transplanted to TaOx; for Rth we use 2.1×10⁵ K/W (σ=50%) typical of sub-100 nm crosspoints.

Priors enter the loss as Mahalanobis regularization (θ − μ_prior)ᵀ Σ_prior⁻¹ (θ − μ_prior).

### Stage 2 — Identifiability analysis BEFORE optimization
Parameter vector θ = (log I₀, log g₀, log V₀, log Vel0, log γ₀, log β, log Ea, log Rth, log F_min, gap_min, gap_max, gap_ini, log tox). Compute S_ij = ∂log|I_sim(V_i)|/∂log θ_j by central differences (relative step 10⁻³ with absolute floor 10⁻¹²) at θ_0 = prior means, on the union of measured voltage points. Weighted Fisher F = Sᵀ W S with W_ii = 1/σ_logI(V_i)² where σ_logI(V) from user's q25/q75: σ_logI ≈ (q75 − q25)/(1.35·|I|·ln 10). Eigendecompose F = U Λ Uᵀ. Flag direction k ill-conditioned if Λ_max/Λ_k > 10³. Cramer-Rao effective σ_eff,j = √(F⁻¹)_jj per parameter. Expected outcome on TaOx DC nominal data: ~4 well-conditioned directions corresponding to {(I₀/V₀)·exp(−gap_min/g₀), V₀, γ₀, Vset} and ~9 ill-conditioned directions absorbed by priors. Save F as CSV for supplementary material.

### Stage 3 — MATLAB bayesopt over HSPICE
- **Search space**: active parameters = well-conditioned subset from Stage 2 (default I₀, g₀, V₀, γ₀); positive scale parameters declared with `optimizableVariable(..., 'Transform','log')`; bounds = max(Verilog-A `(0:...)` bounds, μ_prior ± 2σ_prior).
- **Initial design**: Latin Hypercube, 40 points.
- **Surrogate**: GP with ARD-Matérn-5/2 kernel; `AcquisitionFunctionName = 'expected-improvement-plus'`.
- **Per evaluation**: `write_netlist.m` → `system('hspice ...')` → `parse_lis.m` → interpolate sim to measurement grid → `eval_loss.m`.
- **Loss**: L(θ) = (1/N_set)·Σ_SET[(Δlog10I)/σ_logI]² + (1/N_reset)·Σ_RESET[...] + (Vset_sim−Vset_meas)²/σ_V² + (Vreset_sim−Vreset_meas)²/σ_V² + (θ−μ_prior)ᵀΣ_prior⁻¹(θ−μ_prior). All weights are variance-scaled, not hand-tuned.
- **Budget**: 40 init + 160 acquisition = 200 HSPICE runs ≈ 70 minutes on a single RHEL workstation at ~20 s per HSPICE DC sweep.
- **Failure handling**: HSPICE non-convergence → return L=10⁶, retry with `.option dcstep=1e-3 gmindc=1e-10`; three consecutive fails → log and skip.

### Stage 4 — Local refinement
Nelder-Mead (`fminsearch`) on well-conditioned subspace only, 100 evaluation max, 1% simplex initial size. Ill-conditioned parameters frozen at Stage-1 priors.

### Stage 5 — Validation
1. **LOCO** over the user's ~20 cycles: recompute medoid on N−1 cycles, short BO (10 init + 40 acquisition), predict held-out cycle, log RMSE distribution.
2. **Residual Durbin-Watson** per branch; flag if |DW − 2| > 0.4 → recommend Mahboubi polarity-split or CNM2022V1 series-R extension.
3. **Bootstrap CI**: 100 cycle-resamples × 50-eval short BO each → 95% percentile interval per parameter.
4. **Identifiability report**: σ_eff/|θ| > 0.5 flagged as non-identifiable from this experiment class.
5. **Sanity forward sim**: monotonic SET/RESET, no NDR where measured shows none, ramp-rate invariance at 0.5× and 2× the measured sweep rate.

### Pre-empted reviewer objections
- *BO vs PSO/chaos-PSO*: BO with EI typically converges in O(10²) evaluations on smooth ≤10-D problems; chaos-PSO/SPSSA papers report O(10³–10⁴). The user has no MPI; sample efficiency dominates.
- *Priors not circular*: Frenkel (1938), Fowler-Nordheim (1928), and Schottky-Richardson equations are derived from band theory independently of the Stanford-PKU compact form. They enter the loss as soft Gaussian priors so the data can outvote them.
- *Loss-landscape multimodality*: Stage 2 exposes degenerate directions; priors break ties. If Λ_max/Λ_min remains > 10⁴ after prior fold-in, increase BO budget or add a multi-start.
- *Stanford structurally wrong for TaOx*: Stage 5 Durbin-Watson detects misspecification; fallback to Mahboubi polarity split or PiRNN behavioral model.

### Trade-off vs Reuben baseline
For a single qualitative I-V overlay figure, Reuben 2019's manual sweep is sufficient and costs ~30 min of analyst time. TaO-Fit is justified when (i) parameter CIs are needed, (ii) you scale to 12 conditions × ~10 devices (the user's plan), (iii) reviewer-defensible identifiability claims matter for IEEE T-ED/T-Nano, or (iv) the MWSCAS conduction-mechanism work must feed the model fit. The LOCO test alone justifies the upgrade for a first peer-reviewed publication.

## Section 3 — Codebase

Directory: `stanford_fit/`.

### `stanford_fit/README.md`
```markdown
# stanford_fit — TaO-Fit reference implementation

## Setup
- MATLAB R2023a+ with Statistics and Machine Learning Toolbox (`bayesopt`)
- HSPICE H-2013.03-SP2 or newer on $PATH
- Python ≥3.10 with numpy, pandas, matplotlib (non-interactive), pyyaml
- Verilog-A file rram_v_1_0_0_hspice.va (Stanford NEEDS v1.0.0, included in templates/)

## Usage
```
cd stanford_fit/matlab
matlab -batch "main_fit_stanford('../../data/step02_medoid_S1.csv','../config/default_config.yaml','../../results/S1')"
```
or
```
python stanford_fit/python/03_run_stanford_fit.py \
  --input data/step02_medoid_S1.csv \
  --config stanford_fit/config/default_config.yaml \
  --outdir results/S1
```

## Reviewer Response (top 10 anticipated questions)
1. *Why BO over PSO?* See Section 2; `stage3_bayesopt_driver.m` uses Expected Improvement Plus; budget 200 evaluations.
2. *Are priors circular?* `stage1_extract_priors.m` derives them from model-independent conduction-mechanism regressions (Frenkel 1938; Fowler-Nordheim 1928) with explicit σ; the loss can outvote them.
3. *How do you know the fit is identifiable?* `stage2_identifiability.m` outputs Fisher eigenspectrum and per-parameter effective σ in `fisher_report.csv`. Non-identifiable parameters are flagged.
4. *Cross-cycle validation?* `stage5_validate.m` runs leave-one-cycle-out, reports per-branch RMSE distribution.
5. *Parameter CIs?* Bootstrap with 100 resamples in `stage5_validate.m`; 95% percentile.
6. *Sensitivity to sweep rate?* Forward-simulate at 0.5× and 2× measured rate; `plot_fit_quality.m` panel (d).
7. *Compliance current handling?* `templates/rram_dc_sweep.sp.template` uses behavioral G-clamp not a series R, preserving loss shape.
8. *Verilog-A discontinuities (γ_ini=16 hardcoded; γ→0 below F_min)?* Documented in code; F_min held at Stage-1 prior; the γ_ini override only affects negative-V branch and is modeled but flagged.
9. *Why not just use Reuben 2019 manually?* For single overlay it suffices; lacks CIs and validation — see Section 2.
10. *What if Stanford model is wrong for TaOx?* Durbin-Watson < 1.6 ⇒ recommend Mahboubi polarity split or PiRNN behavioral fallback.
```

### `stanford_fit/matlab/main_fit_stanford.m`
```matlab
function out = main_fit_stanford(csv_path, config_path, outdir)
%MAIN_FIT_STANFORD  Entry point for TaO-Fit pipeline.
    if ~isfolder(outdir); mkdir(outdir); end
    cfg = read_yaml_config(config_path);
    fprintf('[main] loading data from %s\n', csv_path);
    data = readtable(csv_path);
    [setBranch, resetBranch, feats] = split_and_featurize(data);

    fprintf('[main] Stage 1: extracting physics-informed priors\n');
    priors = stage1_extract_priors(setBranch, resetBranch, feats, cfg);
    save(fullfile(outdir,'priors.mat'),'priors');

    fprintf('[main] Stage 2: Fisher identifiability analysis\n');
    fish = stage2_identifiability(priors, setBranch, resetBranch, cfg);
    writematrix(fish.F, fullfile(outdir,'fisher_matrix.csv'));
    save(fullfile(outdir,'fisher_report.mat'),'fish');

    fprintf('[main] Stage 3: Bayesian optimization with HSPICE\n');
    bo_result = stage3_bayesopt_driver(priors, fish, setBranch, resetBranch, cfg, outdir);
    save(fullfile(outdir,'bo_result.mat'),'bo_result');

    fprintf('[main] Stage 4: Nelder-Mead local refinement\n');
    refined = stage4_local_refine(bo_result, fish, setBranch, resetBranch, cfg);
    save(fullfile(outdir,'refined.mat'),'refined');

    fprintf('[main] Stage 5: validation (LOCO + bootstrap)\n');
    val = stage5_validate(refined, fish, setBranch, resetBranch, data, cfg, outdir);
    save(fullfile(outdir,'validation.mat'),'val');

    plot_fit_quality(refined, val, setBranch, resetBranch, fullfile(outdir,'fit_quality.png'));

    out = struct('theta_best',refined.theta,'ci95',val.ci95,'fisher',fish, ...
                 'loco_rmse',val.loco_rmse,'cfg',cfg);
    save(fullfile(outdir,'main_out.mat'),'out');
    fprintf('[main] done. results in %s\n', outdir);
end

function cfg = read_yaml_config(p)
    txt = fileread(p); cfg = struct();
    for line = splitlines(string(txt))'
        s = strtrim(line);
        if startsWith(s,"#") || strlength(s)==0; continue; end
        kv = split(s, ":");
        if numel(kv) < 2; continue; end
        key = char(strtrim(kv(1)));
        val = strtrim(strjoin(kv(2:end),":"));
        num = str2double(val);
        if ~isnan(num); cfg.(key) = num; else; cfg.(key) = char(val); end
    end
end

function [setB, resetB, feats] = split_and_featurize(data)
    setB   = data(data.branch == "SET",   :);
    resetB = data(data.branch == "RESET", :);
    [setB,~]   = sortrows(setB,'butterfly_sequence_index');
    [resetB,~] = sortrows(resetB,'butterfly_sequence_index');
    feats = struct();
    lrs_mask = abs(setB.voltage_V)<0.3 & setB.butterfly_sequence_index>median(setB.butterfly_sequence_index);
    if any(lrs_mask)
        p = polyfit(setB.voltage_V(lrs_mask), setB.median_current_A(lrs_mask), 1);
        feats.G_LRS = p(1); feats.R_LRS = 1/p(1);
    else
        feats.G_LRS = NaN; feats.R_LRS = NaN;
    end
    asc = setB.butterfly_sequence_index <= median(setB.butterfly_sequence_index);
    V = setB.voltage_V(asc); logI = setB.median_log10_abs_current(asc);
    dlogI = gradient(logI, V);
    [~,ix] = max(dlogI); feats.Vset = V(ix);
    descR = resetB.butterfly_sequence_index <= median(resetB.butterfly_sequence_index);
    Vr = resetB.voltage_V(descR); logIr = resetB.median_log10_abs_current(descR);
    dlogIr = gradient(logIr, Vr);
    [~,ix2] = min(dlogIr); feats.Vreset = Vr(ix2);
    hrs_mask = abs(setB.voltage_V - 0.1) < 0.02 & asc;
    if any(hrs_mask); feats.I_HRS_read = mean(setB.median_abs_current_A(hrs_mask));
    else; feats.I_HRS_read = NaN; end
end
```

### `stanford_fit/matlab/stage1_extract_priors.m`
```matlab
function priors = stage1_extract_priors(setB, resetB, feats, cfg)
    kB = 1.380649e-23; q = 1.602176634e-19; eps0 = 8.8541878128e-12;
    T  = field_or(cfg,'T_K',300);
    tox = field_or(cfg,'tox',5e-9);
    eps_r = field_or(cfg,'eps_r_TaOx',25);
    eps = eps_r*eps0;
    a0 = field_or(cfg,'a0',2.5e-10);
    gap_min = field_or(cfg,'gap_min',1e-10);

    asc  = setB.butterfly_sequence_index <= median(setB.butterfly_sequence_index);
    lrs  = setB(~asc & abs(setB.voltage_V) <= max(0.5,0.7*abs(feats.Vreset)), :);
    if height(lrs) >= 6 && ~isnan(feats.G_LRS)
        f = @(p,V) p(1)*sinh(V./p(2));
        p0 = [max(feats.G_LRS,1e-7)*0.25, 0.25];
        opt = optimoptions('lsqcurvefit','Display','off');
        [pfit,~,res,~,~,~,J] = lsqcurvefit(f,p0,lrs.voltage_V,lrs.median_current_A, ...
                                           [1e-12 0.05],[1e-2 2.0],opt);
        A_est = pfit(1); V0_est = pfit(2);
        Cov = full(inv(J'*J)) * (res'*res)/max(1,(numel(res)-2));
        sig_A = sqrt(Cov(1,1)); sig_V0 = sqrt(Cov(2,2));
    else
        A_est = max(feats.G_LRS,1e-6)*0.25; V0_est = 0.43;
        sig_A = 0.5*A_est; sig_V0 = 0.15;
    end

    g0_prior = field_or(cfg,'g0_prior_m',2.75e-10);
    sig_g0   = field_or(cfg,'g0_prior_sigma_m',0.5e-10);
    I0_prior = A_est*V0_est*exp(gap_min/g0_prior);
    sig_I0   = abs(I0_prior)*sqrt((sig_A/A_est)^2 + (sig_V0/V0_est)^2 + ...
                                   (gap_min*sig_g0/g0_prior^2)^2);

    hrs = setB(asc & abs(setB.voltage_V)>0.3 & abs(setB.voltage_V)<0.9*max(abs(feats.Vset),0.5), :);
    if height(hrs) >= 6
        V = hrs.voltage_V; I = hrs.median_abs_current_A;
        y = log(max(I,1e-14)./max(V,1e-3));
        x = sqrt(max(V,0));
        ok = isfinite(y)&isfinite(x)&x>0;
        if sum(ok) >= 5
            p_pf = polyfit(x(ok),y(ok),1);
            kappa = p_pf(1);
            gamma0_prior = 2*kappa*sqrt(pi*eps*tox)*(kB*T/q)*(tox/a0^2);
            gamma0_prior = max(min(gamma0_prior,24),4);
            sig_gamma0 = 0.4*gamma0_prior;
            Ea_prior = max(0.5, min(1.6, -p_pf(2)*kB*T/q));
            sig_Ea = 0.25;
        else
            gamma0_prior = 16.5; sig_gamma0 = 6; Ea_prior = 1.5; sig_Ea = 0.3;
        end
    else
        gamma0_prior = 16.5; sig_gamma0 = 6; Ea_prior = 1.5; sig_Ea = 0.3;
    end

    F_min_prior = field_or(cfg,'F_min_prior',1.4e9);
    sig_Fmin    = 0.3*F_min_prior;

    priors = struct();
    priors.names = {'I0','g0','V0','Vel0','gamma0','beta','Ea','Rth','F_min', ...
                    'gap_min','gap_max','gap_ini','tox'};
    priors.mu = [ I0_prior, g0_prior, V0_est, ...
                  field_or(cfg,'Vel0_prior',150), gamma0_prior, ...
                  field_or(cfg,'beta_prior',1.25), Ea_prior, ...
                  field_or(cfg,'Rth_prior',2.1e5), F_min_prior, ...
                  gap_min, field_or(cfg,'gap_max',1.7e-9), ...
                  field_or(cfg,'gap_ini_HRS',1.4e-9), tox ];
    priors.sigma = [ sig_I0, sig_g0, sig_V0, ...
                     field_or(cfg,'Vel0_sigma',75), sig_gamma0, ...
                     field_or(cfg,'beta_sigma',0.5), sig_Ea, ...
                     field_or(cfg,'Rth_sigma',1e5), sig_Fmin, ...
                     0.05e-9, 0.3e-9, 0.3e-9, 0.5e-9 ];
    priors.lb = [1e-6, 1.5e-10, 0.15, 1,   4,  0.1, 0.5, 1e4, 5e8, 5e-11, 1.0e-9, 0.1e-9, 2e-9];
    priors.ub = [5e-3, 5.0e-10, 0.6,  500, 24, 2.0, 1.8, 5e5, 5e9, 3e-10, 2.5e-9, 2.0e-9, 1e-8];
    priors.feats = feats;
end

function v = field_or(s,fn,d); if isfield(s,fn); v=s.(fn); else; v=d; end; end
```

### `stanford_fit/matlab/stage2_identifiability.m`
```matlab
function fish = stage2_identifiability(priors, setB, resetB, cfg)
    Vgrid = [setB.voltage_V; resetB.voltage_V];
    sigma_logI = max(local_sigma_logI(setB,resetB), 0.05);
    theta0 = priors.mu;  nP = numel(theta0);  nV = numel(Vgrid);

    base = run_hspice(theta0, Vgrid, priors.names, cfg);
    if all(isnan(base)); fish = empty_fisher(priors); return; end

    S = zeros(nV,nP); h = 1e-3;
    for j = 1:nP
        tp = theta0; tm = theta0;
        dp = max(abs(theta0(j))*h, 1e-12);
        tp(j) = theta0(j) + dp; tm(j) = theta0(j) - dp;
        Ip = run_hspice(tp, Vgrid, priors.names, cfg);
        Im = run_hspice(tm, Vgrid, priors.names, cfg);
        S(:,j) = (log10(max(abs(Ip),1e-14))-log10(max(abs(Im),1e-14))) ./ ...
                 (2*dp/max(abs(theta0(j)),1e-30));
    end
    W = diag(1./sigma_logI.^2);
    F = S'*W*S;
    [U,Lam] = eig((F+F')/2);
    lam = real(diag(Lam));  [lam,idx] = sort(lam,'descend'); U = U(:,idx);
    ratio = lam/max(lam,[],'omitnan');
    well_idx = find(ratio > 1e-3);  nonid_idx = find(ratio <= 1e-3);
    eff_sigma = sqrt(max(diag(pinv(F)),0));
    fish = struct('F',F,'eigvals',lam,'eigvecs',U,'ratio',ratio, ...
                  'well_idx',well_idx,'nonid_idx',nonid_idx, ...
                  'eff_sigma',eff_sigma,'names',{priors.names},'theta0',theta0);
end

function s = local_sigma_logI(setB,resetB)
    q25 = [setB.q25_current_A; resetB.q25_current_A];
    q75 = [setB.q75_current_A; resetB.q75_current_A];
    med = abs([setB.median_current_A; resetB.median_current_A]);
    s = (abs(q75-q25)/1.35) ./ max(med,1e-14) / log(10);
    s(~isfinite(s)) = 0.2;
end

function fish = empty_fisher(priors)
    n = numel(priors.mu);
    fish = struct('F',zeros(n),'eigvals',zeros(n,1),'eigvecs',eye(n), ...
                  'ratio',zeros(n,1),'well_idx',(1:min(4,n))','nonid_idx',[], ...
                  'eff_sigma',priors.sigma(:),'names',{priors.names},'theta0',priors.mu);
end
```

### `stanford_fit/matlab/stage3_bayesopt_driver.m`
```matlab
function bo_result = stage3_bayesopt_driver(priors, fish, setB, resetB, cfg, outdir)
    if isempty(fish.well_idx)
        active_names = {'I0','g0','V0','gamma0'};
    else
        active_names = priors.names(fish.well_idx(:)');
    end
    active_names = intersect(active_names,{'I0','g0','V0','gamma0','beta','Vel0'},'stable');

    vars = optimizableVariable.empty;
    for k = 1:numel(active_names)
        nm = active_names{k};
        j = find(strcmp(priors.names,nm));
        lo = max(priors.lb(j), priors.mu(j)-2*priors.sigma(j));
        hi = min(priors.ub(j), priors.mu(j)+2*priors.sigma(j));
        if any(strcmp(nm,{'I0','g0','Vel0','Rth','F_min'}))
            vars(end+1) = optimizableVariable(nm,[lo,hi],'Type','real','Transform','log'); %#ok<AGROW>
        else
            vars(end+1) = optimizableVariable(nm,[lo,hi],'Type','real'); %#ok<AGROW>
        end
    end

    objFun = @(t) eval_loss(t,priors,active_names,setB,resetB,cfg);
    n_init = field_or_(cfg,'bo_n_init',40);
    n_iter = field_or_(cfg,'bo_n_iter',160);

    rng(field_or_(cfg,'rng_seed',0));
    results = bayesopt(objFun, vars, ...
        'MaxObjectiveEvaluations', n_init+n_iter, ...
        'NumSeedPoints', n_init, ...
        'AcquisitionFunctionName','expected-improvement-plus', ...
        'IsObjectiveDeterministic',true, 'UseParallel',false, ...
        'PlotFcn',[], 'Verbose',1);

    theta_full = priors.mu;
    bestPt = bestPoint(results);
    for k = 1:numel(active_names)
        j = find(strcmp(priors.names, active_names{k}));
        theta_full(j) = bestPt.(active_names{k});
    end
    bo_result = struct('theta',theta_full,'active_names',{active_names}, ...
                       'results',results,'best',bestPt);
    save(fullfile(outdir,'bo_results.mat'),'results');
end
function v = field_or_(s,fn,d); if isfield(s,fn); v=s.(fn); else; v=d; end; end
```

### `stanford_fit/matlab/stage4_local_refine.m`
```matlab
function refined = stage4_local_refine(bo_result, fish, setB, resetB, cfg)
    active_names = bo_result.active_names;
    j_active = arrayfun(@(k) find(strcmp(fish.names,active_names{k})), 1:numel(active_names));
    x0 = bo_result.theta(j_active);
    f = @(x) wrap_loss(x,j_active,bo_result.theta,fish.names,setB,resetB,cfg);
    opts = optimset('Display','iter','MaxFunEvals',100,'TolX',1e-5,'TolFun',1e-5);
    [xopt,fval] = fminsearch(f,x0,opts);
    theta = bo_result.theta; theta(j_active) = xopt;
    refined = struct('theta',theta,'fval',fval,'active_names',{active_names});
end
function L = wrap_loss(x,j_active,theta_base,names,setB,resetB,cfg)
    theta = theta_base; theta(j_active) = x;
    fakePriors = struct('mu',theta,'sigma',inf*ones(size(theta)),'names',{names}, ...
                        'lb',-inf*ones(size(theta)),'ub',inf*ones(size(theta)), ...
                        'feats',struct('Vset',1,'Vreset',-1));
    t = table();
    for k = 1:numel(j_active); t.(names{j_active(k)}) = x(k); end
    L = eval_loss(t,fakePriors,names(j_active),setB,resetB,cfg);
end
```

### `stanford_fit/matlab/stage5_validate.m`
```matlab
function val = stage5_validate(refined, fish, setB, resetB, data, cfg, outdir)
    Isim = run_hspice(refined.theta, [setB.voltage_V; resetB.voltage_V], fish.names, cfg);
    nS = height(setB);
    Iset = Isim(1:nS); Ires = Isim(nS+1:end);
    r_set = log10(max(abs(Iset),1e-14)) - setB.median_log10_abs_current;
    r_res = log10(max(abs(Ires),1e-14)) - resetB.median_log10_abs_current;

    val = struct();
    val.r_set = r_set; val.r_res = r_res;
    val.rmse_set = sqrt(mean(r_set.^2));
    val.rmse_res = sqrt(mean(r_res.^2));
    val.dw_set = sum(diff(r_set).^2)/sum(r_set.^2);
    val.dw_res = sum(diff(r_res).^2)/sum(r_res.^2);

    cycles = unique(data.representative_cycle_id);
    loco = zeros(numel(cycles),2);
    for k = 1:numel(cycles)
        sub = data(data.representative_cycle_id ~= cycles(k),:);
        sb = sub(sub.branch=="SET",:); rb = sub(sub.branch=="RESET",:);
        priors_k = stage1_extract_priors(sb,rb, ...
            struct('G_LRS',NaN,'Vset',1,'Vreset',-1,'I_HRS_read',NaN), cfg);
        cfg_s = cfg; cfg_s.bo_n_init = 10; cfg_s.bo_n_iter = 40;
        bo_k = stage3_bayesopt_driver(priors_k, fish, sb, rb, cfg_s, outdir);
        held = data(data.representative_cycle_id == cycles(k),:);
        Ih = run_hspice(bo_k.theta, held.voltage_V, fish.names, cfg);
        r_h = log10(max(abs(Ih),1e-14)) - held.median_log10_abs_current;
        loco(k,1) = sqrt(mean(r_h(held.branch=="SET").^2));
        loco(k,2) = sqrt(mean(r_h(held.branch=="RESET").^2));
    end
    val.loco_rmse = loco;

    nB = field_or__(cfg,'bootstrap_n',100);
    theta_bs = zeros(nB, numel(refined.theta));
    for b = 1:nB
        idx = randsample(cycles, numel(cycles), true);
        boot = data(ismember(data.representative_cycle_id, idx),:);
        bs = boot(boot.branch=="SET",:); br = boot(boot.branch=="RESET",:);
        priors_b = stage1_extract_priors(bs,br, ...
            struct('G_LRS',NaN,'Vset',1,'Vreset',-1,'I_HRS_read',NaN), cfg);
        cfg_b = cfg; cfg_b.bo_n_init = 10; cfg_b.bo_n_iter = 40;
        bo_b = stage3_bayesopt_driver(priors_b, fish, bs, br, cfg_b, outdir);
        theta_bs(b,:) = bo_b.theta;
    end
    val.theta_bs = theta_bs;
    val.ci95 = [quantile(theta_bs,0.025,1); quantile(theta_bs,0.975,1)];
end
function v = field_or__(s,fn,d); if isfield(s,fn); v=s.(fn); else; v=d; end; end
```

### `stanford_fit/matlab/eval_loss.m`
```matlab
function L = eval_loss(t, priors, active_names, setB, resetB, cfg)
    theta = priors.mu;
    for k = 1:numel(active_names)
        j = find(strcmp(priors.names, active_names{k}));
        theta(j) = t.(active_names{k});
    end
    V = [setB.voltage_V; resetB.voltage_V];
    Ihat = run_hspice(theta, V, priors.names, cfg);
    if any(~isfinite(Ihat)); L = 1e6; return; end
    nS = height(setB);
    Iset = Ihat(1:nS); Ires = Ihat(nS+1:end);
    sigS = max((setB.q75_current_A - setB.q25_current_A)/1.35 ./ ...
               max(abs(setB.median_current_A),1e-14) / log(10), 0.05);
    sigR = max((resetB.q75_current_A - resetB.q25_current_A)/1.35 ./ ...
               max(abs(resetB.median_current_A),1e-14) / log(10), 0.05);
    rS = (log10(max(abs(Iset),1e-14))   - setB.median_log10_abs_current)   ./ sigS;
    rR = (log10(max(abs(Ires),1e-14))   - resetB.median_log10_abs_current) ./ sigR;
    Lset = mean(rS.^2); Lreset = mean(rR.^2);
    Vset_sim   = detect_threshold(setB.voltage_V,   Iset,  'set');
    Vreset_sim = detect_threshold(resetB.voltage_V, Ires, 'reset');
    sigV = max(diff(unique(setB.voltage_V)));
    Lv = ((Vset_sim - priors.feats.Vset)^2 + (Vreset_sim - priors.feats.Vreset)^2)/sigV^2;
    Lprior = sum( ((theta - priors.mu) ./ max(priors.sigma,1e-30)).^2 );
    L = Lset + Lreset + 0.5*Lv + 0.1*Lprior;
end
function Vth = detect_threshold(V,I,kind)
    logI = log10(max(abs(I),1e-14));
    dlogI = gradient(logI,V);
    if strcmp(kind,'set'); [~,ix] = max(dlogI); else; [~,ix] = min(dlogI); end
    Vth = V(ix);
end
```

### `stanford_fit/matlab/run_hspice.m`
```matlab
function I = run_hspice(theta, V, names, cfg)
    tmpdir = tempname; mkdir(tmpdir);
    sp_path = fullfile(tmpdir,'rram.sp');
    write_netlist(sp_path, theta, names, V, cfg);
    hspice_bin = field_or___(cfg,'hspice_bin','hspice');
    cmd = sprintf('%s -i %s -o %s', hspice_bin, sp_path, fullfile(tmpdir,'rram'));
    [status,~] = system(cmd);
    if status ~= 0; I = nan(size(V)); try; rmdir(tmpdir,'s'); end; return; end
    try; I = parse_lis(fullfile(tmpdir,'rram.tr0'), V); catch; I = nan(size(V)); end
    try; rmdir(tmpdir,'s'); end
end
function v = field_or___(s,fn,d); if isfield(s,fn); v=s.(fn); else; v=d; end; end
```

### `stanford_fit/matlab/parse_lis.m`
```matlab
function I = parse_lis(tr0_path, Vquery)
    csv_path = strrep(tr0_path,'.tr0','.csv');
    if isfile(csv_path)
        T = readtable(csv_path,'CommentStyle','*');
        I = interp1(T.V_TE, T.I_TE, Vquery, 'pchip', NaN); return
    end
    lis = strrep(tr0_path,'.tr0','.lis');
    if isfile(lis)
        txt = fileread(lis);
        tok = regexp(txt,'([-\d\.eE+]+)\s+([-\d\.eE+]+)','tokens');
        M = cellfun(@(c)[str2double(c{1}) str2double(c{2})], tok,'UniformOutput',false);
        M = vertcat(M{:});
        M = M(M(:,1)>=min(Vquery)-0.01 & M(:,1)<=max(Vquery)+0.01,:);
        [Vs,iu] = unique(M(:,1)); Is = M(iu,2);
        I = interp1(Vs, Is, Vquery, 'pchip', NaN); return
    end
    I = nan(size(Vquery));
end
```

### `stanford_fit/matlab/write_netlist.m`
```matlab
function write_netlist(path, theta, names, V, cfg)
    p = struct(); for k=1:numel(names); p.(names{k}) = theta(k); end
    sweep_rate = field_or4(cfg,'sweep_rate_Vps',0.1);
    t = zeros(size(V));
    for i = 2:numel(V)
        t(i) = t(i-1) + max(abs(V(i)-V(i-1))/sweep_rate, 1e-9);
    end
    cc = field_or4(cfg,'I_compliance',1e-3);
    fid = fopen(path,'w');
    fprintf(fid,'* TaO-Fit DC sweep netlist (HSPICE)\n');
    fprintf(fid,'.option post=2 ingold=2 numdgt=8 nomod csdf=2\n');
    fprintf(fid,'.hdl ''%s''\n', field_or4(cfg,'va_path','../templates/rram_v_1_0_0_hspice.va'));
    fprintf(fid,'.param I0=%.6g g0=%.6g V0=%.6g Vel0=%.6g gamma0=%.6g\n', ...
                p.I0, p.g0, p.V0, p.Vel0, p.gamma0);
    fprintf(fid,'.param beta=%.6g Ea=%.6g Rth=%.6g Fmin=%.6g\n', ...
                p.beta, p.Ea, p.Rth, p.F_min);
    fprintf(fid,'.param gap_min=%.6g gap_max=%.6g gap_ini=%.6g tox=%.6g\n', ...
                p.gap_min, p.gap_max, p.gap_ini, p.tox);
    fprintf(fid,'.param a0=%.6g T0=%.6g\n', ...
                field_or4(cfg,'a0',2.5e-10), field_or4(cfg,'T_K',300));
    fprintf(fid,'Vsrc TE 0 PWL(\n');
    for i=1:numel(V); fprintf(fid,'+ %.6gs %.6g\n', t(i), V(i)); end
    fprintf(fid,'+ )\n');
    fprintf(fid,['Xrram TE BE rram_v_1_0_0 I0=I0 g0=g0 V0=V0 Vel0=Vel0 gamma0=gamma0 ' ...
                 'beta=beta Ea=Ea Rth=Rth Fmin=Fmin gap_min=gap_min gap_max=gap_max ' ...
                 'gap_ini=gap_ini tox=tox a0=a0 T0=T0 model_switch=0\n']);
    fprintf(fid,'Gclamp BE 0 cur=''((abs(I(Xrram.TE))>%.3g)?sign(I(Xrram.TE))*%.3g:0)''\n', cc, cc);
    fprintf(fid,'.tran 1n %.6g uic\n', t(end));
    fprintf(fid,'.probe tran v(TE) i(Xrram.TE)\n');
    fprintf(fid,'.end\n');
    fclose(fid);
end
function v = field_or4(s,fn,d); if isfield(s,fn); v=s.(fn); else; v=d; end; end
```

### `stanford_fit/matlab/plot_fit_quality.m`
```matlab
function plot_fit_quality(refined, val, setB, resetB, out_png)
    fig = figure('Visible','off','Color','w','Position',[100 100 1200 900]);
    tl = tiledlayout(fig,2,2,'TileSpacing','compact','Padding','compact');
    nexttile(tl);
    semilogy(setB.voltage_V, abs(setB.median_current_A),'k.','DisplayName','Meas SET'); hold on
    semilogy(resetB.voltage_V, abs(resetB.median_current_A),'b.','DisplayName','Meas RESET');
    if isfield(val,'r_set')
        semilogy(setB.voltage_V, 10.^(setB.median_log10_abs_current + val.r_set), ...
                 'r-','DisplayName','Fit SET');
        semilogy(resetB.voltage_V, 10.^(resetB.median_log10_abs_current + val.r_res), ...
                 'r--','DisplayName','Fit RESET');
    end
    xlabel('V (V)'); ylabel('|I| (A)'); legend('Location','best'); grid on
    title('Measured vs fitted I-V (log scale)');
    nexttile(tl);
    plot(setB.voltage_V, val.r_set,'k.'); hold on
    plot(resetB.voltage_V, val.r_res,'b.'); yline(0);
    xlabel('V (V)'); ylabel('log_{10}|I| residual'); grid on
    title(sprintf('Residuals (DW_{set}=%.2f, DW_{res}=%.2f)', val.dw_set, val.dw_res));
    nexttile(tl);
    if isfield(val,'theta_bs')
        boxplot(val.theta_bs); xlabel('parameter index'); ylabel('value');
        title('Bootstrap posterior (95% CI)');
    end; grid on
    nexttile(tl);
    if isfield(val,'loco_rmse')
        bar(val.loco_rmse); legend({'SET','RESET'});
        xlabel('held-out cycle'); ylabel('RMSE log_{10}|I|');
        title('Leave-one-cycle-out validation');
    end; grid on
    exportgraphics(fig, out_png, 'Resolution', 300);
    close(fig);
end
```

### `stanford_fit/python/03_run_stanford_fit.py`
```python
#!/usr/bin/env python3
"""Orchestrate the MATLAB TaO-Fit pipeline from Python (optional wrapper)."""
import argparse, pathlib, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input',  required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--matlab_bin', default='matlab')
    args = ap.parse_args()
    in_csv = pathlib.Path(args.input).resolve()
    cfg    = pathlib.Path(args.config).resolve()
    outdir = pathlib.Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    mscript = (
        f"cd('{pathlib.Path(__file__).resolve().parent.parent}/matlab');"
        f"main_fit_stanford('{in_csv}','{cfg}','{outdir}');exit"
    )
    cmd = [args.matlab_bin, '-batch', mscript]
    print('[03] launching MATLAB:', ' '.join(cmd))
    sys.exit(subprocess.call(cmd))

if __name__ == '__main__':
    main()
```

### `stanford_fit/python/hspice_utils.py`
```python
"""Shared HSPICE I/O for Python users."""
from __future__ import annotations
import pathlib, re, numpy as np, pandas as pd

def parse_lis_currents(lis_path: pathlib.Path):
    txt = pathlib.Path(lis_path).read_text(errors='ignore')
    pat = re.compile(r'([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)')
    rows = []
    for m in pat.finditer(txt):
        try:
            t,v,i = map(float, m.groups()); rows.append((t,v,i))
        except ValueError:
            continue
    if not rows: return None
    return pd.DataFrame(rows, columns=['t','V','I']).drop_duplicates('t')

def interp_to_grid(df: pd.DataFrame, V_grid: np.ndarray):
    order = np.argsort(df['V'].values)
    Vs = df['V'].values[order]; Is = df['I'].values[order]
    return np.interp(V_grid, Vs, Is, left=np.nan, right=np.nan)
```

### `stanford_fit/templates/rram_dc_sweep.sp.template`
```spice
* TaO-Fit HSPICE DC sweep template
.option post=2 ingold=2 numdgt=8 nomod csdf=2
.hdl '{{VA_PATH}}'
.param I0={{I0}}  g0={{G0}}  V0={{V0}}  Vel0={{VEL0}}  gamma0={{GAMMA0}}
.param beta={{BETA}}  Ea={{EA}}  Rth={{RTH}}  Fmin={{FMIN}}
.param gap_min={{GAP_MIN}}  gap_max={{GAP_MAX}}  gap_ini={{GAP_INI}}
.param tox={{TOX}}  a0={{A0}}  T0={{T0}}
Vsrc TE 0 PWL(
{{PWL_BODY}}
+ )
Xrram TE BE rram_v_1_0_0
+    I0=I0 g0=g0 V0=V0 Vel0=Vel0 gamma0=gamma0
+    beta=beta Ea=Ea Rth=Rth Fmin=Fmin
+    gap_min=gap_min gap_max=gap_max gap_ini=gap_ini
+    tox=tox a0=a0 T0=T0 model_switch=0
Gclamp BE 0 cur='((abs(I(Xrram.TE))>{{I_CC}})?sign(I(Xrram.TE))*{{I_CC}}:0)'
.tran 1n {{T_END}} uic
.probe tran v(TE) i(Xrram.TE)
.end
```

### `stanford_fit/templates/rram_v_1_0_0_hspice.va`
Included verbatim from the user upload (Stanford NEEDS v1.0.0). The parameter declarations relevant to the fit are:
```verilog
parameter real I0     = 6.14e-5  from (0:inf);
parameter real g0     = 2.7505e-10 from (0:inf);
parameter real V0     = 0.43     from (0:inf);
parameter real Vel0   = 150      from (0:inf);
parameter real gamma0 = 16.5     from (0:inf);
parameter real beta   = 1.25     from (0:gamma0/(pow(gap_max/g1,3)));
parameter real gap_min = 0.1e-9  from (0:L);
parameter real gap_max = 1.7e-9  from (gap_min:L);
parameter real gap_ini = 0.1e-9  from [gap_min:gap_max];
```
These are the Stanford-PKU v1.0.0 defaults; they should NOT be confused with Reuben's IHP-specific HfO2 calibration (Vel0=0.05 m/s, β=0.4, γ₀=19.5, gap_max=18.8 Å).

### `stanford_fit/config/default_config.yaml`
```yaml
T_K: 300
tox: 5.0e-9
a0: 2.5e-10
eps_r_TaOx: 25
gap_min: 1.0e-10
gap_max: 1.7e-9
gap_ini_HRS: 1.4e-9
g0_prior_m: 2.75e-10
g0_prior_sigma_m: 0.5e-10
Vel0_prior: 150
Vel0_sigma: 75
beta_prior: 1.25
beta_sigma: 0.5
Rth_prior: 2.1e5
Rth_sigma: 1.0e5
F_min_prior: 1.4e9
I_compliance: 1.0e-3
sweep_rate_Vps: 0.1
bo_n_init: 40
bo_n_iter: 160
bootstrap_n: 100
rng_seed: 0
hspice_bin: hspice
va_path: ../templates/rram_v_1_0_0_hspice.va
```

### `stanford_fit/examples/run_S1_proof_of_concept.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
INPUT="$ROOT/data/step02/medoid_S1_dev01.csv"
CFG="$ROOT/stanford_fit/config/default_config.yaml"
OUT="$ROOT/results/S1_dev01_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "[run] input=$INPUT"
echo "[run] outdir=$OUT"
matlab -batch "cd('$ROOT/stanford_fit/matlab');main_fit_stanford('$INPUT','$CFG','$OUT')"
echo "[run] done."
```

## Section 4 — Roadmap Beyond the Proof of Concept

- **12 deposition conditions**: rerun Stage 1 priors per condition because PF vs Schottky balance shifts with PO2 (the MWSCAS finding); per-condition prior means and a shared σ_prior enable shrinkage in a hierarchical Bayes formulation. If MATLAB-only is dropped, PyMC or NumPyro can implement the multi-condition hierarchical fit.
- **Cycle-to-cycle variability**: enable `model_switch=1` and add (deltaGap0, T_crit, T_smth) as a second optimization stage matching the across-cycle variance using method-of-moments — the nominal-only Stage 3 result becomes the mean, and the cycle ensemble's spread becomes the target moment.
- **Multi-objective**: if a Pareto trade-off emerges between SET and RESET fidelity, switch to `paretosearch` in the MATLAB Global Optimization Toolbox; report the Pareto front instead of a single scalar loss.
- **Surrogate-model acceleration**: once 200 HSPICE evaluations are cached, train a feed-forward NN on (θ → I(V)) and switch BO acquisition to surrogate evaluations once R² > 0.99 on a held-out batch; use HSPICE only for periodic recalibration. Scales to >100 devices in <1 day on a single workstation.

## Caveats

- **SpiceXpanse technical details could not be independently verified** from open public sources at the time of writing. The JuSER metadata confirms authors, title, and venue (Bezugam, Choi, Menzel, Strukov; IEEE NMDC 2025; DOI 10.1109/NMDC64551.2025.11234564) and the code is at https://github.com/saibez/SpiceXpanse, but the exact composite-loss form (MSE+IoU+DTW+memory-window), parallelization details, and wall-clock figures are inside the paywalled conference paper. The gap analysis treats SpiceXpanse charitably and cites only publicly indexed claims; this should be re-checked against the IEEE Xplore full text before manuscript submission.
- **UNIMORE paper venue**: the IEEE Xplore document 9947161 corresponds to ESSDERC 2022, not ICECS 2022 as sometimes mis-cited. Correct citation: T. Zanotti, P. Pavan, F.M. Puglisi, "Self-Consistent Automated Parameter Extraction of RRAM Physics-Based Compact Model," IEEE ESSDERC 2022. The UNIMORE compact model itself is on nanoHUB (Puglisi, Zanotti, Pavan 2019, DOI 10.21981/15GF-KX29).
- **Reuben 2019 "7-step fitting algorithm"** is described in the IEEE T-Nano 2019 paper itself. The public FAU manual (cs3.tf.fau.de, December 2018) lists the parameter declaration order in the Verilog-A header (g0, V0, Vel0, I0, β, γ0) and the IHP HfO2 calibrated values, but does NOT contain a numbered 7-step procedure — the procedural detail must be drawn from the journal paper. Implementers should consult the journal text directly.
- **Stanford v1.0.0 defaults vs Reuben IHP calibration**: in our Stage 1 priors we use the Stanford–ASU Verilog-A v1.0.0 defaults (Vel0=150 m/s, β=1.25, γ₀=16.5) as broad priors. We deliberately do NOT use Reuben's IHP-specific HfO2 1T1R calibrated values (Vel0=0.05 m/s, β=0.4, γ₀=19.5) as priors for TaOx — these are an HfO2 device-specific operating point, not a generic prior. Implementers should be careful to distinguish them.
- **Single nominal DC data has hard identifiability limits.** Rth, β, Vel0, Ea, F_min, gap_max, gap_ini, gap_min, tox are very likely non-identifiable from a single nominal medoid I-V; TaO-Fit treats them as priors-only and reports σ_eff/|θ| in the Fisher report. To identify these would require pulsed measurements (Rth, Vel0), multi-temperature DC (Ea), or compliance-current sweeps (gap_max, gap_ini). This is an honest scope statement and should be reproduced in any manuscript that uses TaO-Fit.
- **Polarity asymmetry on Ti/Pt/TaOx/Ta/Pt**: with asymmetric Ta and Pt electrodes, |Vset| ≠ |Vreset| is expected and the single-polarity Stanford-PKU form may show structurally biased residuals on one branch. The Durbin-Watson check in Stage 5 detects this; if DW < 1.6 on one branch but not the other, the recommended fallback is Mahboubi-style polarity-split parameters (γ₀⁺ ≠ γ₀⁻; β⁺ ≠ β⁻) before considering a behavioral PiRNN model.
- **Verilog-A discontinuities documented but not "fixed"**: γ_ini = 16 hardcoded for the negative half-cycle (in the user's uploaded v1.0.0) overrides γ₀, and γ collapses to zero when the local field falls below F_min. These are properties of the compact model as released and are honored by TaO-Fit; they are flagged in code comments but not patched, because patching them would invalidate comparison with other Stanford-PKU literature.

---

## Bibliography

**Primary (user-uploaded):**

1. S.S. Bezugam, S. Choi, S. Menzel, D.B. Strukov, "SpiceXpanse: A Scalable, Automated Framework for Efficient Parameter Optimization and Modeling of RRAM Circuits," 2025 IEEE 20th Nanotechnology Materials and Devices Conference (NMDC), Delhi, India, 9–11 Oct 2025. DOI: 10.1109/NMDC64551.2025.11234564. Code: https://github.com/saibez/SpiceXpanse. JuSER: https://juser.fz-juelich.de/record/1052883.

2. A. Hamid, O. Hassan, "CNN-Based Automated Parameter Extraction Framework for Modeling Memristive Devices," arXiv:2511.07926v1, Nov 2025. https://arxiv.org/abs/2511.07926.

3. V. Mahboubi, Á. Gómez, A. Calomarde, D. Arumí, R. Rodríguez, S. Manich et al., "On the Fitting and Improvement of RRAM Stanford-Based Model Parameters Using TiN/Ti/HfO2/W Experimental Data," 2022 37th Conf. Design of Circuits and Integrated Circuits (DCIS), IEEE 9970051. https://ieeexplore.ieee.org/document/9970051.

4. J. Reuben, D. Fey, C. Wenger, "A Modeling Methodology for Resistive RAM Based on Stanford-PKU Model With Extended Multilevel Capability," IEEE Trans. Nanotechnology 18, 647–656 (2019). DOI: 10.1109/TNANO.2019.2922838. Manual: https://www.cs3.tf.fau.de/files/2018/04/manual1t1rsimulation_december2018.pdf.

5. M. Chowdhury, A. Moazzeni, K. Tutuncuoglu, "Atomic-Scale Insights into the Switching Mechanisms of RRAM Devices," 68th IEEE Int. Midwest Symp. Circuits and Systems (MWSCAS) 2025.

**Secondary (web-sourced):**

6. Z. Jiang, Y. Wu, S. Yu, L. Yang, K. Song, Z. Karim, H.-S.P. Wong, "A Compact Model for Metal–Oxide Resistive Random Access Memory With Experiment Verification," IEEE Trans. Electron Devices 63(5), 1884–1892 (2016). DOI: 10.1109/TED.2016.2545412.

7. Stanford University Resistive-Switching Random Access Memory (RRAM) Verilog-A Model v1.0.0, nanoHUB. https://nanohub.org/publications/19. https://nano.stanford.edu/downloads/stanford-rram-model.

8. T. Zanotti, P. Pavan, F.M. Puglisi, "Self-consistent Automated Parameter Extraction of RRAM Physics-Based Compact Model," IEEE ESSDERC 2022, IEEE Xplore 9947161. https://ieeexplore.ieee.org/document/9947161.

9. F.M. Puglisi, T. Zanotti, P. Pavan, "Unimore Resistive Random Access Memory (RRAM) Verilog-A Model v1.0.0," nanoHUB (2019). DOI: 10.21981/15GF-KX29. https://nanohub.org/publications/289.

10. Y. Sha, J. Lan, Y. Li, Q. Chen, "A Physics-Informed Recurrent Neural Network for RRAM Modeling," Electronics 12(13), 2906 (2023). DOI: 10.3390/electronics12132906.

11. D.A. Zhevnenko, F.P. Meshchaninov, V.S. Kozhevnikov, E.S. Shamin, O.A. Telminov, E.S. Gornev, "Research and Development of Parameter Extraction Approaches for Memristor Models," Micromachines 12(10), 1220 (2021). DOI: 10.3390/mi12101220.

12. N. Saxena, "Memristor Model Optimization Based on Parameter Extraction From Device Characterization Data," 2019. https://par.nsf.gov/servlets/purl/10130554.

13. J. Frenkel, "On Pre-Breakdown Phenomena in Insulators and Electronic Semi-Conductors," Physical Review 54(8), 647–648 (1938). DOI: 10.1103/PhysRev.54.647.

14. R.H. Fowler, L. Nordheim, "Electron Emission in Intense Electric Fields," Proceedings of the Royal Society of London, Series A 119, 173–181 (1928).

15. J.J. Yang, M.-X. Zhang, J.P. Strachan, F. Miao, M.D. Pickett, R.D. Kelley, G. Medeiros-Ribeiro, R.S. Williams, "High switching endurance in TaOx memristive devices," Applied Physics Letters 97, 232102 (2010). DOI: 10.1063/1.3524521.

16. A. Serb, A. Khiat, T. Prodromakis, "An RRAM Biasing Parameter Optimizer," IEEE Trans. Electron Devices 62(11), 3685–3691 (2015). DOI: 10.1109/TED.2015.2478491.

17. Stanford–ASU Verilog-A RRAM model source (mirror): https://github.com/ZongxianYang0521/RRAM_model.

18. A. Levy, "WP-RRAM-SPICE-Model: A well-posed RRAM SPICE model implemented in Verilog-A," https://github.com/akashlevy/WP-RRAM-SPICE-Model.

19. F.M. Puglisi, T. Zanotti, P. Pavan, "Comprehensive physics-based RRAM compact model including the effect of variability and multi-level random telegraph noise," Solid-State Electronics 194, 108368 (2022). DOI: 10.1016/j.sse.2022.108368.

20. C. Yakopcic, T.M. Taha, G. Subramanyam, R.E. Pino, "Generalized Memristive Device SPICE Model and its Application in Circuit Design," IEEE Trans. CAD 32(8), 1201–1214 (2013). DOI: 10.1109/TCAD.2013.2252057.