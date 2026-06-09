# Architecture Flowcharts

This document contains Mermaid flowcharts for explaining the research and code
architecture of the RRAM variability and compact-model fitting project.

The diagrams are intentionally split into multiple views:

- research architecture
- repository architecture
- artifact flow
- modern pipeline
- TaO-Fit architecture
- HSPICE fitting loop
- publication deliverables
- troubleshooting and interpretation

## 1. Research Architecture

```mermaid
flowchart TD
    experiment["RRAM experiment; TaOx devices measured with B1500"]
    processConditions["DOE process conditions; oxygen percentage and deposition power"]
    rawCurves["Raw I-V cycles; forming, SET, RESET, endurance"]
    qualityControl["Quality control; reject incomplete, weak, noisy, or failed cycles"]
    variabilityAnalysis["Variability analysis; cycle quality, device quality, HRS and LRS distributions"]
    representativeSelection["Representative selection; medoid device and cycle"]
    compactModel["Stanford-PKU RRAM compact model; Verilog-A in HSPICE"]
    baselineSimulation["Baseline simulation; compare default or chosen parameters"]
    physicsPriors["Physics-informed priors; LRS sinh and PF-style HRS features"]
    identifiability["Identifiability analysis; Fisher matrix and uncertainty flags"]
    optimization["HSPICE-in-the-loop fitting; Bayesian optimization and local refinement"]
    validation["Validation; residuals, RMSE, Durbin-Watson, optional LOCO and bootstrap"]
    publication["Publication outputs; plots, metrics, parameter tables, method claims"]

    processConditions --> experiment
    experiment --> rawCurves
    rawCurves --> qualityControl
    qualityControl --> variabilityAnalysis
    variabilityAnalysis --> representativeSelection
    representativeSelection --> baselineSimulation
    compactModel --> baselineSimulation
    representativeSelection --> physicsPriors
    physicsPriors --> identifiability
    compactModel --> optimization
    physicsPriors --> optimization
    identifiability --> optimization
    representativeSelection --> optimization
    optimization --> validation
    baselineSimulation --> publication
    validation --> publication
    variabilityAnalysis --> publication
```

## 2. Repository Architecture

```mermaid
flowchart TD
    repo["RRAM-VariabilityProject"]

    docs["Documentation; RUN_INSTRUCTIONS, walkthroughs, guides, flowcharts"]
    wrappers["Shell wrappers; run_01.sh, run_02.sh, run_03.sh"]
    modernPython["Modern Python pipeline; extraction, representative selection, baseline"]
    taofit["stanford_fit; MATLAB and HSPICE fitting framework"]
    stanfordModel["Stanford model assets; Verilog-A, benchmarks, manual"]
    modernData["raw_data; S1 through S12 measurement corpus"]
    legacyArchive["DC endurance-DOE; historical scripts, CSVs, figures"]
    resultArtifacts["results and generated step folders; outputs for analysis"]

    repo --> docs
    repo --> wrappers
    repo --> modernPython
    repo --> taofit
    repo --> stanfordModel
    repo --> modernData
    repo --> legacyArchive
    repo --> resultArtifacts

    wrappers --> modernPython
    modernData --> modernPython
    modernPython --> resultArtifacts
    taofit --> resultArtifacts
    stanfordModel --> taofit
    stanfordModel --> modernPython
    legacyArchive --> docs
```

## 3. Scientific Artifact Flow

```mermaid
flowchart LR
    rawCsv["Raw B1500 CSVs"]
    parsedCycles["Parsed cycles; CycleRecord and IVBlock"]
    qualityTables["Quality tables; cycle summary and device summary"]
    cleanPoints["Clean point table; voltage, current, branch, log current"]
    medoidCurve["Representative medoid curve"]
    fitTargets["Device metrics; Vset, Vreset, Iread, memory window"]
    baselineDeck["Baseline HSPICE deck"]
    baselineMetrics["Baseline metrics; MAE, RMSE, overlays"]
    priors["Prior table; mu, sigma, bounds"]
    fittedTheta["Fitted parameter vector"]
    validationMetrics["Validation metrics; residuals and diagnostics"]
    paperFigures["Paper and presentation figures"]

    rawCsv --> parsedCycles
    parsedCycles --> qualityTables
    parsedCycles --> cleanPoints
    qualityTables --> medoidCurve
    cleanPoints --> medoidCurve
    medoidCurve --> fitTargets
    medoidCurve --> baselineDeck
    baselineDeck --> baselineMetrics
    medoidCurve --> priors
    priors --> fittedTheta
    fittedTheta --> validationMetrics
    baselineMetrics --> paperFigures
    fitTargets --> paperFigures
    validationMetrics --> paperFigures
```

