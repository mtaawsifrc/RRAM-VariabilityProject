# Codebase Guide For RRAM Variability And Stanford Model Fitting

This guide explains the research purpose and software structure of this
repository. It is written for a PhD student who needs to understand, present,
publish, and defend the workflow: from measured RRAM device data, through
representative-cycle extraction, to Stanford-PKU compact-model simulation and
TaO-Fit parameter fitting.

The short version:

- The raw experiment is a resistive random-access memory (RRAM) variability
  study across deposition conditions.
- The measured data are many B1500 I-V CSV files from devices and cycles.
- The first Python scripts clean the raw measurements and choose a defensible
  representative device/cycle.
- The baseline script compares that representative curve to the Stanford-PKU
  RRAM Verilog-A compact model using HSPICE.
- The `stanford_fit/` MATLAB pipeline tries to turn this into a publishable
  fitting method with physics-informed priors, identifiability reporting,
  Bayesian optimization, local refinement, and validation diagnostics.

## Research Goal

The scientific goal is to connect experimental TaOx RRAM switching data to a
compact model in a way that is reproducible, physically interpretable, and
defensible for publication.

The research problem has several layers:

1. Experimental layer: measure SET/RESET I-V behavior across devices, cycles,
   and deposition conditions.
2. Variability layer: identify which devices and cycles are usable, typical,
   noisy, failed, or outlying.
3. Representation layer: reduce a large ensemble of cycles to a representative
   measured curve without cherry-picking.
4. Compact-model layer: simulate the Stanford-PKU RRAM model with HSPICE.
5. Fitting layer: estimate model parameters that reproduce measured SET/RESET
   behavior.
6. Identifiability layer: state which parameters are actually constrained by
   the available DC I-V data and which are prior-dominated.
7. Publication layer: produce plots, metrics, tables, and reproducible outputs
   that can be shown to an advisor, included in a paper, and defended during
   review.

This codebase is not just a plotting folder. It is a research pipeline for
turning raw experimental evidence into compact-model claims.

## Repository Roles

The repository has four major zones.

### Modern Pipeline

These files are the primary path:

- `01_extract_clean_cycles.py`
- `02_select_device_representative_curve.py`
- `03_run_stanford_baseline.py`
- `run_01.sh`
- `run_02.sh`
- `run_03.sh`
- `RUN_INSTRUCTIONS.md`

This path extracts clean cycles, selects a representative measured curve, and
runs a baseline Stanford model comparison.

### TaO-Fit Implementation

The `stanford_fit/` directory contains the more advanced fitting framework:

- `stanford_fit/python/03_run_stanford_fit.py`
- `stanford_fit/matlab/main_fit_stanford.m`
- `stanford_fit/matlab/stage1_extract_priors.m`
- `stanford_fit/matlab/stage2_identifiability.m`
- `stanford_fit/matlab/stage3_bayesopt_driver.m`
- `stanford_fit/matlab/stage4_local_refine.m`
- `stanford_fit/matlab/stage5_validate.m`
- `stanford_fit/matlab/eval_loss.m`
- `stanford_fit/matlab/simulate_branches.m`
- `stanford_fit/matlab/write_netlist.m`
- `stanford_fit/matlab/run_hspice.m`
- `stanford_fit/matlab/parse_lis.m`
- `stanford_fit/matlab/apply_compliance.m`
- `stanford_fit/config/default_config.yaml`
- `stanford_fit/config/fast_verify.yaml`
- `stanford_fit/templates/rram_v_1_0_0_hspice.va`

This path is where the research novelty lives: priors, identifiability,
optimization, and validation.

### Experimental Data Archive

The main raw data are under:

- `raw_data/S1`
- `raw_data/S2`
- `raw_data/S3`
- `raw_data/S4`
- `raw_data/S5`
- `raw_data/S6`
- `raw_data/S7`
- `raw_data/S8`
- `raw_data/S9`
- `raw_data/S10`
- `raw_data/S11`
- `raw_data/S12`

`Depos_Condition.csv` maps sample IDs to deposition conditions:

- `Sample`
- `Oxygen_pct`
- `Power_W`

This table is scientifically important because the variability and switching
behavior should eventually be interpreted as a function of processing
conditions.

### Historical Lab Archive

`DC endurance-DOE/` contains older scripts, figures, and raw/processed lab data.
Examples:

