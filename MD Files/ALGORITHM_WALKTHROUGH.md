# Core Algorithm Walkthrough

> **2026-06 update:** the pipeline now includes `02c_classify_conduction_regimes.py`
> (automatic ohmic/PF/Schottky/FN regime classification per state segment),
> regime-conditioned Stage-1 priors (`regime_map_csv`), mechanism-aware loss
> weighting in `eval_loss.m`, a Stage-4b profile-likelihood identifiability check
> (`stage4b_profile_likelihood.m`, `run_profile`), a per-run
> `identifiability_report.csv`, and runners `07_run_final.py` /
> `run_full_pipeline.sh`. Also: `run_fisher` now defaults to 1 (evaluated at the
> fitted optimum), and scripts 02b/04/05/06 exist beyond what is described below.
> See `MD Files/SUGGESTED_ALGORITHMIC_CHANGES.md` and `RUN_INSTRUCTIONS.md`.

This document explains the core logic of the repository for a new PhD student
or new developer joining the project. It focuses on the modern fitting pipeline:

1. `01_extract_clean_cycles.py`
2. `02_select_device_representative_curve.py`
3. `03_run_stanford_baseline.py`
4. `stanford_fit/`, the MATLAB/HSPICE TaO-Fit optimizer

The older scripts under `DC endurance-DOE/` are useful historical analysis
artifacts, but they are mostly one-off plotting and extraction scripts with
hardcoded local filenames. Treat them as lab archive material unless a specific
figure or legacy extraction needs to be reproduced.

## Mental Model

The project turns raw Keysight B1500-style measurement CSVs into a compact
representative I-V curve and then compares or fits that curve against the
Stanford-PKU RRAM compact model.

The data flow is:

```text
raw_data/S1/*.csv
  -> 01_extract_clean_cycles.py
  -> step01_S1/01_extracted_points.csv
  -> step01_S1/01_cycle_summary.csv
  -> step01_S1/01_device_summary.csv
  -> 02_select_device_representative_curve.py
  -> step02_S1/*_representative_curve_FIXED.csv
  -> 03_run_stanford_baseline.py
  -> step03_S1_baseline/* simulation, comparison, metric, and overlay files
  -> stanford_fit/matlab/main_fit_stanford.m for full TaO-Fit optimization
```

There are two related but distinct simulation paths:

- The top-level baseline path in `03_run_stanford_baseline.py` creates a
  baseline HSPICE deck and reports how well a chosen parameter set matches the
  representative curve.
- The `stanford_fit/matlab/` path repeatedly creates HSPICE decks inside an
  optimization loop, using priors, Bayesian optimization, local refinement, and
  residual validation.

## Stage 1: Raw CSV Extraction

Main file: `01_extract_clean_cycles.py`

Entry point:

- `main()` at `01_extract_clean_cycles.py:443`
- CLI parser in `build_parser()` at `01_extract_clean_cycles.py:424`

The script expects a folder of raw CSV files and writes a normalized point table,
a per-cycle summary, and a per-device summary.

### Data Structures

`IVBlock` at `01_extract_clean_cycles.py:24` is one contiguous measurement block:

- `title`: the B1500 block title, such as a SET or RESET label.
- `voltage`: NumPy array of voltage samples.
- `current`: NumPy array of current samples.

`CycleRecord` at `01_extract_clean_cycles.py:31` is the unit of analysis:

- `path`: source CSV path.
- `condition`: currently inferred from `path.parent.name`.
- `device_id`: device identifier, usually from B1500 metadata.
- `test_name`, `measurement_id`, `record_time`: parsed from filename or metadata.
- `blocks`: list of `IVBlock`.
- `cycle_number`: assigned after grouping by `(condition, device_id)`.

This division matters. One CSV can contain multiple B1500 analysis blocks; the
pipeline preserves that block structure before flattening points.

### Parsing Raw B1500 CSVs

The file-level parser is `parse_b1500_csv(path, condition)` at
`01_extract_clean_cycles.py:117`.

It uses four regular expressions declared near the top of the file:

- `TITLE_RE` at `01_extract_clean_cycles.py:18` finds block titles.
- `DATA_RE` at `01_extract_clean_cycles.py:19` finds `DataValue, voltage, current`
  rows.
- `RECORD_TIME_RE` at `01_extract_clean_cycles.py:20` finds measurement time.
- `TARGET_RE` at `01_extract_clean_cycles.py:21` finds the device target.

Parsing happens in this order:

1. `read_csv_text()` reads the file with `utf-8-sig` and replacement for bad
   characters.
2. `parse_filename_metadata()` at `01_extract_clean_cycles.py:59` extracts
   `device_id`, `test_name`, `measurement_id`, and a timestamp from filenames
   like `[B6-01-4um-12,SET-RESET,12,8_30_2024 5_00_00 PM].csv`.
3. `extract_target()` and `extract_record_time()` search metadata lines for a
   more authoritative device and time.
4. `parse_b1500_csv()` scans for all title rows. Each title starts a new
   `IVBlock`; `extract_data_pairs()` at `01_extract_clean_cycles.py:96` pulls
   finite numeric voltage/current pairs inside that block.
5. If no title rows exist, the whole file becomes one `IVBlock` named `All`.

