# Codebase Mermaid Flowcharts

These Mermaid diagrams summarize the full codebase workflow, data movement,
module dependencies, and step-by-step algorithm logic. They are split into
multiple diagrams so each one stays readable.

## 1. High-Level Workflow

```mermaid
flowchart TD
    rawArchive["Raw measurement archive; raw_data/S* and DC endurance-DOE/S*"]
    runInstructions["RUN_INSTRUCTIONS.md"]
    runStageOne["run_01.sh"]
    extractCycles["01_extract_clean_cycles.py"]
    stepOneOutputs["step01_S1 outputs; points, cycle summary, device summary"]
    runStageTwo["run_02.sh"]
    selectRepresentative["02_select_device_representative_curve.py"]
    stepTwoOutputs["step02_S1 outputs; selected points, programming segments, representative curve"]
    runStageThree["run_03.sh"]
    baselineCompare["03_run_stanford_baseline.py"]
    stepThreeOutputs["step03_S1_baseline outputs; HSPICE decks, simulation CSVs, metrics, plots"]
    taofitLauncher["stanford_fit/python/03_run_stanford_fit.py; or MATLAB direct call"]
    taofitMain["stanford_fit/matlab/main_fit_stanford.m"]
    taofitResults["results/S1_taofit_*; priors, Fisher report, BO result, refined fit, validation"]

    runInstructions --> runStageOne
    rawArchive --> runStageOne
    runStageOne --> extractCycles
    extractCycles --> stepOneOutputs
    runInstructions --> runStageTwo
    stepOneOutputs --> runStageTwo
    runStageTwo --> selectRepresentative
    selectRepresentative --> stepTwoOutputs
    runInstructions --> runStageThree
    stepTwoOutputs --> runStageThree
    runStageThree --> baselineCompare
    baselineCompare --> stepThreeOutputs
    stepTwoOutputs --> taofitLauncher
    taofitLauncher --> taofitMain
    taofitMain --> taofitResults
```

## 2. Data Flow And Artifacts

```mermaid
flowchart LR
    b1500Csv["B1500 CSV files; raw_data/S1/*.csv"]
    cycleRecords["CycleRecord objects; path, condition, device, blocks"]
    ivBlocks["IVBlock objects; title, voltage, current"]
    pointRows["Point rows; voltage_V, current_A, abs_current_A, log10_abs_current"]
    cycleSummary["01_cycle_summary.csv; quality per cycle"]
    deviceSummary["01_device_summary.csv; quality per device"]
    extractedPoints["01_extracted_points.csv; all normalized points"]
    selectedDevice["Selected condition and device"]
    selectedPoints["*_selected_points.csv"]
    programmingSegments["*_programming_segments.csv"]
    repCurve["*_representative_curve_FIXED.csv"]
    fitTargets["*_fit_targets_FIXED.csv"]
    experimentWindow["03_experiment_fit_window.csv"]
    hspiceDeck["HSPICE deck; butterfly_baseline.sp or branch decks"]
    hspiceLis["HSPICE output; .lis or runlog"]
    simCsv["03_all_sim.csv; and branch simulation CSVs"]
    comparisonCsv["03_exp_vs_baseline_comparison.csv"]
    metricsCsv["03_fit_metrics.csv; 03_read_ratio_summary.csv"]
    plots["Overlay plots; 03_baseline_overlay.png"]

    b1500Csv --> cycleRecords
    cycleRecords --> ivBlocks
    ivBlocks --> pointRows
    pointRows --> extractedPoints
    cycleRecords --> cycleSummary
    cycleSummary --> deviceSummary
    deviceSummary --> selectedDevice
    extractedPoints --> selectedDevice
    selectedDevice --> selectedPoints
    selectedPoints --> programmingSegments
    programmingSegments --> repCurve
    programmingSegments --> fitTargets
    repCurve --> experimentWindow
    repCurve --> hspiceDeck
    hspiceDeck --> hspiceLis
    hspiceLis --> simCsv
    experimentWindow --> comparisonCsv
    simCsv --> comparisonCsv
    comparisonCsv --> metricsCsv
    comparisonCsv --> plots
```

## 3. Module Dependency Map