- `Vset Extraction.py`
- `histograp plot*.py`
- `folder plot.py`
- `I-V.py`
- `log-I-V.py`
- `Step 1-CDF-Extracting LRS and HRS.py`
- `Step 2-CDF data extraction-no plotting.py`
- `step 3-CDF Final.py`
- `memorywindow.py`
- `ltp amp.py`

These are mostly historical one-off scripts for specific figures or extraction
tasks. They support earlier analysis such as forming voltage histograms, SET
voltage histograms, LRS/HRS CDFs, and I-V plots. They are not the clean modern
pipeline, but they document how measurements were explored and how figures were
made during the research process.

## End-To-End Pipeline

The canonical run order is documented in `RUN_INSTRUCTIONS.md`.

The intended workflow is:

1. Install Python dependencies.
2. Put MATLAB and HSPICE on `PATH`.
3. Run `bash run_01.sh`.
4. Run `bash run_02.sh`.
5. Run `bash run_03.sh`.
6. Diagnose one TaO-Fit HSPICE call.
7. Run TaO-Fit.
8. Inspect `step01_S1/`, `step02_S1/`, `step03_S1_baseline/`, and `results/`.

The wrapper scripts currently target S1:

- `run_01.sh` reads `raw_data/S1` and writes `step01_S1`.
- `run_02.sh` reads `step01_S1` and writes `step02_S1`.
- `run_03.sh` reads the S1 representative curve and writes
  `step03_S1_baseline`.

For a publication-scale study, the same logic can be repeated across S1-S12.
That would let you compare compact-model fit quality and extracted parameter
trends across oxygen percentage and deposition power.

## Stage 1: Raw Cycle Extraction

Main script: `01_extract_clean_cycles.py`

Wrapper: `run_01.sh`

Research purpose:

This stage converts raw instrument output into a clean, standardized dataset.
Scientifically, this is the quality-control stage. It answers:

- Which files contain valid I-V data?
- Which cycles contain enough voltage/current points?
- Which cycles show meaningful current modulation?
- Which cycles include both SET and RESET behavior?
- Which devices have enough good cycles for downstream statistical analysis?

Without this stage, fitting would be vulnerable to failed devices, incomplete
sweeps, instrument artifacts, or files with too little dynamic range.

### What The Experiment Produces

The raw files are B1500-style CSV files. Each file may contain one or more
measurement blocks. A block usually corresponds to a sweep or part of a sweep.
Each useful row contains voltage and current.

The code recognizes:

- metadata rows, such as record time and test target
- analysis setup title rows, used to split the CSV into blocks
- data value rows, containing voltage/current pairs

### Key Code Objects

`IVBlock` represents one block of measured I-V data:

- `title`
- `voltage`
- `current`

`CycleRecord` represents one measured cycle/file:

- `path`
- `condition`
- `device_id`
- `test_name`
- `measurement_id`
- `record_time`
- `blocks`
- `cycle_number`

The research meaning is:

- `CycleRecord` is one experimental observation.
- `IVBlock` is a sub-sweep or labeled section inside that observation.

### Key Functions

`parse_b1500_csv(path, condition)` reads one raw CSV. It extracts metadata,
splits the file into blocks, and returns a `CycleRecord`.

`infer_branch(title, voltage)` labels a block as `SET`, `RESET`, `MIXED`, or
`UNKNOWN`. It first uses the title text, then falls back to voltage polarity.

`cycle_quality(cycle, args)` decides whether a cycle is good enough to keep.
It calculates:

- number of points
- voltage span
- peak current
- median current
- dynamic range in decades
- SET/RESET coverage

The rejection reasons have research meaning:

- `too_few_points`: not enough samples to trust the curve.
- `low_voltage_span`: sweep did not cover enough voltage to observe switching.
- `weak_signal`: current never rose above the minimum useful signal level.
- `too_high_current`: possible short, breakdown, or measurement artifact.
- `mostly_floor_current`: current is mostly at noise floor.
- `low_dynamic_range`: not enough HRS/LRS contrast or switching modulation.
- `missing_set_or_reset`: incomplete bipolar switching cycle.

`collect_cycles(folder, recursive)` reads many CSVs, groups them by
`condition` and `device_id`, sorts them by time, and assigns `cycle_number`.

`write_outputs(cycles, output_dir, args)` writes the normalized CSV outputs.