## 4. Modern Pipeline Execution Flow

```mermaid
flowchart TD
    start["Start from RUN_INSTRUCTIONS.md"]
    runOne["bash run_01.sh"]
    extract["01_extract_clean_cycles.py"]
    stepOne["step01_S1; extracted points, cycle summary, device summary"]
    runTwo["bash run_02.sh"]
    select["02_select_device_representative_curve.py"]
    stepTwo["step02_S1; selected points, programming segments, representative curve"]
    runThree["bash run_03.sh"]
    baseline["03_run_stanford_baseline.py"]
    stepThree["step03_S1_baseline; deck, sim CSV, comparison, metrics, plots"]
    diagnose["diagnose_hspice_once.m"]
    taofitRun["run_S1_proof_of_concept.sh or Python launcher"]
    finalResults["results/S1_taofit; priors, Fisher, BO, refined fit, validation"]

    start --> runOne
    runOne --> extract
    extract --> stepOne
    stepOne --> runTwo
    runTwo --> select
    select --> stepTwo
    stepTwo --> runThree
    runThree --> baseline
    baseline --> stepThree
    stepTwo --> diagnose
    diagnose --> taofitRun
    taofitRun --> finalResults
```

## 5. Stage 1 Extraction Architecture

```mermaid
flowchart TD
    inputFolder["Input folder; raw_data/S1"]
    csvScanner["collect_cycles; scan CSV files"]
    fileParser["parse_b1500_csv; read one measurement file"]
    metadataParser["Parse filename and metadata; device, test, time"]
    blockParser["Split by Analysis.Setup.Title; create IVBlock list"]
    branchInference["infer_branch; SET, RESET, MIXED, UNKNOWN"]
    cycleQuality["cycle_quality; voltage span, current range, dynamic decades"]
    cycleNumbering["Assign cycle_id within condition and device"]
    pointTable["01_extracted_points.csv"]
    cycleTable["01_cycle_summary.csv"]
    deviceTable["01_device_summary.csv"]

    inputFolder --> csvScanner
    csvScanner --> fileParser
    fileParser --> metadataParser
    fileParser --> blockParser
    blockParser --> branchInference
    branchInference --> cycleQuality
    metadataParser --> cycleNumbering
    cycleQuality --> cycleTable
    cycleQuality --> pointTable
    cycleNumbering --> pointTable
    cycleTable --> deviceTable
```

## 6. Stage 2 Representative Selection Architecture

```mermaid
flowchart TD
    stepOneInputs["Stage 1 outputs; points and device summary"]
    deviceRanking["pick_best_device; rank by good cycles and quality"]
    pointFilter["Filter good SET and RESET points for selected device"]
    segmentSplit["split_voltage_segments; monotonic voltage pieces"]
    segmentScore["choose_programming_segment; polarity, direction, span"]
    programSegments["Programming segments"]
    representativeMode{"Representative mode"}
    medianGrid["median-grid; pointwise median on voltage grid"]
    medoidScore["medoid scoring; cycle error from typical log-current curve"]
    medoidSelect["Select real representative cycle or branch"]
    repCurve["Representative curve CSV"]
    repPlot["Representative curve plot"]
    targetMetrics["Fit targets; switch voltage and current at Vread"]

    stepOneInputs --> deviceRanking
    deviceRanking --> pointFilter
    pointFilter --> segmentSplit
    segmentSplit --> segmentScore
    segmentScore --> programSegments
    programSegments --> representativeMode
    representativeMode -->|"median-grid"| medianGrid
    representativeMode -->|"medoid-cycle or medoid-branch"| medoidScore
    medoidScore --> medoidSelect
    medianGrid --> repCurve
    medoidSelect --> repCurve
    repCurve --> repPlot
    programSegments --> targetMetrics
```

## 7. Stage 3 Baseline Simulation Architecture

