function bo_result = stage3_bayesopt_driver(priors, fish, setB, resetB, cfg, outdir) %#ok<INUSL>
%STAGE3_BAYESOPT_DRIVER Optimize the configured active Stanford parameters.
%   The active set is config-driven (active_params in the YAML), defaulting
%   to the current scale (I0,g0) AND switching dynamics so the model can
%   place Vset/Vreset and the hysteresis window. Stage 2 (Fisher) is now an
%   informational report only and no longer gates which params are fit.
    active_names = resolve_active_names(priors, cfg);

    % Ablation hook: 'defaults_only' skips optimization and returns the physics
    % prior mean (the un-tuned initial guess), so the ablation can quantify how
    % much Bayesian optimization improves on the physics priors alone.
    if field_or(cfg, 'defaults_only', 0)
        bo_result = struct('theta', priors.mu, 'active_names', {active_names}, ...
            'results', [], 'best', struct(), 'priors', priors);
        results = []; %#ok<NASGU>
        save(fullfile(outdir, 'bo_results.mat'), 'results');
        return;
    end

    % Scale/degenerate parameters search their full physical range (their
    % priors are weakly identifiable); structural priors stay near mu +/- 3 sigma.
    wide_set = {'I0', 'g0', 'Rs', 'Vel0_set', 'Vel0_res', 'F_min_set', 'F_min_res'};
    log_set = {'I0', 'g0', 'Rs', 'Rth', 'Vel0_set', 'Vel0_res', 'F_min_set', 'F_min_res'};

    vars = optimizableVariable.empty;
    for k = 1:numel(active_names)
        nm = active_names{k};
        j = find(strcmp(priors.names, nm), 1);
        if ismember(nm, wide_set)
            lo = priors.lb(j);
            hi = priors.ub(j);
        else
            lo = max(priors.lb(j), priors.mu(j) - 3 * priors.sigma(j));
            hi = min(priors.ub(j), priors.mu(j) + 3 * priors.sigma(j));
        end
        if lo >= hi
            lo = priors.lb(j);
            hi = priors.ub(j);
        end
        if ismember(nm, log_set)
            lo = max(lo, realmin);
            vars(end + 1) = optimizableVariable(nm, [lo, hi], 'Type', 'real', 'Transform', 'log'); %#ok<AGROW>
        else
            vars(end + 1) = optimizableVariable(nm, [lo, hi], 'Type', 'real'); %#ok<AGROW>
        end
    end

    objFun = @(t) eval_loss(t, priors, active_names, setB, resetB, cfg);
    n_init = field_or(cfg, 'bo_n_init', 40);
    n_iter = field_or(cfg, 'bo_n_iter', 160);

    rng(field_or(cfg, 'rng_seed', 0));
    results = bayesopt(objFun, vars, ...
        'MaxObjectiveEvaluations', n_init + n_iter, ...
        'NumSeedPoints', n_init, ...
        'AcquisitionFunctionName', 'expected-improvement-plus', ...
        'IsObjectiveDeterministic', true, ...
        'UseParallel', false, ...
        'PlotFcn', [], ...
        'Verbose', 1);

    theta_full = priors.mu;
    bestPt = bestPoint(results);
    for k = 1:numel(active_names)
        j = find(strcmp(priors.names, active_names{k}), 1);
        theta_full(j) = bestPt.(active_names{k});
    end

    bo_result = struct('theta', theta_full, 'active_names', {active_names}, ...
        'results', results, 'best', bestPt, 'priors', priors);
    save(fullfile(outdir, 'bo_results.mat'), 'results');
end

function names = resolve_active_names(priors, cfg)
%RESOLVE_ACTIVE_NAMES Active parameter list from config, else expanded default.
    default_set = {'I0', 'g0', 'Rs', ...
        'V0_set', 'V0_res', 'gamma0_set', 'Ea_set', 'Ea_res', ...
        'F_min_set', 'F_min_res', 'Vel0_set', 'Vel0_res', ...
        'gap_max_set', 'gap_max_res', 'gap_ini_set', 'gap_ini_res'};
    if isfield(cfg, 'active_params') && (ischar(cfg.active_params) || isstring(cfg.active_params))
        parts = strtrim(split(string(cfg.active_params), ','));
        parts = parts(strlength(parts) > 0);
        cand = cellstr(parts(:)');
    else
        cand = default_set;
    end
    names = cand(ismember(cand, priors.names));
    if isempty(names)
        names = default_set(ismember(default_set, priors.names));
    end
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