### Stage 1 Outputs

`01_extracted_points.csv`

This is the main cleaned point table. Each row is one measured point with:

- sample/device/cycle identity
- branch label
- block identity
- voltage
- current
- absolute current
- log10 absolute current
- quality flags

Research use:

- This is the master table for downstream curve selection, plotting, and
  possible future statistical modeling.

`01_cycle_summary.csv`

This is one row per measured cycle. It records quality statistics and rejection
reasons.

Research use:

- This supports a quality-control table for a thesis or supplementary material.
- It can justify how many cycles were kept or rejected.

`01_device_summary.csv`

This aggregates each device:

- total cycles
- good cycles
- mean quality score
- good fraction

Research use:

- This supports defensible device selection.
- It avoids choosing a device only because one curve looked good by eye.

## Stage 2: Representative Device And Curve Selection

Main script: `02_select_device_representative_curve.py`

Wrapper: `run_02.sh`

Research purpose:

This stage reduces a large measurement ensemble to a representative measured
curve. That is a sensitive scientific step because a single compact-model fit is
usually performed on one nominal I-V curve. If the curve is cherry-picked, the
model fit is not defensible.

This script tries to make curve selection systematic:

- choose a device with many good cycles
- extract the programming segments
- choose a real measured cycle close to typical behavior
- save the selected curve and selection metadata

### Device Selection

`pick_best_device(device_summary, min_good_cycles)` chooses the device with:

1. enough good cycles
2. maximum `good_cycles`
3. high `mean_quality_score`
4. high `good_fraction`

Research meaning:

- The selected device is not just visually appealing.
- It is the device with the strongest statistical evidence of stable usable
  switching.

Manual selection is still possible with `--condition` and `--device-id`, which
is useful when preparing a specific figure or checking a known device.

### Programming Segment Extraction

Raw set-reset files may include multiple voltage sweeps or direction changes.
The fitting target should focus on the actual programming branch.

The segment extraction chain is:

- `split_voltage_segments()`
- `choose_programming_segment()`
- `build_programming_segments()`

`split_voltage_segments()` cuts a sweep when voltage direction changes.

`choose_programming_segment()` scores candidate segments:

- SET should be mostly positive voltage and positive-going.
- RESET should be mostly negative voltage and negative-going.
- Both need enough points and enough voltage span.

Research meaning:

- This separates the physically relevant switching sweep from return sweeps,
  read points, or repeated sub-sweeps.
- It improves the fit target by avoiding irrelevant portions of the instrument
  program.

### Representative Curve Modes

The script supports three modes:

- `medoid-cycle`
- `medoid-branch`
- `median-grid`

The default is `medoid-cycle`.

`median-grid` computes a pointwise median curve after interpolating cycles to a
common voltage grid. This is statistically smooth, but it may not correspond to
any real physical cycle.

`medoid-cycle` chooses a real cycle whose log-current behavior is closest to the
typical ensemble. This is usually better for compact-model fitting because the
model is being asked to reproduce a physically observed trajectory, not a
synthetic median of different cycles.

### Medoid Logic

`score_branch_cycles_against_typical()` does the scientific ranking:

1. Build a voltage grid for each branch.
2. Interpolate each cycle to that grid using log10 absolute current.
3. Compute the typical log-current at each voltage.
4. Compute each cycle's absolute log error from the typical behavior.
5. Rank cycles by median absolute log error.

`representative_measured_curve()` then chooses:

- one real cycle for both SET and RESET in `medoid-cycle` mode, if possible
- one real cycle per branch in `medoid-branch` mode

Research meaning:

- A medoid is a measured representative, not an average.
- This supports the claim that the nominal fit is tied to actual device
  behavior.

### Fit Targets

`estimate_threshold()` extracts switching-voltage estimates using a current
threshold.

`current_at_vread()` extracts read current at a chosen `vread`, default `0.1 V`.

Research use:

- switching voltage distributions
- HRS/LRS read current comparison
- memory-window summaries
- advisor slides showing compact device metrics

### Stage 2 Outputs

Representative outputs include:

- `*_selected_points.csv`
- `*_programming_segments.csv`
- `*_representative_curve_FIXED.csv`
- `*_representative_scores_FIXED.csv`
- `*_fit_targets_FIXED.csv`
- `*_selection_info_FIXED.txt`
- `*_representative_curve_FIXED.png`