```mermaid
flowchart TD
    repCurve["Representative curve CSV"]
    fitWindow["filter_rep; experiment fit window"]
    sweepLimits["apply_rep_voltage_limits; match measured voltage range"]
    compliance["resolve_set_compliance_current; explicit or automatic"]
    deckMode{"Deck mode"}
    butterflyDeck["make_butterfly_deck; bipolar PWL transient"]
    separateDecks["make_deck; separate SET and RESET pulse decks"]
    hspiceRun["run_hspice; execute deck"]
    parseOutput["parse_hspice_lis or fallback_parse_stdout"]
    signConvention["apply_hspice_current_convention"]
    simTable["Simulation CSVs"]
    compareMode{"Butterfly sequence index available"}
    sequenceCompare["interpolate_butterfly_sim_to_exp; align by sequence progress"]
    voltageCompare["interpolate_sim_to_exp; align by voltage"]
    fitMetrics["fit_metric_rows; log-current errors"]
    readRatios["butterfly_read_currents; HRS and LRS ratios"]
    overlays["plot_overlay; log and linear views"]

    repCurve --> fitWindow
    repCurve --> sweepLimits
    sweepLimits --> deckMode
    compliance --> deckMode
    deckMode -->|"butterfly"| butterflyDeck
    deckMode -->|"separate"| separateDecks
    butterflyDeck --> hspiceRun
    separateDecks --> hspiceRun
    hspiceRun --> parseOutput
    parseOutput --> signConvention
    signConvention --> simTable
    simTable --> compareMode
    fitWindow --> compareMode
    compareMode -->|"yes"| sequenceCompare
    compareMode -->|"no"| voltageCompare
    sequenceCompare --> fitMetrics
    voltageCompare --> fitMetrics
    sequenceCompare --> readRatios
    fitMetrics --> overlays
    readRatios --> overlays
```

## 8. TaO-Fit MATLAB Architecture

```mermaid
flowchart TD
    inputCsv["Representative curve CSV"]
    configYaml["default_config.yaml or fast_verify.yaml"]
    mainFit["main_fit_stanford.m"]
    normalize["normalize_input_table"]
    features["split_and_featurize; Vset, Vreset, G_LRS, R_LRS"]
    stageOne["stage1_extract_priors; physics-informed priors"]
    stageTwo{"run_fisher"}
    fisher["stage2_identifiability; Fisher matrix"]
    emptyFisher["empty_fisher; placeholder report"]
    stageThree["stage3_bayesopt_driver; Bayesian optimization"]
    loss["eval_loss; log-current, threshold, prior penalties"]
    forward["simulate_branches; SET and RESET HSPICE simulations"]
    stageFour["stage4_local_refine; fminsearch polish"]
    stageFive["stage5_validate; residuals and diagnostics"]
    plotFit["plot_fit_quality"]
    outputs["priors.mat, fisher_report.mat, bo_result.mat, refined.mat, validation.mat, fit_quality.png"]

    inputCsv --> mainFit
    configYaml --> mainFit
    mainFit --> normalize
    normalize --> features
    features --> stageOne
    stageOne --> stageTwo
    stageTwo -->|"enabled"| fisher
    stageTwo -->|"disabled"| emptyFisher
    fisher --> stageThree
    emptyFisher --> stageThree
    stageThree --> loss
    loss --> forward
    forward --> loss
    loss --> stageThree
    stageThree --> stageFour
    stageFour --> loss
    stageFour --> stageFive
    stageFive --> plotFit
    plotFit --> outputs
```

## 9. Physics-Informed Prior Flow

```mermaid
flowchart TD
    repData["Representative SET and RESET data"]
    config["Config constants; T, tox, a0, eps_r, gap_min"]
    lrsRegion["Select LRS low-voltage SET return region"]
    sinhFit["Fit I = A sinh(V / V0)"]
    i0Prior["Compute I0 prior from A, gap_min, and g0 prior"]
    v0Prior["Use fitted V0 as V0 prior"]
    pfRegion["Select high-field pre-switch SET region"]
    pfFit["Fit log(I divided by V) versus sqrt(V)"]
    gammaPrior["Compute gamma0 prior"]
    eaPrior["Compute Ea prior"]
    resistancePrior["Estimate Rs from measured LRS resistance"]
    sharedPriors["Shared priors; I0, g0, beta, Rth, gap_min, tox, Rs"]
    splitPriors["Split priors; V0, gamma0, Ea, F_min, Vel0, gap_max, gap_ini"]
    priorStruct["priors struct; names, mu, sigma, lb, ub, feats"]

    repData --> lrsRegion
    config --> lrsRegion
    lrsRegion --> sinhFit
    sinhFit --> i0Prior
    sinhFit --> v0Prior
    repData --> pfRegion
    config --> pfRegion
    pfRegion --> pfFit
    pfFit --> gammaPrior
    pfFit --> eaPrior
    repData --> resistancePrior
    i0Prior --> sharedPriors
    resistancePrior --> sharedPriors
    v0Prior --> splitPriors
    gammaPrior --> splitPriors
    eaPrior --> splitPriors
    sharedPriors --> priorStruct
    splitPriors --> priorStruct
```

## 10. HSPICE-In-The-Loop Fitting Architecture

