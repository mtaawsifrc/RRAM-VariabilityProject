## Bottom line

I would not submit the current version yet. The central idea—reporting generalization, identifiability, and mechanism validity together—is strong, and the repository contains a much richer dataset than the paper currently exploits. But several headline conclusions are presently overstated or supported by non-independent tests.

No intervention can honestly guarantee an 80% IEEE acceptance probability. With the existing analysis, I would expect major-review or rejection risk. With the population-level and model-validity upgrades below, this could become a genuinely competitive TNANO/TDMR paper; TED would probably require additional temperature/rate measurements.

## Most serious problems

1. **The fitted result is not one deployable compact model.**

   SET and RESET are simulated separately using different \(V_0,E_a,F_{\min},\nu_0,g_{\max},g_{\mathrm{ini}}\) values and independent initial states [simulate_branches.m](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/stanford_fit/matlab/simulate_branches.m:1). The released Verilog-A device has one parameter set and one continuous state trajectory. Consequently, the current fit cannot yet be dropped into a circuit and reproduce alternating SET/RESET operations as claimed around [main_alt_codex.tex](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/Latex_main/main_alt_codex.tex:775).

   More seriously, compliance is applied by clipping the current after HSPICE finishes. The unclipped current still drives temperature and gap evolution inside HSPICE [write_netlist.m](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/stanford_fit/matlab/write_netlist.m:1). That state evolution is not physically equivalent to an SMU-limited experiment.

2. **The “out-of-sample” test is not genuinely held out.**

   All cycles are used to choose the medoid, so the supposed test cycles influence the training target. The validation code then scores every cycle without removing the medoid itself [08_paper_alt_figures.py](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/08_paper_alt_figures.py:245).

   The paper’s statement that every in-sample value lies within the held-out IQR is also false. Recalculation from the archived data gives only 14 of 24 condition–branch cases inside the IQR. S1 RESET has a 0.310-decade gap—45% of its in-sample error—despite the small average gap. No equivalence test was performed, so “statistically indistinguishable” should not be claimed.

3. **Only 12 quality-selected devices are analyzed despite a very large population.**

   The repository has 545 devices and 10,871 accepted cycles. The paper uses one device per condition and 461 cycles—about 4% of the available cycles. Devices are selected primarily by maximum good-cycle count [02_select_device_representative_curve.py](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/02_select_device_representative_curve.py:20), creating selection bias toward unusually well-characterized devices.

   This prevents the paper from supporting process-wide or device-population conclusions. The four center samples are insufficient to conclude that device-to-device differences are “mostly cycling rather than fabrication.”

4. **The Schottky classification is not yet convincing physical proof.**

   The code compares BIC values calculated after different response transformations—\(\ln I\), \(\ln(I/V)\), and \(\ln(I/V^2)\) [02c_classify_conduction_regimes.py](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/02c_classify_conduction_regimes.py:59). Those residual likelihoods are not directly comparable without transformation Jacobians and a common observation model.

   Additional problems:

   - “States” are split at voltage turnaround, not at the actual switching event.
   - The \([1,60]\) permittivity range is used to admit Schottky/PF candidates and is later presented as evidence confirming them. That is circular.
   - Room-temperature DC linearization alone normally cannot decisively distinguish Schottky, PF, trap-assisted tunneling, or mixed conduction.

5. **The identifiability calculations contain methodological defects.**

   - Fisher sensitivities are already derivatives with respect to log parameters, so the inverse-Fisher diagonal approximates relative uncertainty. Dividing it by the physical parameter again is dimensionally incorrect [stage2_identifiability.m](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/stanford_fit/matlab/stage2_identifiability.m:43).
   - Reported Fisher spans of \(10^{37}\)–\(10^{66}\) cannot be numerically resolved in double precision. They demonstrate rank deficiency, not quantitatively meaningful “orders of magnitude.”
   - The “profile likelihood” fixes every nuisance parameter rather than reoptimizing them. It is a one-dimensional objective slice, not a profile likelihood.
   - Profile files are stale: for S1, the profile reports an optimum loss of 26.55 while the current refined artifact reports 18.79.
   - Bootstrap fits use only 32 BO evaluations and no local refinement, versus hundreds for the point estimate. The resulting distribution mixes cycle variability with optimization-budget bias.
   - Reporting the bootstrap median merely so it lies inside its own interval “by construction” does not solve the estimator mismatch.

6. **The deposition trend is statistically fragile.**

   A six-coefficient response surface is fit to twelve sample-level values. The two claimed SET effects have borderline \(p=0.0265\) and \(p=0.0444\), without multiplicity correction or propagation of parameter uncertainty. They would not survive even a simple two-test Bonferroni correction. A nonsignificant lack-of-fit test is also not evidence that lack of fit is absent.

7. **The switching-threshold objective is unreliable.**

   The derivative-based detector selects the 0-V boundary as the switching point in nearly every archived condition. S10 is the exception and consequently has an objective near 793 while comparable conditions are around 20–47. This indicates a boundary artifact and explains the unexplained S10 loss anomaly.

8. **The ablation does not establish physical superiority.**

   Regime conditioning performs essentially the same—or slightly worse—than uninformative BO in RMSE. Without synthetic parameter-recovery experiments or an independently validated mechanism, it cannot show that down-weighting prevents “parameter distortion.” Multiple optimizer seeds and convergence comparisons are also absent.