```mermaid
flowchart TD
    subgraph TopLevelPython["Top-level Python pipeline"]
        extractPy["01_extract_clean_cycles.py"]
        selectPy["02_select_device_representative_curve.py"]
        baselinePy["03_run_stanford_baseline.py"]
    end

    subgraph ShellWrappers["Shell wrappers"]
        runOne["run_01.sh"]
        runTwo["run_02.sh"]
        runThree["run_03.sh"]
    end

    subgraph DataDirs["Data and generated artifact directories"]
        rawData["raw_data/S*"]
        stepOne["step01_*"]
        stepTwo["step02_*"]
        stepThree["step03_*"]
        resultsDir["results/*"]
    end

    subgraph StanfordModel["Stanford model assets"]
        rootVa["rram_v_1_0_0_hspice.va"]
        templateVa["stanford_fit/templates/rram_v_1_0_0_hspice.va"]
        modelArchive["RRAM_StanfordModel/*"]
    end

    subgraph TaofitPython["Python launcher utilities"]
        pyLauncher["stanford_fit/python/03_run_stanford_fit.py"]
        hspiceUtils["stanford_fit/python/hspice_utils.py"]
    end

    subgraph TaofitMatlab["MATLAB TaO-Fit modules"]
        mainFit["main_fit_stanford.m"]
        stageOne["stage1_extract_priors.m"]
        stageTwo["stage2_identifiability.m"]
        stageThree["stage3_bayesopt_driver.m"]
        evalLoss["eval_loss.m"]
        simulateBranches["simulate_branches.m"]
        writeNetlist["write_netlist.m"]
        runHspice["run_hspice.m"]
        parseLis["parse_lis.m"]
        applyCompliance["apply_compliance.m"]
        stageFour["stage4_local_refine.m"]
        stageFive["stage5_validate.m"]
        plotFit["plot_fit_quality.m"]
    end

    runOne --> extractPy
    runTwo --> selectPy
    runThree --> baselinePy
    rawData --> extractPy
    extractPy --> stepOne
    stepOne --> selectPy
    selectPy --> stepTwo
    stepTwo --> baselinePy
    baselinePy --> stepThree
    rootVa --> baselinePy
    pyLauncher --> mainFit
    stepTwo --> pyLauncher
    mainFit --> stageOne
    mainFit --> stageTwo
    mainFit --> stageThree
    mainFit --> stageFour
    mainFit --> stageFive
    mainFit --> plotFit
    stageThree --> evalLoss
    stageFour --> evalLoss
    stageFive --> simulateBranches
    evalLoss --> simulateBranches
    simulateBranches --> runHspice
    simulateBranches --> applyCompliance
    runHspice --> writeNetlist
    runHspice --> parseLis
    writeNetlist --> templateVa
    mainFit --> resultsDir
    modelArchive --> rootVa
```

## 4. Stage 1 Algorithm: Extract And Score Cycles

```mermaid
flowchart TD
    startStageOne["Start; 01_extract_clean_cycles.py main"]
    parseArgs["Parse CLI args; folder, output-dir, quality thresholds"]
    collectCycles["collect_cycles"]
    listCsv["List CSV files; glob or recursive rglob"]
    parseCsv["parse_b1500_csv"]
    parseFilename["parse_filename_metadata"]
    readLines["read_csv_text"]
    readMetadata["extract_target and extract_record_time"]
    findTitles["Find Analysis.Setup.Title rows"]
    extractBlocks["extract_data_pairs per block"]
    makeRecord["Create CycleRecord with IVBlock list"]
    groupCycles["Group by condition and device_id"]
    assignCycleIds["Sort by time and assign cycle_number"]
    writeOutputs["write_outputs"]
    qualityLoop["For each CycleRecord"]
    inferBranches["infer_branch per block"]
    qualityScore["cycle_quality; point count, voltage span, current range, dynamic decades"]
    summaryRows["Build cycle summary rows"]
    pointRows["Build normalized point rows"]
    deviceRows["Aggregate device stats"]
    saveFiles["Save 01_cycle_summary.csv; 01_extracted_points.csv; 01_device_summary.csv"]

    startStageOne --> parseArgs
    parseArgs --> collectCycles
    collectCycles --> listCsv
    listCsv --> parseCsv
    parseCsv --> parseFilename
    parseCsv --> readLines
    readLines --> readMetadata
    readLines --> findTitles
    findTitles --> extractBlocks
    extractBlocks --> makeRecord
    makeRecord --> groupCycles
    groupCycles --> assignCycleIds
    assignCycleIds --> writeOutputs
    writeOutputs --> qualityLoop
    qualityLoop --> inferBranches
    inferBranches --> qualityScore
    qualityScore --> summaryRows
    qualityScore --> pointRows
    summaryRows --> deviceRows
    pointRows --> saveFiles
    deviceRows --> saveFiles
```

## 5. Stage 2 Algorithm: Select Representative Curve