The parser is deliberately tolerant: bad numeric rows are skipped, missing times
fall back to filename time, and finally to file modification time.

### Branch Inference

`infer_branch(title, voltage)` at `01_extract_clean_cycles.py:156` assigns each
block to one of:

- `SET`
- `RESET`
- `MIXED`
- `UNKNOWN`

The branch rule is simple:

1. If the lowercase block title contains `reset`, return `RESET`.
2. If it contains `set`, return `SET`.
3. Otherwise compare the voltage extrema:
   - if `vmax > abs(vmin)`, infer `SET`
   - if `abs(vmin) > vmax`, infer `RESET`
   - otherwise `MIXED`

This is an important assumption: a block's polarity is inferred from label text
first, then from voltage polarity.

### Cycle Quality

`cycle_quality(cycle, args)` at `01_extract_clean_cycles.py:198` decides whether
a cycle is usable.

It concatenates all block voltages/currents, removes non-finite points, then
computes:

- `v_min`, `v_max`, `v_span`
- `i_abs_min`, `i_abs_median`, `i_abs_max`
- `dynamic_decades`, from `calc_dynamic_decades()` at
  `01_extract_clean_cycles.py:182`
- whether the cycle appears to contain both SET and RESET content

The rejection checks are controlled by parser arguments in `build_parser()`:

- `--current-floor`, default `1e-13`
- `--min-points`, default `40`
- `--min-vspan`, default `1.0`
- `--min-abs-vmax`, default `0.5`
- `--min-peak-current`, default `1e-9`
- `--max-peak-current`, default `1.0`
- `--min-dynamic-decades`, default `0.5`
- `--no-require-set-reset`, which disables the default SET/RESET requirement

The quality score is not a machine-learning model. It is a heuristic score based
on point count, voltage span, dynamic range, and SET/RESET presence
(`01_extract_clean_cycles.py:258` to `01_extract_clean_cycles.py:263`).

### Cycle Collection and Numbering

`collect_cycles(folder, recursive)` at `01_extract_clean_cycles.py:283` gathers
CSV files, parses each into a `CycleRecord`, and assigns `cycle_number`.

The cycle number is local to each `(condition, device_id)` group:

```text
condition + device_id
  -> sort cycles by record_time and filename
  -> assign cycle_number = 1, 2, 3, ...
```

That `cycle_number` later becomes `cycle_id` in the output CSVs.

### Outputs From Stage 1

`write_outputs(cycles, output_dir, args)` at `01_extract_clean_cycles.py:313`
writes three files:

- `01_cycle_summary.csv`
- `01_extracted_points.csv`
- `01_device_summary.csv`

`01_cycle_summary.csv` is one row per source cycle. It includes:

- `condition`
- `device_id`
- `cycle_id`
- `file`
- `record_time`
- `is_good`
- `quality_score`
- `reject_reason`
- current/voltage summary statistics

`01_extracted_points.csv` is the normalized point cloud. Its key columns are:

- `condition`
- `device_id`
- `cycle_id`
- `block_id`
- `block_title`
- `branch`
- `point_index`
- `voltage_V`
- `current_A`
- `abs_current_A`
- `log10_abs_current`
- `is_good_cycle`
- `quality_score`
- `source_file`

`01_device_summary.csv` aggregates the cycle summaries per device:

- `total_cycles`
- `good_cycles`
- `mean_quality_score`
- `good_fraction`

This file is what Stage 2 uses to choose the best device unless a device is
manually specified.

## Stage 2: Device Selection and Representative Curve

Main file: `02_select_device_representative_curve.py`

Entry point:

- `main()` at `02_select_device_representative_curve.py:554`

Inputs:

- `--step01-dir`
- `01_extracted_points.csv`
- `01_device_summary.csv`

Outputs:

- selected point CSV
- programming segment CSV
- representative curve CSV
- optional representative score CSV
- fit target CSV
- selection info text file
- representative curve PNG

### Choosing the Device

`pick_best_device(device_summary, min_good_cycles)` at
`02_select_device_representative_curve.py:20` picks the device with the strongest
usable cycle statistics.

The algorithm:

1. Keep devices with `good_cycles >= min_good_cycles`.
2. If no device passes, use all devices.
3. Sort by:
   - `good_cycles` descending
   - `mean_quality_score` descending
   - `good_fraction` descending
4. Pick the first row.

The default `--min-good-cycles` is `5`.

Manual override is available with:

- `--condition`
- `--device-id`

### Selecting Good Points

In `main()`, points are filtered at `02_select_device_representative_curve.py:611`.
Only points satisfying all of the following survive:

- matching selected `condition`
- matching selected `device_id`
- `is_good_cycle == true`
- `branch` is `SET` or `RESET`

This means rejected cycles never contribute to the representative curve.

### Finding Programming Segments

The measurement block may include a complete up/down sweep. For fitting, the
script wants the actual programming part of each cycle and branch.

The segment pipeline is:

1. `build_programming_segments()` at `02_select_device_representative_curve.py:104`
2. `choose_programming_segment()` at `02_select_device_representative_curve.py:64`
3. `split_voltage_segments()` at `02_select_device_representative_curve.py:33`

`split_voltage_segments()` sorts points by `point_index`, computes `dv`, converts
that to a sign direction, and cuts the block whenever voltage direction changes.
The result is a list of monotonic voltage segments.