For publication, the most important outputs are:

- representative curve CSV for model fitting
- representative curve PNG for sanity checking
- representative scores to justify medoid selection
- fit targets for compact switching/read metrics

## Stage 3: Stanford Baseline Simulation

Main script: `03_run_stanford_baseline.py`

Wrapper: `run_03.sh`

Research purpose:

This stage asks: before doing a full parameter optimization, how well does a
chosen Stanford-PKU model parameter set reproduce the representative measured
curve?

This is important because it creates a baseline for the paper:

- If the baseline is poor, optimization is justified.
- If the baseline has systematic residuals, that reveals model limitations.
- If baseline mismatch is measured in log-current decades, the improvement from
  TaO-Fit can be quantified.

### HSPICE Deck Generation

The script supports two deck modes:

- `butterfly`: one bipolar PWL sweep from 0 to SET voltage to 0 to RESET voltage
  to 0
- `separate`: independent SET and RESET pulse-style simulations

The wrapper uses butterfly mode.

`make_butterfly_deck()` writes:

- HSPICE options
- `.hdl` include for Verilog-A
- one `X1` Stanford RRAM device
- one PWL voltage source
- transient analysis
- `.print tran V(in) I(Vin)`

Research meaning:

- The butterfly deck mimics a full bipolar I-V switching loop.
- It is the closest simple HSPICE analog of the measured representative curve.

### Model Parameters

The script exposes compact-model parameters as CLI arguments:

- `gap_min`
- `gap_max`
- `g0`
- `V0`
- `Vel0`
- `I0`
- `beta`
- `gamma0`
- `Rth`
- `tox`
- `deltaGap0`

Research meaning:

- These are the compact-model parameters whose physical interpretation must be
  discussed carefully in a thesis or paper.
- Some parameters are strongly coupled, so a good curve overlay does not
  automatically imply a unique physical parameter extraction.

### Simulation Parsing

`run_hspice()` executes HSPICE.

`parse_hspice_lis()` parses the `.lis` file.

`apply_hspice_current_convention()` flips the current sign because source
current convention is opposite the device-current convention used downstream.

Research meaning:

- Sign convention is not a cosmetic issue. If mishandled, SET/RESET current
  direction and plotted I-V polarity can be wrong.

### Compliance Handling

RRAM SET can be current-limited by the SMU. The Stanford model does not
natively include the measurement instrument's compliance clamp.

This script handles compliance by:

- estimating the measured SET compliance plateau with
  `estimate_set_compliance_current()`
- clamping simulated positive-voltage SET current with `apply_set_compliance()`

Research meaning:

- This prevents the fitting comparison from penalizing the model for exceeding
  an instrument-imposed current limit.
- It also makes clear that compliance is a measurement condition, not purely a
  device material property.

### Comparison Metrics

The baseline comparison creates:

- `03_experiment_fit_window.csv`
- `03_butterfly_sim.csv` or branch simulation CSVs
- `03_all_sim.csv`
- `03_exp_vs_baseline_comparison.csv`
- `03_fit_parameters.csv`
- `03_fit_metrics.csv`
- `03_read_ratio_summary.csv`
- `03_baseline_overlay.png`
- `03_baseline_overlay_linear.png`

The core residual is:

```text
log_error = measured_log10_abs_current - simulated_log10_abs_current
```

Metrics include:

- log10 MAE in decades
- log10 RMSE in decades
- median error
- mean error
- p90 absolute error

Research use:

- These are paper-ready quantitative fit-quality metrics.
- They are more defensible than visual overlay alone.

## TaO-Fit: Full Parameter Fitting Framework

Directory: `stanford_fit/`

Research purpose:

TaO-Fit is the project's advanced compact-model fitting framework. It is meant
to go beyond manual tuning or visual overlay by adding:

- physics-informed priors
- identifiability analysis
- HSPICE-in-the-loop Bayesian optimization
- local refinement
- validation diagnostics

This is the most publishable part of the codebase because it addresses a key
reviewer concern: RRAM compact-model parameters are often non-unique, correlated,
and sensitive to initialization.

## TaO-Fit Entry Points

There are two launch routes.

Python launcher:

- `stanford_fit/python/03_run_stanford_fit.py`

MATLAB direct entry:

- `stanford_fit/matlab/main_fit_stanford.m`