```mermaid
flowchart TD
    startStageTwo["Start; 02_select_device_representative_curve.py main"]
    readStepOne["Read 01_extracted_points.csv; Read 01_device_summary.csv"]
    normalizeBool["Convert is_good_cycle with as_bool"]
    optionalFilters["Apply optional condition filter"]
    deviceChoice{"Was device-id provided"}
    manualDevice["Use requested device_id; and matching condition"]
    bestDevice["pick_best_device; sort by good_cycles, mean_quality_score, good_fraction"]
    filterPoints["Filter selected_points; condition, device, good cycle, SET or RESET"]
    buildSegments["build_programming_segments"]
    splitSegments["split_voltage_segments; cut on voltage direction changes"]
    scoreSegments["choose_programming_segment; branch polarity, direction, useful span"]
    modeChoice{"representative_mode"}
    medianGrid["median-grid path; make_voltage_grid and representative_branch_curve"]
    medoidPath["medoid path; representative_measured_curve"]
    scoreCycles["score_branch_cycles_against_typical; median abs log error vs typical grid"]
    selectMedoid["Select medoid-cycle or medoid-branch"]
    measuredCurve["measured_curve_from_cycle; copy real measured points into representative schema"]
    addMetadata["Add condition, device_id, butterfly_sequence_index"]
    targets["estimate_threshold and current_at_vread"]
    plotRep["plot_selected_device"]
    saveStageTwo["Save selected points, segments, representative curve, scores, targets, info, plot"]

    startStageTwo --> readStepOne
    readStepOne --> normalizeBool
    normalizeBool --> optionalFilters
    optionalFilters --> deviceChoice
    deviceChoice -->|"yes"| manualDevice
    deviceChoice -->|"no"| bestDevice
    manualDevice --> filterPoints
    bestDevice --> filterPoints
    filterPoints --> buildSegments
    buildSegments --> splitSegments
    splitSegments --> scoreSegments
    scoreSegments --> modeChoice
    modeChoice -->|"median-grid"| medianGrid
    modeChoice -->|"medoid-cycle or medoid-branch"| medoidPath
    medoidPath --> scoreCycles
    scoreCycles --> selectMedoid
    selectMedoid --> measuredCurve
    medianGrid --> addMetadata
    measuredCurve --> addMetadata
    addMetadata --> targets
    addMetadata --> plotRep
    targets --> saveStageTwo
    plotRep --> saveStageTwo
```

## 6. Stage 3 Algorithm: Baseline HSPICE Comparison

```mermaid
flowchart TD
    startStageThree["Start; 03_run_stanford_baseline.py main"]
    parseBaselineArgs["Parse representative CSV, Verilog-A path, deck mode, model parameters"]
    readRep["Read representative curve CSV"]
    autoLimits["apply_rep_voltage_limits; set_vmax and reset_vmin from measured voltage range"]
    filterExperiment["filter_rep; keep SET and RESET fit windows"]
    complianceChoice["resolve_set_compliance_current"]
    makeDeckChoice{"deck_mode"}
    makeButterfly["make_butterfly_deck; single bipolar PWL transient"]
    makeSeparate["make_deck for SET and RESET; legacy separate pulse transients"]
    runDecks["For each generated deck"]
    runHspicePy["run_hspice; execute hspice and save runlog"]
    parseLisPy["parse_hspice_lis; or fallback_parse_stdout"]
    validateSim["require_hspice_success; require_sim_points"]
    labelBranches["label_butterfly_branches; or assign branch label"]
    applyCompliancePy["apply_set_compliance"]
    saveSim["Save branch sim CSVs and 03_all_sim.csv"]
    compareChoice{"Butterfly sequence available"}
    compareButterfly["interpolate_butterfly_sim_to_exp; align by normalized sequence progress"]
    compareBranches["interpolate_sim_to_exp; align branch simulation by voltage"]
    metrics["fit_metric_rows; MAE, RMSE, median error, p90 error"]
    ratioSummary["butterfly_read_currents; read-current ratios at Vread"]
    plots["plot_overlay; log and linear overlays"]
    saveBaseline["Save comparison, parameters, metrics, ratios, plots"]

    startStageThree --> parseBaselineArgs
    parseBaselineArgs --> readRep
    readRep --> autoLimits
    autoLimits --> filterExperiment
    filterExperiment --> complianceChoice
    complianceChoice --> makeDeckChoice
    makeDeckChoice -->|"butterfly"| makeButterfly
    makeDeckChoice -->|"separate"| makeSeparate
    makeButterfly --> runDecks
    makeSeparate --> runDecks
    runDecks --> runHspicePy
    runHspicePy --> validateSim
    validateSim --> parseLisPy
    parseLisPy --> labelBranches
    labelBranches --> applyCompliancePy
    applyCompliancePy --> saveSim
    saveSim --> compareChoice
    compareChoice -->|"yes"| compareButterfly
    compareChoice -->|"no"| compareBranches
    compareButterfly --> metrics
    compareBranches --> metrics
    metrics --> ratioSummary
    ratioSummary --> plots
    plots --> saveBaseline
```