`choose_programming_segment()` scores candidate monotonic segments differently
for SET and RESET:

- SET favors mostly positive voltage, positive-going direction, and useful
  positive span.
- RESET favors mostly negative voltage, negative-going direction, and useful
  negative span.

The knobs are:

- `--min-segment-points`, default `20`
- `--min-segment-vspan`, default `0.3`

The returned `program_segments` table is still measured data; it is just the
subset judged to be the programming sweep.

### Representative Modes

The script supports three modes through `--representative-mode`:

- `medoid-cycle`, default
- `medoid-branch`
- `median-grid`

The default `medoid-cycle` is the most physically conservative because it tries
to pick a real measured cycle, not a synthetic pointwise median curve.

### Median-Grid Representative

The older `median-grid` path uses:

- `make_voltage_grid()` at `02_select_device_representative_curve.py:131`
- `representative_branch_curve()` at `02_select_device_representative_curve.py:142`

`make_voltage_grid()` creates a branch-specific voltage grid:

- SET: from nonnegative 1st percentile to 99th percentile.
- RESET: from 1st percentile to nonpositive 99th percentile.

`representative_branch_curve()` interpolates every cycle onto this grid in
`log10_abs_current`, then takes per-voltage medians and quartiles. It requires
at least `--min-overlap-cycles` cycles at a voltage point.

This creates a smooth statistical representative curve, but that curve may not
correspond to any real measured cycle.

### Medoid Representative

The default medoid path is centered on `representative_measured_curve()` at
`02_select_device_representative_curve.py:352`.

The key helper is `score_branch_cycles_against_typical()` at
`02_select_device_representative_curve.py:265`.

For each branch:

1. Build a voltage grid.
2. Interpolate every cycle to that grid with `interpolate_cycles_to_grid()`.
3. At each grid voltage, compute the typical median log current.
4. For each cycle, compute `abs_log_error` from the typical curve.
5. Summarize by:
   - `representative_score`, the median absolute log error
   - `mean_abs_log_error`
   - `p90_abs_log_error`
   - `overlap_points`
6. Reject cycles with fewer than `--min-medoid-grid-points`, default `20`.

`representative_measured_curve()` then ranks each cycle within each branch. In
`medoid-cycle` mode, it prefers a single cycle that is jointly representative
for both SET and RESET. It does this by building a pivot table of branch rank
fractions and minimizing the mean rank fraction across required branches
(`02_select_device_representative_curve.py:376` to
`02_select_device_representative_curve.py:394`).

In `medoid-branch` mode, it picks the best real cycle separately for each
branch.

`measured_curve_from_cycle()` at `02_select_device_representative_curve.py:306`
then reconstructs the output representative curve from the original measured
points of the selected cycle and block.

Important output columns include:

- `branch`
- `voltage_V`
- `median_current_A`
- `q25_current_A`
- `q75_current_A`
- `median_log10_abs_current`
- `median_abs_current_A`
- `n_cycles`
- `representative_mode`
- `representative_cycle_id`
- `representative_score`
- `representative_point_index`
- `representative_source_file`

Even though columns say `median_*`, in medoid mode they are values from one real
cycle copied into the common downstream schema.

### Butterfly Sequence Index

If the representative output has `representative_point_index`, `main()` sorts SET
before RESET and adds `butterfly_sequence_index` at
`02_select_device_representative_curve.py:684`.

That index matters later. The baseline and TaO-Fit code can use it to preserve
the measured sequence rather than sorting solely by voltage.

### Fit Targets

Two diagnostic target families are computed:

- `estimate_threshold()` at `02_select_device_representative_curve.py:423`
- `current_at_vread()` at `02_select_device_representative_curve.py:461`

`estimate_threshold()` scans each branch and cycle for the first point where
`abs_current_A >= --switch-current-threshold`, default `1e-6`.

`current_at_vread()` interpolates log current at `--vread`, default `0.1 V`.

These targets are not the full fitting loss. They are compact diagnostics that
help interpret switching voltage and read-current behavior.

## Stage 3: Stanford Baseline Simulation

Main file: `03_run_stanford_baseline.py`

Entry point:

- `main()` at `03_run_stanford_baseline.py:776`

This script is a baseline comparison tool. It generates one HSPICE deck in
`butterfly` mode, or two independent decks in `separate` mode, parses the
simulation results, interpolates simulation to experiment, and reports log-error
metrics.

### Numeric Parsing Helpers

HSPICE output uses engineering suffixes such as `u`, `m`, `n`, and sometimes
Fortran-style `D` exponents. `hspice_num()` at `03_run_stanford_baseline.py:45`
normalizes these values using `HSPICE_SUFFIX_SCALE` at
`03_run_stanford_baseline.py:28`.

This is why parsing does not simply call `float()` on the raw text.

### Model Parameters

The CLI parameter defaults are declared in `main()`:

- `--gap-min`, default `5e-10`
- `--gap-max`, default `15e-10`
- `--g0`, default `0.35e-9`
- `--V0`, default `0.35`
- `--Vel0`, default `10.0`
- `--I0`, default `1e-3`
- `--beta`, default `0.8`
- `--gamma0`, default `16.0`
- `--Rth`, default `2.1e3`
- `--tox`, default `7.5e-9`
- `--deltaGap0`, default `1e-4`