The Python launcher is only a convenience wrapper. It constructs a MATLAB
`-batch` command and calls:

```text
main_fit_stanford(input_csv, config, outdir)
```

The actual algorithm is in MATLAB.

## TaO-Fit Main Orchestrator

Main file:

- `stanford_fit/matlab/main_fit_stanford.m`

Research purpose:

This file turns the representative curve into a fitted compact-model parameter
set and supporting diagnostics.

Execution order:

1. Read YAML config.
2. Load representative CSV.
3. Normalize required input columns.
4. Split measured curve into SET and RESET branches.
5. Extract compact features such as `Vset`, `Vreset`, `G_LRS`, and `R_LRS`.
6. Derive priors.
7. Optionally run Fisher identifiability.
8. Run Bayesian optimization.
9. Run local refinement.
10. Run validation.
11. Save results and fit-quality plot.

The required input columns are:

- `branch`
- `voltage_V`
- `median_log10_abs_current`
- `median_abs_current_A`
- `median_current_A`

Optional columns include:

- `butterfly_sequence_index`
- `q25_current_A`
- `q75_current_A`
- `representative_cycle_id`

Research meaning:

- The representative curve is not just a plot. It becomes the formal
  measurement vector for parameter inference.

## Stage 1 In TaO-Fit: Physics-Informed Priors

Main file:

- `stanford_fit/matlab/stage1_extract_priors.m`

Research purpose:

This stage translates measured curve features into soft priors for the compact
model. This is a scientific bridge between experimental conduction behavior and
the Stanford model parameters.

Why this matters:

- Pure numerical optimization can fit an I-V curve with physically unrealistic
  parameter combinations.
- RRAM compact models often have parameter degeneracy.
- Physics-informed priors regularize the inverse problem.
- Priors give reviewers a reason to trust fitted values more than black-box
  curve-fitting.

### LRS Sinh Prior

`fit_lrs_sinh()` fits:

```text
I = A sinh(V / V0)
```

on the low-voltage SET return branch.

Scientific interpretation:

- LRS low-voltage behavior constrains conductance-like parameters.
- The fit estimates `V0`, which controls nonlinear current-voltage curvature.
- `A` is related to `I0` and `g0` through the Stanford current equation.

The code avoids the high-current compliance plateau because that region is
instrument-limited and should not be used to infer intrinsic conduction.

### PF-Inspired Priors

`fit_pf_priors()` fits:

```text
log(I / V) versus sqrt(V)
```

Scientific interpretation:

- This resembles a Poole-Frenkel-style field-assisted conduction analysis.
- The slope and intercept provide soft information about field enhancement and
  activation energy.
- The code maps this to `gamma0` and `Ea` priors.

These priors are not treated as exact truth. They are soft constraints with
uncertainty.

### Shared And Split Parameters

Shared parameters:

- `I0`
- `g0`
- `beta`
- `Rth`
- `gap_min`
- `tox`
- `Rs`

Split parameters:

- `V0_set`, `V0_res`
- `gamma0_set`, `gamma0_res`
- `Ea_set`, `Ea_res`
- `F_min_set`, `F_min_res`
- `Vel0_set`, `Vel0_res`
- `gap_max_set`, `gap_max_res`
- `gap_ini_set`, `gap_ini_res`

Research meaning:

- The Stanford model is not naturally rich enough to capture all polarity
  asymmetry in real TaOx devices.
- Splitting branch-sensitive parameters is a practical way to let SET and RESET
  behavior differ while preserving a common compact-model structure.

## Stage 2 In TaO-Fit: Fisher Identifiability

Main file:

- `stanford_fit/matlab/stage2_identifiability.m`

Research purpose:

This stage evaluates whether the measured I-V curve actually contains enough
information to identify each parameter.

Why this matters for publication:

- A model can fit the curve well but still have non-unique parameters.
- Reviewers may ask whether extracted parameters are identifiable.
- Fisher analysis gives a quantitative way to flag weakly constrained
  directions.

Current practical behavior:

- `run_fisher` is `0` in `default_config.yaml`.
- When disabled, the code returns an informational placeholder.
- When enabled, it finite-differences HSPICE simulations around the prior mean.

The enabled workflow computes:

- sensitivity matrix `S`
- weighted sensitivity `Sw`
- Fisher matrix `F = Sw' * Sw`
- eigenvalues and eigenvectors
- effective parameter uncertainty
- relative parameter uncertainty