## 7. TaO-Fit Algorithm: MATLAB Optimization Pipeline

```mermaid
flowchart TD
    startTaofit["Start; main_fit_stanford(csv, config, outdir)"]
    readConfig["taofit_read_yaml; load flat YAML config"]
    readTable["readtable representative CSV"]
    normalizeInput["normalize_input_table; require core columns and fill optional columns"]
    splitFeaturize["split_and_featurize; SET, RESET, Vset, Vreset, G_LRS, R_LRS"]
    priors["Stage 1; stage1_extract_priors"]
    fisher{"run_fisher is 1"}
    fisherFull["Stage 2; finite-difference Fisher identifiability"]
    fisherEmpty["empty_fisher; informational placeholder"]
    bayesopt["Stage 3; stage3_bayesopt_driver"]
    activeNames["resolve_active_names; config active_params or default split set"]
    lossLoop["Bayesian optimization calls eval_loss"]
    localRefine["Stage 4; stage4_local_refine with fminsearch in log space"]
    validation["Stage 5; stage5_validate"]
    plotQuality["plot_fit_quality"]
    saveResults["Save priors.mat, fisher report, bo result, refined.mat, validation.mat, main_out.mat"]

    startTaofit --> readConfig
    readConfig --> readTable
    readTable --> normalizeInput
    normalizeInput --> splitFeaturize
    splitFeaturize --> priors
    priors --> fisher
    fisher -->|"yes"| fisherFull
    fisher -->|"no"| fisherEmpty
    fisherFull --> bayesopt
    fisherEmpty --> bayesopt
    bayesopt --> activeNames
    activeNames --> lossLoop
    lossLoop --> localRefine
    localRefine --> validation
    validation --> plotQuality
    plotQuality --> saveResults
```

## 8. TaO-Fit Prior Derivation Logic

```mermaid
flowchart TD
    startPriors["stage1_extract_priors"]
    constants["Load constants and config; T_K, tox, eps_r_TaOx, a0, gap_min"]
    fitLrs["fit_lrs_sinh"]
    lrsMask["Choose low-voltage SET return sweep; exclude compliance plateau"]
    fitSinh["Fit I = A sinh(V / V0); with fminsearch in log parameter space"]
    deriveI0["Derive I0_prior; I0 = A exp(gap_min / g0_prior)"]
    fitPf["fit_pf_priors"]
    pfWindow["Choose positive high-field pre-switch SET window"]
    pfRegression["Fit log(I / V) vs sqrt(V)"]
    deriveGammaEa["Map slope and intercept to gamma0_prior and Ea_prior"]
    rsPrior["Estimate Rs_prior from R_LRS; or fallback series_R_ohm"]
    sharedPriors["Create shared priors; I0, g0, beta, Rth, gap_min, tox, Rs"]
    splitPriors["Create split priors; V0, gamma0, Ea, F_min, Vel0, gap_max"]
    gapInit["Create gap_ini_set and gap_ini_res"]
    packPriors["Pack priors struct; names, mu, sigma, lb, ub, feats"]

    startPriors --> constants
    constants --> fitLrs
    fitLrs --> lrsMask
    lrsMask --> fitSinh
    fitSinh --> deriveI0
    constants --> fitPf
    fitPf --> pfWindow
    pfWindow --> pfRegression
    pfRegression --> deriveGammaEa
    constants --> rsPrior
    deriveI0 --> sharedPriors
    deriveGammaEa --> splitPriors
    rsPrior --> sharedPriors
    sharedPriors --> gapInit
    splitPriors --> gapInit
    gapInit --> packPriors
```

## 9. TaO-Fit Loss And HSPICE Forward Model