Timing parameters include:

- `--tstep`, default `1u`
- `--butterfly-set-time`, default `1m`
- `--butterfly-zero-after-set-time`, default `2m`
- `--butterfly-reset-time`, default `3m`
- `--butterfly-final-time`, default `4m`
- `--butterfly-tstop`, default `4m`

`model_parameter_rows()` at `03_run_stanford_baseline.py:53` records the
parameter values used into `03_fit_parameters.csv`.

### Deck Generation

`make_butterfly_deck()` at `03_run_stanford_baseline.py:119` writes a single
bipolar transient deck:

```text
0 -> +set_vmax -> 0 -> reset_vmin -> 0
```

It instantiates:

```text
X1 in 0 rram_v_1_0_0
```

with parameters including `gap_ini`, `model_switch`, `deltaGap0`, `g0`, `V0`,
`Vel0`, `I0`, `beta`, `gamma0`, `gap_min`, `gap_max`, `Rth`, and `tox`.

`make_deck()` at `03_run_stanford_baseline.py:83` is the older separate-branch
path. It emits one SET pulse deck and one RESET pulse deck.

### HSPICE Execution and Parsing

`run_hspice(deck_path, hspice_cmd)` at `03_run_stanford_baseline.py:147` runs:

```text
hspice <deck name>
```

inside the output directory and saves stdout/stderr to a `.runlog`.

The preferred parser is `parse_hspice_lis()` at
`03_run_stanford_baseline.py:163`. If the `.lis` file is absent, the code falls
back to `fallback_parse_stdout()` at `03_run_stanford_baseline.py:202`.

Both parsers expect three numeric columns:

- time
- voltage
- current

`apply_hspice_current_convention()` at `03_run_stanford_baseline.py:238` flips
the current sign because HSPICE source current convention is opposite the device
current convention used by the project.

`require_hspice_success()` and `require_sim_points()` fail loudly if HSPICE did
not run or the parsed result is empty.

### Experiment Window

The representative CSV is read at `03_run_stanford_baseline.py:847`.

If `--deck-mode butterfly` and auto limits are enabled, `apply_rep_voltage_limits()`
at `03_run_stanford_baseline.py:340` sets:

- `args.set_vmax` to the maximum positive representative voltage.
- `args.reset_vmin` to the minimum negative representative voltage.

`filter_rep()` at `03_run_stanford_baseline.py:316` then restricts the
experimental points to the selected SET/RESET voltage windows.

The resulting fitting window is saved as `03_experiment_fit_window.csv`.

### Compliance Current

The measured SET branch can be limited by SMU compliance. The baseline path
handles this after simulation:

- `estimate_set_compliance_current()` at `03_run_stanford_baseline.py:357`
  estimates compliance from the high-voltage tail of measured SET.
- `resolve_set_compliance_current()` at `03_run_stanford_baseline.py:405`
  chooses explicit `--set-compliance-current`, automatic estimate, or no clamp.
- `apply_set_compliance()` at `03_run_stanford_baseline.py:382` clamps simulated
  positive-voltage current magnitude and records `unclamped_current_A`.

This is not a physical Verilog-A compliance model. It is a post-processing
alignment step so the baseline simulation can be compared to compliance-limited
measurements.

### Comparing Simulation to Experiment

There are two comparison modes:

- `interpolate_sim_to_exp()` at `03_run_stanford_baseline.py:413` for separate
  SET/RESET branch comparison.
- `interpolate_butterfly_sim_to_exp()` at `03_run_stanford_baseline.py:448` for
  sequence comparison.

In butterfly mode, the code sorts simulation by `time_s` and experiment by
`butterfly_sequence_index`, then maps both to a normalized progress coordinate
from `0` to `1`. This avoids forcing the bipolar transient to be a single-valued
function of voltage.

The comparison table includes:

- `sim_log10_abs_current`
- `sim_abs_current_A`
- `log_error`

where:

```text
log_error = measured median_log10_abs_current - simulated log10_abs_current
```

`fit_metric_rows()` at `03_run_stanford_baseline.py:578` reports:

- valid comparison point count
- log10 MAE in decades
- log10 RMSE in decades
- median error
- mean error
- p90 absolute error

### Read-Current Ratio Diagnostics

`split_butterfly_sweeps()` at `03_run_stanford_baseline.py:473` divides a
butterfly curve into four states:

- `SET_HRS_PRE`
- `SET_LRS_POST`
- `RESET_LRS_PRE`
- `RESET_HRS_POST`

`butterfly_read_currents()` at `03_run_stanford_baseline.py:529` interpolates
currents at `+|Vread|` or `-|Vread|` and computes:

- `SET_LRS_to_HRS`
- `RESET_LRS_to_HRS`

`print_ratio_tuning_hint()` at `03_run_stanford_baseline.py:640` prints a model
tuning hint if the simulated ratio is much larger than experiment.

## Stage 4: Full TaO-Fit Optimizer

Main folder: `stanford_fit/`

There are two ways to launch it:

- `stanford_fit/python/03_run_stanford_fit.py`
- direct MATLAB call to `stanford_fit/matlab/main_fit_stanford.m`

The Python wrapper is only an orchestrator. Its `main()` builds a MATLAB
`-batch` command and calls `main_fit_stanford(...)`.

