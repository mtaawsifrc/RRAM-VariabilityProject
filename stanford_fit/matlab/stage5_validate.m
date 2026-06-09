function val = stage5_validate(refined, fish, setB, resetB, data, cfg, outdir)
%STAGE5_VALIDATE Compute residual diagnostics; LOCO/bootstrap need multi-cycle input.
    [Iset, Ires] = simulate_branches(refined.theta, fish.names, setB, resetB, cfg);

    r_set = log10(max(abs(Iset), 1e-14)) - setB.median_log10_abs_current;
    r_res = log10(max(abs(Ires), 1e-14)) - resetB.median_log10_abs_current;

    val = struct();
    val.r_set = r_set;
    val.r_res = r_res;
    val.rmse_set = sqrt(mean(r_set.^2, 'omitnan'));
    val.rmse_res = sqrt(mean(r_res.^2, 'omitnan'));
    val.dw_set = durbin_watson(r_set);
    val.dw_res = durbin_watson(r_res);
    val.loco_rmse = [];
    val.theta_bs = [];
    val.ci95 = nan(2, numel(refined.theta));
    val.validation_note = "LOCO/bootstrap skipped: representative CSV does not contain full per-cycle ensemble.";

    if ~ismember("representative_cycle_id", string(data.Properties.VariableNames))
        return;
    end

    cycles = unique(data.representative_cycle_id);
    cycles = cycles(isfinite(cycles));
    has_pidx = ismember("point_index", string(data.Properties.VariableNames));
    if numel(cycles) < 3 || ~has_pidx
        % Need >=3 distinct cycles AND a per-cycle ensemble (point_index) to
        % aggregate. The single representative curve has neither, so CIs stay NaN.
        return;
    end
    feats0 = field_or_struct(refined.priors, 'feats', struct());

    % LOCO and bootstrap are independently gated: each is heavy, and the
    % bootstrap parameter CIs are the primary cross-cycle uncertainty result.
    if field_or(cfg, 'run_loco', 0)
        loco = nan(numel(cycles), 2);
        for k = 1:numel(cycles)
            train = aggregate_cycles(data(data.representative_cycle_id ~= cycles(k), :));
            held  = aggregate_cycles(data(data.representative_cycle_id == cycles(k), :));
            if height(train) < 10 || height(held) < 4
                continue;
            end
            sb = train(upper(string(train.branch)) == "SET", :);
            rb = train(upper(string(train.branch)) == "RESET", :);
            priors_k = stage1_extract_priors(sb, rb, feats0, cfg);
            cfg_s = cfg;
            cfg_s.bo_n_init = field_or(cfg, 'loco_bo_n_init', 8);
            cfg_s.bo_n_iter = field_or(cfg, 'loco_bo_n_iter', 24);
            bo_k = stage3_bayesopt_driver(priors_k, fish, sb, rb, cfg_s, outdir);
            heldSet = held(upper(string(held.branch)) == "SET", :);
            heldRes = held(upper(string(held.branch)) == "RESET", :);
            [IhSet, IhRes] = simulate_branches(bo_k.theta, priors_k.names, heldSet, heldRes, cfg);
            rhSet = log10(max(abs(IhSet), 1e-14)) - heldSet.median_log10_abs_current;
            rhRes = log10(max(abs(IhRes), 1e-14)) - heldRes.median_log10_abs_current;
            loco(k, 1) = sqrt(mean(rhSet.^2, 'omitnan'));
            loco(k, 2) = sqrt(mean(rhRes.^2, 'omitnan'));
        end
        val.loco_rmse = loco;
        val.validation_note = "LOCO completed.";
    end

    if ~field_or(cfg, 'run_bootstrap', 0)
        return;
    end
    val.validation_note = "Bootstrap CIs computed across cycles.";
    nB = field_or(cfg, 'bootstrap_n', 100);
    cfg_b = cfg;
    cfg_b.bo_n_init = field_or(cfg, 'bootstrap_bo_n_init', 8);
    cfg_b.bo_n_iter = field_or(cfg, 'bootstrap_bo_n_iter', 24);
    theta_bs = nan(nB, numel(refined.theta));
    rng(field_or(cfg, 'rng_seed', 0) + 12345);   % reproducible, distinct from BO seed
    for b = 1:nB
        % Cluster bootstrap: resample whole cycles with replacement, then
        % aggregate into one median curve so each refit sees a single sweep.
        draw = cycles(randi(numel(cycles), [numel(cycles), 1]));
        boot = aggregate_cycles(stack_cycles(data, draw));
        bs = boot(upper(string(boot.branch)) == "SET", :);
        br = boot(upper(string(boot.branch)) == "RESET", :);
        if height(bs) < 5 || height(br) < 5
            continue;
        end
        priors_b = stage1_extract_priors(bs, br, feats0, cfg);
        bo_b = stage3_bayesopt_driver(priors_b, fish, bs, br, cfg_b, outdir);
        theta_bs(b, :) = bo_b.theta;
    end
    val.theta_bs = theta_bs;
    ok = all(isfinite(theta_bs), 2);
    if any(ok)
        val.ci95 = [quantile(theta_bs(ok, :), 0.025, 1); quantile(theta_bs(ok, :), 0.975, 1)];
    end
end

function out = stack_cycles(data, draw)
%STACK_CYCLES Vertically stack the rows of each drawn cycle, preserving
%   multiplicity (a cycle drawn twice contributes twice to the median).
    parts = cell(numel(draw), 1);
    for i = 1:numel(draw)
        parts{i} = data(data.representative_cycle_id == draw(i), :);
    end
    out = vertcat(parts{:});
end

function curve = aggregate_cycles(tbl)
%AGGREGATE_CYCLES Collapse a multi-cycle table into one median I-V curve per
%   branch. Grouping is by (branch, point_index) -- the sweep position -- so
%   the forward and return (hysteresis) halves stay distinct even where they
%   share a voltage. q25/q75 become the empirical cycle-to-cycle spread, which
%   variance-weights the fit loss.
    if isempty(tbl)
        curve = tbl;
        return;
    end
    br = upper(string(tbl.branch));
    pidx = double(tbl.point_index);
    [g, gbr, gpi] = findgroups(br, pidx);
    med = @(x) median(x, 'omitnan');
    voltage = splitapply(med, double(tbl.voltage_V), g);
    medI    = splitapply(med, double(tbl.median_current_A), g);
    medAbs  = splitapply(med, double(tbl.median_abs_current_A), g);
    medLog  = splitapply(med, double(tbl.median_log10_abs_current), g);
    q25     = splitapply(@(x) quantile(x, 0.25), double(tbl.median_current_A), g);
    q75     = splitapply(@(x) quantile(x, 0.75), double(tbl.median_current_A), g);
    curve = table(cellstr(gbr), voltage, medI, medAbs, medLog, q25, q75, gpi, ...
        'VariableNames', {'branch', 'voltage_V', 'median_current_A', ...
        'median_abs_current_A', 'median_log10_abs_current', ...
        'q25_current_A', 'q75_current_A', 'butterfly_sequence_index'});
    curve = sortrows(curve, {'branch', 'butterfly_sequence_index'});
end

function d = durbin_watson(r)
    r = r(isfinite(r));
    if numel(r) < 2 || sum(r.^2) == 0
        d = NaN;
    else
        d = sum(diff(r).^2) / sum(r.^2);
    end
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

function v = field_or_struct(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