```mermaid
flowchart TD
    evalLoss["eval_loss"]
    thetaBase["Start from priors.mu; or priors.theta_base"]
    overwriteActive["Overwrite active parameters from optimizer table"]
    simulate["simulate_branches"]
    assembleSet["assemble_branch for SET; prefer *_set then shared then cfg then defaults"]
    assembleReset["assemble_branch for RESET; prefer *_res then shared then cfg then defaults"]
    runSet["run_hspice for SET voltage samples"]
    runReset["run_hspice for RESET voltage samples"]
    writeDeck["write_netlist; PWL source, Rs, Verilog-A instance"]
    executeHspice["Execute hspice with timeout"]
    parseOutput["parse_lis; parse time, V(TE), I(Vsrc), flip sign"]
    alignCurrent["Interpolate current to measured timestamps"]
    clampCurrent["apply_compliance; clamp to I_compliance"]
    residuals["Compute normalized log-current residuals; SET and RESET"]
    thresholds["detect_threshold; Vset and Vreset from log-current derivative"]
    priorPenalty["Compute prior penalty; ((theta - mu) / sigma)^2"]
    finalLoss["Final loss; Lset + Lreset + 0.5 Lv + 0.1 Lprior"]

    evalLoss --> thetaBase
    thetaBase --> overwriteActive
    overwriteActive --> simulate
    simulate --> assembleSet
    simulate --> assembleReset
    assembleSet --> runSet
    assembleReset --> runReset
    runSet --> writeDeck
    runReset --> writeDeck
    writeDeck --> executeHspice
    executeHspice --> parseOutput
    parseOutput --> alignCurrent
    alignCurrent --> clampCurrent
    clampCurrent --> residuals
    residuals --> thresholds
    thresholds --> priorPenalty
    priorPenalty --> finalLoss
```

## 10. HSPICE Execution Sequence

```mermaid
flowchart TD
    optimizerCandidate["Optimizer proposes candidate active parameters"]
    lossReceives["eval_loss receives candidate table"]
    fullTheta["Build full theta vector from priors and active parameters"]
    simulateBoth["simulate_branches runs SET and RESET paths"]
    setBranchPath["SET path; assemble *_set plus shared parameters"]
    resetBranchPath["RESET path; assemble *_res plus shared parameters"]
    makeTimes["pwl_times maps measured voltages to transient timestamps"]
    netlistWrite["write_netlist creates temporary rram.sp"]
    hspiceRun["run_hspice executes HSPICE with timeout"]
    outputChoice{"Output file available"}
    parseLisFile["parse_lis reads .lis or .mt0"]
    parseFailure["Return NaN current vector and optionally keep temp files"]
    signFlip["Flip HSPICE source-current sign"]
    interpolateTime["Interpolate simulated current to measured timestamps"]
    complianceClamp["apply_compliance clamps to I_compliance"]
    branchCurrents["Return SET and RESET current vectors"]
    scalarLoss["eval_loss computes scalar objective"]

    optimizerCandidate --> lossReceives
    lossReceives --> fullTheta
    fullTheta --> simulateBoth
    simulateBoth --> setBranchPath
    simulateBoth --> resetBranchPath
    setBranchPath --> makeTimes
    resetBranchPath --> makeTimes
    makeTimes --> netlistWrite
    netlistWrite --> hspiceRun
    hspiceRun --> outputChoice
    outputChoice -->|"yes"| parseLisFile
    outputChoice -->|"no"| parseFailure
    parseLisFile --> signFlip
    signFlip --> interpolateTime
    interpolateTime --> complianceClamp
    complianceClamp --> branchCurrents
    parseFailure --> branchCurrents
    branchCurrents --> scalarLoss
```

## 11. Legacy Archive Role

```mermaid
flowchart TD
    dcArchive["DC endurance-DOE/S*"]
    formingCsv["Forming, first reset, set-reset, endurance CSVs"]
    thresholdScripts["Vset Extraction.py; jump-based threshold extraction"]
    histogramScripts["histograp plot*.py; voltage histogram figures"]
    cdfScripts["Step 1, Step 2, Step 3 CDF scripts; LRS and HRS cumulative distributions"]
    ivScripts["folder plot.py, I-V.py, log-I-V.py, memorywindow.py; publication-style plots"]
    generatedFigures["JPG and JPEG figures"]
    modernPipeline["Modern numbered pipeline; uses raw_data/S* instead"]

    dcArchive --> formingCsv
    dcArchive --> thresholdScripts
    dcArchive --> histogramScripts
    dcArchive --> cdfScripts
    dcArchive --> ivScripts
    thresholdScripts --> generatedFigures
    histogramScripts --> generatedFigures
    cdfScripts --> generatedFigures
    ivScripts --> generatedFigures
    formingCsv -. historical source .-> modernPipeline
```