The actual algorithm is in MATLAB.

### Main MATLAB Orchestrator

File: `stanford_fit/matlab/main_fit_stanford.m`

Entry point:

- `main_fit_stanford(csv_path, config_path, outdir)` at
  `stanford_fit/matlab/main_fit_stanford.m:1`

Execution order:

1. Read config with `taofit_read_yaml()` at
   `stanford_fit/matlab/main_fit_stanford.m:40`.
2. Load representative CSV with `readtable()`.
3. Normalize required columns with `normalize_input_table()` at
   `stanford_fit/matlab/main_fit_stanford.m:70`.
4. Split data into SET and RESET branches and compute features with
   `split_and_featurize()` at `stanford_fit/matlab/main_fit_stanford.m:92`.
5. Run Stage 1 priors with `stage1_extract_priors()`.
6. Run Stage 2 Fisher report with `stage2_identifiability()`.
7. Run Stage 3 Bayesian optimization with `stage3_bayesopt_driver()`.
8. Run Stage 4 local refinement with `stage4_local_refine()`.
9. Run Stage 5 validation with `stage5_validate()`.
10. Plot fit quality with `plot_fit_quality()`.

The required input columns are checked in `normalize_input_table()`:

- `branch`
- `voltage_V`
- `median_log10_abs_current`
- `median_abs_current_A`
- `median_current_A`

Optional columns are filled if missing:

- `butterfly_sequence_index`
- `q25_current_A`
- `q75_current_A`
- `representative_cycle_id`

### Feature Extraction

`split_and_featurize()` computes:

- `setB`: rows whose `branch` is SET
- `resetB`: rows whose `branch` is RESET
- `feats.Vset`: voltage at maximum derivative of SET log current
- `feats.Vreset`: voltage at minimum derivative of RESET log current
- `feats.G_LRS`: low-voltage LRS conductance estimate
- `feats.R_LRS`: reciprocal of `G_LRS`
- `feats.hysteresis_area`: trapezoid area in voltage/log-current space
- `feats.I_HRS_read`: mean current near 0.1 V

The derivative helper `safe_gradient()` at
`stanford_fit/matlab/main_fit_stanford.m:145` de-duplicates x-values before
calling MATLAB `gradient()`.

### Config Parameters

Primary config file: `stanford_fit/config/default_config.yaml`

Important fields:

- `T_K`, `tox`, `a0`, `eps_r_TaOx`
- `gap_min`, `gap_max`, `gap_ini_HRS`
- `g0_prior_m`, `g0_prior_sigma_m`
- `Vel0_prior`, `Vel0_sigma`
- `beta_prior`, `beta_sigma`
- `Rth_prior`, `Rth_sigma`
- `F_min_prior`
- `I_compliance`
- `series_R_ohm`
- `sweep_rate_Vps`
- `tran_step_s`
- `hspice_timeout_s`
- `keep_failed_hspice`
- `run_fisher`
- `bo_n_init`
- `bo_n_iter`
- `bootstrap_n`
- `rng_seed`
- `hspice_bin`
- `va_path`

The default config sets `run_fisher: 0`, so Fisher analysis is skipped unless
explicitly enabled.

### TaO-Fit Stage 1: Physics-Informed Priors

File: `stanford_fit/matlab/stage1_extract_priors.m`

Entry point:

- `stage1_extract_priors(setB, resetB, feats, cfg)` at line 1

The output `priors` struct contains:

- `priors.names`
- `priors.mu`
- `priors.sigma`
- `priors.lb`
- `priors.ub`
- `priors.feats`

Each parameter prior is represented as:

```text
[mu, sigma, lb, ub]
```

The code first loads physical constants and config defaults:

- `T`
- `tox`
- `eps_r`
- `eps_taox`
- `a0`
- `gap_min`

Then it estimates LRS and HRS/prior quantities.

#### LRS Sinh Prior

`fit_lrs_sinh(setB, feats)` at `stanford_fit/matlab/stage1_extract_priors.m:90`
fits:

```text
I = A * sinh(V / V0)
```

on a low-voltage SET return-sweep region:

- `voltage_V > 0.02`
- `voltage_V < 0.6`
- positive current
- below `0.95 * Imax` to avoid the compliance plateau

It optimizes in log space:

```matlab
x0 = log([A_default, V0_default])
obj = @(x) mean((I - exp(x(1)) .* sinh(V ./ exp(x(2)))).^2)
```

The resulting `A_est` and `V0_est` inform:

- `I0_prior = A_est * exp(gap_min / g0_prior)`
- `V0` prior

The code comment at `stage1_extract_priors.m:17` explains the model relationship:

```text
A_est = I0 * exp(-gap_min / g0)
```

#### PF-Inspired Priors

`fit_pf_priors()` at `stanford_fit/matlab/stage1_extract_priors.m:137`
estimates `gamma0_prior` and `Ea_prior` from a Poole-Frenkel-style regression.

It fits:

```text
y = log(I / V)
x = sqrt(V)
p_pf = polyfit(x, y, 1)
```

Then it maps the fitted slope/intercept into:

- `gamma0_prior`
- `Ea_prior`

The result is clamped to reasonable model bounds:

- `gamma0_prior` between `4` and `24`
- `Ea_prior` between `0.1` and `1.0`