Research interpretation:

- Large relative uncertainty means a parameter should not be overclaimed.
- Such parameters should be reported as prior-dominated or not identifiable
  from this experiment alone.

## Stage 3 In TaO-Fit: Bayesian Optimization

Main file:

- `stanford_fit/matlab/stage3_bayesopt_driver.m`

Research purpose:

This stage searches parameter space using HSPICE simulations as the objective
function. It is the main fitting engine.

Why Bayesian optimization:

- HSPICE simulations are expensive.
- The loss surface can be nonlinear and nonconvex.
- Gradients are not readily available.
- Bayesian optimization can be more sample-efficient than brute force sweeps.

The active parameter list comes from:

- `active_params` in config, if provided
- otherwise a default split set containing current-scale, parasitic, switching,
  field, gap, and initial-gap parameters

Important config parameters:

- `bo_n_init`
- `bo_n_iter`
- `rng_seed`
- `hspice_bin`
- `hspice_timeout_s`

Research meaning:

- `bo_n_init` controls how broadly the initial parameter space is sampled.
- `bo_n_iter` controls how much optimization effort is spent after initialization.
- Random seed supports reproducibility.

## TaO-Fit Loss Function

Main file:

- `stanford_fit/matlab/eval_loss.m`

Research purpose:

This function defines what it means for a simulated compact-model curve to fit
the measured representative curve.

The loss combines:

1. SET log-current residuals.
2. RESET log-current residuals.
3. switching-voltage penalty.
4. prior penalty.

The final objective is:

```text
L = Lset + Lreset + 0.5 * Lv + 0.1 * Lprior
```

Scientific interpretation:

- Log-current residuals matter because RRAM currents span many orders of
  magnitude.
- Linear-current error would overweight high-current LRS regions and underweight
  HRS.
- SET and RESET are both included so the fit is bipolar.
- Switching-voltage penalty helps align threshold behavior, not just current
  magnitude.
- Prior penalty prevents unphysical parameter drift.

The current uncertainty estimate uses:

```text
sigma_logI ~= (q75_current_A - q25_current_A) / 1.35 / abs(median_current_A) / log(10)
```

Research meaning:

- If quartile information is present, the loss can weight points by variability.
- This is closer to a statistically meaningful objective than unweighted MSE.

## TaO-Fit Forward Simulation

Main files:

- `stanford_fit/matlab/simulate_branches.m`
- `stanford_fit/matlab/write_netlist.m`
- `stanford_fit/matlab/run_hspice.m`
- `stanford_fit/matlab/parse_lis.m`
- `stanford_fit/matlab/apply_compliance.m`

Research purpose:

This block maps candidate compact-model parameters to simulated currents at the
same voltage samples as the measured data.

### Branch-Split Simulation

`simulate_branches()` creates two simulations:

- SET branch
- RESET branch

Each branch receives branch-specific parameters where available.

Research meaning:

- This allows the fitting procedure to represent asymmetric SET and RESET
  behavior while still using the Stanford RRAM model.

### Netlist Writing

`write_netlist()` emits a temporary HSPICE deck with:

- PWL voltage source
- series resistor `Rs`
- Stanford Verilog-A RRAM instance
- transient analysis
- printed voltage and current

Research meaning:

- The measured voltage samples are turned into a simulation waveform.
- The series resistor approximates parasitic/probe resistance and softens the
  LRS branch.

### HSPICE Execution

`run_hspice()` creates a temporary directory, writes the deck, runs HSPICE, and
keeps failed files if configured.

Research meaning:

- Every loss evaluation is an actual compact-model simulation.
- This is not fitting to an analytic surrogate unless such a surrogate is added
  later.

### Parsing And Alignment

`parse_lis()` reads HSPICE output, flips current sign, and interpolates simulated
current to the same timestamps used for the measured voltage sequence.

Research meaning:

- Alignment by time avoids problems when voltage is not single-valued during a
  butterfly sweep.
- It makes simulated and measured points comparable one-to-one.

### Compliance

`apply_compliance()` clamps simulated current to `I_compliance`.

Research meaning:

- This encodes the measurement setup.
- It prevents instrument-limited regions from corrupting intrinsic parameter
  extraction.

## Stage 4 In TaO-Fit: Local Refinement