9. **Results provenance is inconsistent.**

   The manuscript’s fit values come from the regime-conditioned variability/ablation runs, whereas the Fisher figure comes from different `*_taofit` fits. Stale profile files coexist with newer results. The main script continues after failed stages and still prints “Done” [run_full_pipeline.sh](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/run_full_pipeline.sh:20). Tables and abstract numbers are manually hardcoded.

10. **Novelty is positioned against an outdated baseline.**

   Automated Stanford-model extraction and D2D/C2C statistical calibration are already active topics. Examples include a [2022 Stanford-model D2D/C2C extraction method](https://www.sciencedirect.com/science/article/pii/S0038110122000934), a [2025 CNN-based Stanford extractor](https://arxiv.org/abs/2511.07926), and variability-aware compact models validated across operating conditions [Microelectronic Engineering, 2022](https://www.sciencedirect.com/science/article/pii/S0167931722001800). Automation and bootstrap fitting alone are therefore insufficient novelty.

## Best improvement path

### 1. Exploit the existing 545-device dataset

This is the highest-return improvement and requires no new fabrication.

Build a hierarchical analysis:

\[
y_{s,d,c}=f(\mathrm{O_2},P)+u_s+u_{s,d}+u_{s,d,c},
\]

where sample/deposition run, device, and cycle are separate levels. First analyze direct observables—\(V_\mathrm{SET}\), \(V_\mathrm{RESET}\), HRS/LRS conductance, memory window, Schottky-like slope—before compact-model parameters.

Use device-level train/test splits:

- select the model and medoid only from training devices;
- validate on completely untouched devices;
- report predictive interval coverage, not only median RMSE;
- keep deposition-run inference separate from within-wafer device replication.

This turns the work from “twelve example devices” into a population compact-model study.

### 2. Produce one continuous, circuit-usable model

Fit a complete SET–RESET waveform in one HSPICE transient with one evolving gap state. If polarity asymmetry is essential, implement it explicitly and smoothly in one Verilog-A instance.

Model the B1500 compliance inside the circuit so the limited current controls Joule heating and state evolution. Validate the final file on:

- multiple consecutive DC cycles;
- at least one pulse sequence;
- an unseen device;
- a simple 1T1R circuit.

### 3. Make the Schottky result the physical novelty—but verify it

Add a state-dependent barrier current to the Stanford filament current, for example a smooth parallel Schottky branch active at large gap. Compare:

1. original Stanford model;
2. Stanford plus Schottky branch;
3. an empirical flexible baseline.

Use leave-device-out likelihood/RMSE, residual autocorrelation, and information criteria on the same untransformed log-current likelihood. The existing systematic RESET error gives strong motivation.

For definitive mechanism discrimination, collect a modest temperature dataset, perhaps 250–350 K on the low-, center-, and high-oxygen conditions. Temperature-dependent conduction analysis is a recognized route for separating transport mechanisms, as demonstrated in [temperature-dependent RRAM studies](https://research.ibm.com/publications/temperature-dependent-studies-of-the-electrical-properties-and-the-conduction-mechanism-of-hfox-based-rram).

### 4. Turn identifiability into experimental design

Use corrected SVD/Fisher or true profile likelihood to determine which measurements would identify the sloppy directions. Then collect a small targeted matrix:

- 3–5 voltage ramp rates;
- 2–3 compliance currents;
- 3 temperatures;
- several devices at three DOE conditions.

Jointly fitting rate and temperature data would separate \(E_a\) from \(\nu_0\), while compliance variation would inform filament/gap and resistance parameters. “Identifiability-guided measurement design” is a stronger journal contribution than merely declaring parameters nonidentifiable.

### 5. Repair the statistical foundation

- Use true nested holdout and equivalence tests with a predeclared acceptable margin.
- Reoptimize nuisance parameters for genuine profile likelihoods.
- Use the same estimator and optimization budget for point and bootstrap fits.
- Repeat optimization across seeds to quantify algorithmic variance.
- Replace raw CV with log-scale interval widths and predictive uncertainty.
- Fit DOE effects with hierarchical weighting and multiplicity-aware intervals.
- Present “failure to detect lack of fit,” not “no lack of fit.”

## Recommended reframed contribution

A stronger title/story would be:

> **Population-Validated and Identifiability-Guided Calibration of a Hybrid Stanford–Schottky TaOₓ RRAM Model Across a Deposition DOE**

The defensible novelty would then be:

- population validation across hundreds of devices;
- one circuit-deployable hybrid physical model;
- separation of cycle, device, and process variability;
- identifiability-guided selection of new measurements;
- genuine unseen-device prediction.

## Abstract and presentation

The DOCX is an extended summary, not an abstract. It also:

- contains the literal text `TaO$_x$` in the title;
- says it contains eight figures but embeds ten [build_abstract.py](/home/hm5701/Documents/PINN/Variability_Project_v0.0.5/Latex_Abstract/build_abstract.py:275);
- hardcodes every numerical result;
- repeats the unsupported generalization, Schottky-confirmation, Fisher-span, and variance-component claims;
- contains no state-of-the-art citations.

The manuscript layout is generally professional, but Figs. 2, 5–8 are too dense at IEEE column size. Move diagnostic heatmaps and full condition tables to supplementary material and keep four main figures centered on population validation, hybrid-model improvement, hierarchical process effects, and circuit/pulse validation.

My priority order would be: fix continuous-model/compliance correctness → use all devices with nested validation → correct mechanism and identifiability statistics → add targeted temperature/rate data → rewrite the paper and abstract.