#### Shared vs Polarity-Split Priors

The priors are intentionally split into two sets:

Shared parameters at `stage1_extract_priors.m:56`:

- `I0`
- `g0`
- `beta`
- `Rth`
- `gap_min`
- `tox`
- `Rs`

Polarity-split parameters at `stage1_extract_priors.m:57`:

- `V0_set`, `V0_res`
- `gamma0_set`, `gamma0_res`
- `Ea_set`, `Ea_res`
- `F_min_set`, `F_min_res`
- `Vel0_set`, `Vel0_res`
- `gap_max_set`, `gap_max_res`

Initial gap is also split:

- `gap_ini_set`: HRS-like large gap
- `gap_ini_res`: LRS-like `gap_min`

This design acknowledges that the Stanford model is mostly symmetric, while the
device data may have asymmetric SET and RESET behavior.

### TaO-Fit Stage 2: Fisher Identifiability

File: `stanford_fit/matlab/stage2_identifiability.m`

Entry point:

- `stage2_identifiability(priors, setB, resetB, cfg)` at line 1

Important practical point: by default, `run_fisher` is `0`, so the function
returns `empty_fisher(priors)` immediately.

If enabled, the algorithm:

1. Uses `theta0 = priors.mu`.
2. Simulates baseline branch currents with `simulate_branches()`.
3. For each parameter, central-differences the simulated log current with
   relative step `relStep = 1e-3`.
4. Builds sensitivity matrix `S`.
5. Scales by `sigma_logI`.
6. Computes Fisher matrix:

```text
F = Sw' * Sw
```

7. Eigendecomposes `F`.
8. Computes effective and relative parameter uncertainty with `pinv(F)`.
9. Flags well-conditioned parameters using `rel_sigma < 0.5`.

The current code treats Fisher as informational. Stage 3 no longer uses Fisher
to choose active parameters; it uses YAML/config-driven active names.

### TaO-Fit Stage 3: Bayesian Optimization

File: `stanford_fit/matlab/stage3_bayesopt_driver.m`

Entry point:

- `stage3_bayesopt_driver(priors, fish, setB, resetB, cfg, outdir)` at line 1

The first important function is `resolve_active_names()` at
`stanford_fit/matlab/stage3_bayesopt_driver.m:63`.

If `cfg.active_params` exists, it parses that comma-separated string. Otherwise
it uses the default active set:

- `I0`
- `g0`
- `Rs`
- `V0_set`
- `V0_res`
- `gamma0_set`
- `Ea_set`
- `Ea_res`
- `F_min_set`
- `F_min_res`
- `Vel0_set`
- `Vel0_res`
- `gap_max_set`
- `gap_max_res`
- `gap_ini_set`
- `gap_ini_res`

Search bounds are constructed from priors:

- Parameters in `wide_set` use full `[lb, ub]`.
- Other parameters use `[mu - 3*sigma, mu + 3*sigma]`, clipped to `[lb, ub]`.
- Parameters in `log_set` use MATLAB `optimizableVariable(..., 'Transform','log')`.

`wide_set` includes:

- `I0`
- `g0`
- `Rs`
- `Vel0_set`
- `Vel0_res`
- `F_min_set`
- `F_min_res`

`log_set` includes:

- `I0`
- `g0`
- `Rs`
- `Rth`
- `Vel0_set`
- `Vel0_res`
- `F_min_set`
- `F_min_res`

The objective is:

```matlab
objFun = @(t) eval_loss(t, priors, active_names, setB, resetB, cfg)
```

The Bayesian optimizer uses:

- `bo_n_init`, default from config `48`
- `bo_n_iter`, default from config `160`
- acquisition function `expected-improvement-plus`
- deterministic objective
- serial execution

After `bayesopt`, the best point is copied back into the full `theta_full`
parameter vector.

### The Loss Function

File: `stanford_fit/matlab/eval_loss.m`

Entry point:

- `eval_loss(t, priors, active_names, setB, resetB, cfg)` at line 1

The loss is the core of the optimizer. It has three parts:

1. SET log-current residual loss
2. RESET log-current residual loss
3. switching-voltage penalty
4. soft prior penalty

The function starts with a full parameter vector:

- `theta = priors.mu`, or
- `theta = priors.theta_base` during local refinement

Then it overwrites the active parameters from the optimizer table `t`.

Forward simulation happens here:

```matlab
[Iset, Ires] = simulate_branches(theta, priors.names, setB, resetB, cfg)
```

If either branch returns non-finite values, the loss is `1e6`.

Log-current residuals are:

```text
rS = (log10(abs(Iset)) - measured_SET_log10_abs_current) / sigS
rR = (log10(abs(Ires)) - measured_RESET_log10_abs_current) / sigR
```

where `sigS` and `sigR` come from `current_sigma_log()` at
`stanford_fit/matlab/eval_loss.m:44`:

```text
sigma_logI ~= (q75_current_A - q25_current_A) / 1.35 / abs(median_current_A) / log(10)
```

Invalid or tiny sigmas are replaced with at least `0.05`.

The switching-voltage penalty detects simulated thresholds using
`detect_threshold()` at `stanford_fit/matlab/eval_loss.m:51`, which finds the
maximum SET derivative or minimum RESET derivative in log current.