```mermaid
flowchart TD
    candidate["Candidate parameters from Bayesian optimization or fminsearch"]
    fullTheta["Full theta vector"]
    branchAssembly["assemble_branch; SET and RESET parameter vectors"]
    voltageWaveform["Measured voltage samples converted to PWL timestamps"]
    writeDeck["write_netlist; temporary HSPICE deck"]
    verilogA["Stanford Verilog-A model"]
    runCircuit["run_hspice; transient circuit simulation"]
    parseLis["parse_lis; time, voltage, current"]
    alignCurrent["Interpolate simulated current to measured samples"]
    complianceClamp["apply_compliance; enforce SMU current limit"]
    residuals["Residuals in log10 current decades"]
    thresholdPenalty["Switching-voltage penalty"]
    priorPenalty["Soft prior penalty"]
    scalarLoss["Scalar objective returned to optimizer"]

    candidate --> fullTheta
    fullTheta --> branchAssembly
    branchAssembly --> voltageWaveform
    voltageWaveform --> writeDeck
    verilogA --> writeDeck
    writeDeck --> runCircuit
    runCircuit --> parseLis
    parseLis --> alignCurrent
    alignCurrent --> complianceClamp
    complianceClamp --> residuals
    residuals --> thresholdPenalty
    thresholdPenalty --> priorPenalty
    priorPenalty --> scalarLoss
```

## 11. Publication Deliverable Flow

```mermaid
flowchart TD
    rawDataset["Raw dataset and DOE conditions"]
    qcTables["Quality-control tables"]
    selectedCurve["Representative medoid curve"]
    targetMetrics["Device target metrics; Vset, Vreset, Iread"]
    baselineOverlay["Baseline Stanford overlay"]
    baselineError["Baseline error metrics"]
    priorTable["Prior and bound table"]
    fittedTable["Fitted parameter table"]
    fitOverlay["Final fit overlay"]
    residualPlot["Residual and validation plots"]
    identifiabilityReport["Identifiability report and caveats"]
    advisorSlides["Advisor presentation"]
    manuscript["Manuscript methods, results, and supplement"]

    rawDataset --> qcTables
    qcTables --> selectedCurve
    selectedCurve --> targetMetrics
    selectedCurve --> baselineOverlay
    baselineOverlay --> baselineError
    selectedCurve --> priorTable
    priorTable --> fittedTable
    fittedTable --> fitOverlay
    fitOverlay --> residualPlot
    fittedTable --> identifiabilityReport
    targetMetrics --> advisorSlides
    baselineError --> advisorSlides
    residualPlot --> advisorSlides
    identifiabilityReport --> advisorSlides
    qcTables --> manuscript
    selectedCurve --> manuscript
    priorTable --> manuscript
    fittedTable --> manuscript
    residualPlot --> manuscript
    identifiabilityReport --> manuscript
```

## 12. Interpretation And Troubleshooting Flow

```mermaid
flowchart TD
    result["Fit or baseline result"]
    validPoints{"Enough valid comparison points"}
    noPoints["Check HSPICE output format, parser, .lis availability, and runlog"]
    highMae{"High log10 MAE or RMSE"}
    acceptable["Fit is quantitatively acceptable; inspect residual structure"]
    complianceIssue{"SET LRS plateau too high"}
    adjustCompliance["Check I_compliance and apply_set_compliance behavior"]
    ratioIssue{"LRS to HRS ratio mismatch"}
    tuneGap["Inspect g0, gap_min, gap_max, I0, and Rs"]
    voltageIssue{"Vset or Vreset shifted"}
    tuneDynamics["Inspect Vel0, gamma0, Ea, F_min, and gap_ini"]
    residualStructure{"Residuals are structured"}
    modelLimit["Discuss model limitation, polarity asymmetry, or missing parasitics"]
    publishReady["Prepare figures, tables, caveats, and reproducibility notes"]

    result --> validPoints
    validPoints -->|"no"| noPoints
    validPoints -->|"yes"| highMae
    highMae -->|"no"| acceptable
    highMae -->|"yes"| complianceIssue
    complianceIssue -->|"yes"| adjustCompliance
    complianceIssue -->|"no"| ratioIssue
    ratioIssue -->|"yes"| tuneGap
    ratioIssue -->|"no"| voltageIssue
    voltageIssue -->|"yes"| tuneDynamics
    voltageIssue -->|"no"| residualStructure
    acceptable --> residualStructure
    residualStructure -->|"yes"| modelLimit
    residualStructure -->|"no"| publishReady
    modelLimit --> publishReady
```