Main file:

- `stanford_fit/matlab/stage4_local_refine.m`

Research purpose:

Bayesian optimization finds a good global region. Local refinement polishes the
fit around that region.

The code uses:

- `fminsearch`
- log-space parameter encoding
- bounds checking
- same `eval_loss()` objective

Research meaning:

- This is a hybrid global/local fitting strategy.
- It can improve the final overlay and metrics without relying only on the
  Bayesian optimizer's discrete sampled candidates.

## Stage 5 In TaO-Fit: Validation

Main file:

- `stanford_fit/matlab/stage5_validate.m`

Research purpose:

This stage checks whether the fitted model is credible beyond simply producing
a nice overlay.

Always-on diagnostics:

- SET residual vector
- RESET residual vector
- SET RMSE
- RESET RMSE
- SET Durbin-Watson statistic
- RESET Durbin-Watson statistic

Research interpretation:

- RMSE in log-current decades quantifies fit error.
- Durbin-Watson detects structured residuals. Structured residuals can indicate
  missing physics, polarity asymmetry, compliance problems, or series resistance
  effects.

Optional diagnostics:

- leave-one-cycle-out validation
- bootstrap confidence intervals

These require richer per-cycle information and config flags.

For publication, this stage supports the claim that the model fit is not just
visually good but quantitatively evaluated.

## Stanford Verilog-A Model

Relevant files:

- `rram_v_1_0_0_hspice.va`
- `stanford_fit/templates/rram_v_1_0_0_hspice.va`
- `RRAM_StanfordModel/rram_v_1_0_0.va`

Research purpose:

These files implement the Stanford-PKU RRAM compact model. The model describes
resistive switching through a state variable `gap`, where current depends
exponentially on gap and nonlinearly on voltage.

Core current relation:

```text
I = I0 * exp(-gap / g0) * sinh(V / V0)
```

Core thermal relation:

```text
T_cur = T_ini + abs(V * I * Rth)
```

Core gap-rate relation:

```text
gap_ddt = -Vel0 * exp(-q * Ea / (kb * T_cur))
          * sinh(gamma * a0 / tox * q * V / (kb * T_cur))
```

Research meaning:

- `gap` represents the effective tunneling/filament gap.
- `I0`, `g0`, and `V0` control current scale and nonlinearity.
- `Vel0`, `Ea`, `gamma0`, and `F_min` control switching dynamics.
- `Rth` couples electrical power to local temperature.
- `gap_min` and `gap_max` bound LRS/HRS states.

Important caution:

- A good fit does not automatically prove every parameter is physically unique.
- Some parameter combinations can compensate for each other.
- This is why TaO-Fit includes priors and identifiability analysis.

## Historical Scripts And Their Research Role

The scripts under `DC endurance-DOE/` support exploratory analysis and figure
generation.

### `Vset Extraction.py`

Purpose:

- Extracts voltage values associated with maximum current jump or subtraction.

Research use:

- forming-voltage distribution
- SET-voltage distribution
- process-condition comparisons

Limitations:

- hardcoded folder names
- per-sample copies
- less general than the modern pipeline

### `histograp plot*.py`

Purpose:

- Plots histograms from extracted voltage CSVs.

Research use:

- advisor slides showing forming, SET, or RESET voltage distributions
- process-condition comparison figures

### `folder plot.py`, `I-V.py`, `log-I-V.py`, `reset plot.py`

Purpose:

- Generate I-V or log I-V plots from folders of measurement CSVs.

Research use:

- inspect device behavior
- create publication-style figures
- compare forming, set-reset, and reset behavior

### `Step 1/2/3 CDF` Scripts

Purpose:

- Extract HRS/LRS read currents and plot cumulative distributions.

Research use:

- memory-window analysis
- variability distribution
- reliability and yield discussion

### `memorywindow.py`

Purpose:

- Extracts or compares HRS/LRS current values from fixed rows.

Research use:

- memory-window summaries
- early exploratory analysis

### `ltp amp.py`

Purpose:

- Plots long-term potentiation or pulse-related current response.

Research use:

- neuromorphic or analog switching behavior, if included in the broader PhD
  project.

## Result Folders

Generated folders are ignored by `.gitignore`:

- `step01_*`
- `step02_*`
- `step03_*`
- `step03_*_baseline`

Research meaning:

- These are reproducible outputs, not source.
- They should be regenerated from raw data and scripts.
- For a paper submission, freeze a specific output folder or archive it with
  date, commit, and config.

The tracked `results/` folder currently contains prior TaO-Fit artifacts:

- `priors.mat`
- `fisher_matrix.csv`
- `fisher_report.mat`

These are partial outputs from earlier runs. For final publication, rerun the
pipeline cleanly and save a complete result set.

## What To Present To Your Advisor

For an advisor meeting, the clearest story is:

1. Experimental dataset:
   - S1-S12 deposition conditions from `Depos_Condition.csv`
   - number of measured files/cycles per sample
   - examples of raw I-V curves
2. Quality control:
   - number of accepted/rejected cycles
   - rejection reasons
   - device summary table
3. Representative curve selection:
   - selected device
   - medoid score explanation
   - plot of all cycles plus representative curve
4. Baseline compact-model simulation:
   - Stanford baseline overlay
   - log10 MAE and RMSE
   - read-current ratio summary
5. TaO-Fit:
   - physics-informed priors
   - parameter bounds
   - active fitted parameters
   - final fit overlay
   - residual plot
   - identifiability discussion
6. Publication claim:
   - not just "we fit a curve"
   - instead "we built a reproducible, physics-constrained, identifiability-aware
     fitting workflow for TaOx RRAM compact-model calibration"

## What To Include In A Paper

Methods section:

- measurement setup and deposition conditions
- raw data parsing and quality filters
- medoid representative-cycle selection
- Stanford-PKU model equations
- prior derivation from measured conduction features
- HSPICE-in-the-loop optimization
- loss function in log-current space
- validation metrics

Results section:

- distributions of forming/SET/RESET voltages
- HRS/LRS read current CDFs
- representative I-V curves
- baseline vs fitted overlays
- parameter table with priors, fitted values, and bounds
- fit metrics
- residual diagnostics
- identifiability caveats

Supplementary material:

- cycle summary tables
- device selection table
- configuration YAML
- HSPICE deck template
- code version/commit
- full result folder

## Reproducibility Checklist

Before presenting final results:

1. Record the exact code version.
2. Record the sample and device ID used.
3. Save `RUN_INSTRUCTIONS.md` commands used.
4. Save the config YAML.
5. Save the representative curve CSV.
6. Save generated HSPICE decks.
7. Save fit metrics and overlays.
8. Save residual diagnostics.
9. Note whether `run_fisher`, `run_loco`, or `run_bootstrap` were enabled.
10. Archive the final `results/` output folder.

## Important Caveats

This codebase is powerful, but several caveats matter for publication:

- The default wrappers are currently S1-specific.
- Legacy scripts are not general-purpose and often contain hardcoded filenames.
- The representative medoid curve is a nominal curve, not the full ensemble.
- LOCO/bootstrap validation needs full per-cycle information and config support.
- Some Stanford model parameters are not uniquely identifiable from a single DC
  I-V curve.
- Compliance current is handled as a post-simulation clamp in the fitting path.
- The Verilog-A model contains branch-specific behavior that can complicate
  interpretation of `gamma0`.
- HSPICE availability and output format are external dependencies.

These caveats do not weaken the work if they are stated clearly. In fact,
explicitly discussing identifiability and model limitations can strengthen the
paper.

## Glossary

RRAM:

- Resistive random-access memory, a nonvolatile device that switches between
  high and low resistance states.

SET:

- Switching event that usually moves the device from HRS to LRS.

RESET:

- Switching event that usually moves the device from LRS to HRS.

HRS:

- High-resistance state.

LRS:

- Low-resistance state.

Medoid:

- A real measured cycle that is closest to the typical behavior of the ensemble.

Representative curve:

- The selected measured curve used as the nominal compact-model fitting target.

Compact model:

- A circuit-simulation model, here Stanford-PKU RRAM Verilog-A, used in HSPICE.

HSPICE:

- Circuit simulator used to evaluate the Verilog-A RRAM model.

Prior:

- A soft parameter estimate or constraint before optimization.

Identifiability:

- Whether the available data can uniquely constrain a parameter.

Bayesian optimization:

- A sample-efficient black-box optimization method used here because each loss
  evaluation requires an HSPICE run.

Residual:

- Difference between measured and simulated current, usually in log10 current
  decades in this codebase.