The final loss is:

```text
L = Lset + Lreset + 0.5 * Lv + 0.1 * Lprior
```

This weighting means the main fit is dominated by variance-scaled log-current
matching, with softer contributions from switching voltage and priors.

### Forward Simulation Loop

Files:

- `stanford_fit/matlab/simulate_branches.m`
- `stanford_fit/matlab/write_netlist.m`
- `stanford_fit/matlab/run_hspice.m`
- `stanford_fit/matlab/parse_lis.m`
- `stanford_fit/matlab/apply_compliance.m`

`simulate_branches()` at `stanford_fit/matlab/simulate_branches.m:1` builds two
canonical model parameter vectors:

- `theta_set`
- `theta_res`

It uses `assemble_branch()` at `stanford_fit/matlab/simulate_branches.m:17`,
which resolves each model parameter in this priority:

1. Branch-specific parameter, such as `V0_set` or `V0_res`.
2. Shared parameter, such as `I0`.
3. Config override.
4. Hardcoded default.

The canonical model parameter order is:

```text
I0, g0, V0, Vel0, gamma0, beta, Ea, Rth,
F_min, gap_min, gap_max, gap_ini, tox, Rs
```

Each branch then calls:

```matlab
run_hspice(theta_branch, branch_voltage_vector, model_names, cfg)
```

followed by `apply_compliance(...)`.

#### Writing HSPICE Decks

`write_netlist()` at `stanford_fit/matlab/write_netlist.m:1` emits a transient
PWL deck matching the measured voltage samples.

It writes:

- `.hdl` path to the Verilog-A model
- `.param` lines for model parameters
- a PWL source `Vsrc NSRC 0 PWL(...)`
- series resistor `Rrs NSRC TE Rs`
- device instance `Xrram TE 0 rram_v_1_0_0`
- `.tran`
- `.print tran V(TE) I(Vsrc)`

`Rs` is used as a parasitic/probe/softening resistance. Compliance current is
not put into the deck in this path; it is applied after parsing with
`apply_compliance()`.

#### Running HSPICE

`run_hspice()` at `stanford_fit/matlab/run_hspice.m:1` creates a temporary
directory, writes `rram.sp`, and runs:

```text
timeout <hspice_timeout_s> <hspice_bin> -i rram.sp -o rram
```

The time vector is generated by `pwl_times()` at
`stanford_fit/matlab/run_hspice.m:49`:

```text
t(i) = t(i-1) + max(abs(V(i) - V(i-1)) / sweep_rate_Vps, 1e-12)
```

That gives every measured voltage sample a monotonic transient timestamp. The
same timestamps are used when parsing, which makes interpolation robust to
HSPICE adaptive stepping.

#### Parsing HSPICE Output

`parse_lis()` at `stanford_fit/matlab/parse_lis.m:1` reads `.lis` or `.mt0`
output. It searches for a table containing `time` plus `v(te)` or `i(vsrc)`,
then parses numeric triplets.

It flips source current sign:

```matlab
Iraw = -rows(:, 3)
```

Then it interpolates current to the original query timestamps:

```matlab
I = interp1(tsim, Iraw, tquery(:), 'linear', 'extrap')
```

The output is a current vector aligned one-to-one with the measured voltage
points.

#### Compliance Clamp

`apply_compliance()` clamps current magnitude to `cfg.I_compliance`, defaulting
to `1e-3` if absent. In `default_config.yaml`, `I_compliance` is `5.0e-4`.

This models the B1500 compliance behavior at the comparison/loss level.

### TaO-Fit Stage 4: Local Refinement

File: `stanford_fit/matlab/stage4_local_refine.m`

Entry point:

- `stage4_local_refine(bo_result, fish, setB, resetB, cfg)` at line 1

This stage starts from the Bayesian optimization result and runs MATLAB
`fminsearch()` on the active parameter subspace.

Important detail: active parameters are encoded in log space:

- `encode_params(x)` returns `log(max(x, realmin))`
- `decode_params(z)` returns `exp(z)`

That keeps all positive physical parameters positive during local refinement.

`wrap_loss()` rejects out-of-bounds decoded parameters by returning a large
penalty. Otherwise it constructs a table compatible with `eval_loss()`.

Default max evaluations are from `refine_max_fun_evals`, or `100` if absent.

### TaO-Fit Stage 5: Validation

File: `stanford_fit/matlab/stage5_validate.m`

Entry point:

- `stage5_validate(refined, fish, setB, resetB, data, cfg, outdir)` at line 1

The always-on validation computes:

- `r_set`
- `r_res`
- `rmse_set`
- `rmse_res`
- `dw_set`
- `dw_res`

Residuals are measured in log10 current decades:

```text
r = log10(abs(I_sim)) - measured_median_log10_abs_current
```

`durbin_watson()` at `stanford_fit/matlab/stage5_validate.m:76` reports residual
autocorrelation structure. Values far from 2 suggest structured residuals,
which may indicate model mismatch, branch asymmetry, missing series resistance,
or another systematic issue.

LOCO and bootstrap are optional:

- LOCO requires `representative_cycle_id`, at least three cycles, and
  `run_loco: 1`.
- Bootstrap requires `run_bootstrap: 1`.

With the current representative medoid CSV, LOCO/bootstrap are typically skipped
because the CSV contains a compact representative curve, not the full per-cycle
ensemble.

## Stanford Verilog-A Model Logic

Main model files:

- `rram_v_1_0_0_hspice.va`
- `stanford_fit/templates/rram_v_1_0_0_hspice.va`
- `RRAM_StanfordModel/rram_v_1_0_0.va`

The model module is `rram_v_1_0_0(TE, BE)`.

Core state:

- `gap`: conductive gap state
- `gap_ddt`: deterministic gap velocity
- `gap_random_ddt`: dynamic variation term
- `gamma`: field enhancement factor
- `T_cur`: local temperature
- `Itb`: device current

Core current relation:

```text
I = I0 * exp(-gap / g0) * sinh(Vtb / V0)
```

Core thermal relation:

```text
T_cur = T_ini + abs(Vtb * Itb * Rth)
```

Core gap-rate relation:

```text
gap_ddt = -Vel0 * exp(-q * Ea / (kb * T_cur))
          * sinh(gamma * a0 / tox * q * Vtb / (kb * T_cur))
```

The model clamps `gap` between `gap_min` and `gap_max`.

Important practical caveat: in the top-level HSPICE model, negative voltage
sets `gamma_ini = 16` before computing `gamma`, which means RESET behavior is
not controlled by `gamma0` in quite the same way as positive voltage behavior.
The project partly compensates for branch asymmetry in the MATLAB path by
running SET and RESET as separate branch simulations with split parameters.

## What To Watch When Modifying The Algorithm

Do not treat the three numbered scripts as independent utilities. Their CSV
schemas are the contract between stages.

The most important schema dependencies are:

- Stage 2 expects `01_extracted_points.csv` columns such as `condition`,
  `device_id`, `cycle_id`, `block_id`, `branch`, `point_index`, `voltage_V`,
  `current_A`, `abs_current_A`, `log10_abs_current`, and `is_good_cycle`.
- Stage 3 expects representative columns such as `branch`, `voltage_V`,
  `median_current_A`, `median_abs_current_A`, `median_log10_abs_current`, and
  preferably `butterfly_sequence_index`.
- TaO-Fit expects `branch`, `voltage_V`, `median_log10_abs_current`,
  `median_abs_current_A`, and `median_current_A`.

Key algorithmic assumptions:

- Branch labels are inferred from block title first, voltage polarity second.
- Bad cycles are excluded before representative curve selection.
- Default representative mode is a real measured medoid cycle, not a synthetic
  median curve.
- HSPICE current sign is flipped after parsing.
- SET compliance is handled as a current clamp outside the Verilog-A model.
- The MATLAB optimizer uses branch-split parameters to handle polarity
  asymmetry.
- Fisher identifiability is currently informational unless `run_fisher: 1`.
- Bayesian optimization active parameters are config-driven.

## Quick File Index

- `RUN_INSTRUCTIONS.md`: shortest operational runbook.
- `run_01.sh`: wrapper for Stage 1 extraction.
- `run_02.sh`: wrapper for Stage 2 representative curve selection.
- `run_03.sh`: wrapper for Stage 3 baseline comparison.
- `01_extract_clean_cycles.py`: parser, quality filter, point table generator.
- `02_select_device_representative_curve.py`: device selector, segment extractor,
  representative medoid/median builder.
- `03_run_stanford_baseline.py`: one-shot Stanford baseline HSPICE comparison.
- `stanford_fit/README.md`: setup and launch instructions for TaO-Fit.
- `stanford_fit/config/default_config.yaml`: main optimizer and physical defaults.
- `stanford_fit/config/fast_verify.yaml`: smaller-budget verification config.
- `stanford_fit/python/03_run_stanford_fit.py`: Python launcher for MATLAB.
- `stanford_fit/matlab/main_fit_stanford.m`: TaO-Fit orchestrator.
- `stanford_fit/matlab/stage1_extract_priors.m`: prior derivation.
- `stanford_fit/matlab/stage2_identifiability.m`: optional Fisher analysis.
- `stanford_fit/matlab/stage3_bayesopt_driver.m`: Bayesian optimization.
- `stanford_fit/matlab/stage4_local_refine.m`: Nelder-Mead refinement.
- `stanford_fit/matlab/stage5_validate.m`: residual diagnostics and optional
  LOCO/bootstrap.
- `stanford_fit/matlab/eval_loss.m`: objective function.
- `stanford_fit/matlab/simulate_branches.m`: branch-split forward model.
- `stanford_fit/matlab/write_netlist.m`: transient PWL HSPICE deck writer.
- `stanford_fit/matlab/run_hspice.m`: temp deck execution and current alignment.
- `stanford_fit/matlab/parse_lis.m`: HSPICE ASCII parser.
- `stanford_fit/matlab/apply_compliance.m`: current compliance clamp.
- `stanford_fit/templates/rram_v_1_0_0_hspice.va`: Verilog-A model used by
  TaO-Fit.
- `rram_v_1_0_0_hspice.va`: top-level HSPICE-compatible Stanford model used by
  the baseline wrapper.
- `raw_data/S*`: modern raw measurement corpus.
- `DC endurance-DOE/S*`: historical lab archive and one-off plotting scripts.
- `results/`: saved TaO-Fit outputs from previous runs.
