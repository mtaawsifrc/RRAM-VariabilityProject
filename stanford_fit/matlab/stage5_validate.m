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
    if numel(cycles) < 3 || ~field_or(cfg, 'run_loco', 0)
        return;
    end

    loco = nan(numel(cycles), 2);
    for k = 1:numel(cycles)
        held = data(data.representative_cycle_id == cycles(k), :);
        train = data(data.representative_cycle_id ~= cycles(k), :);
        if height(train) < 10 || height(held) < 4
            continue;
        end
        sb = train(upper(string(train.branch)) == "SET", :);
        rb = train(upper(string(train.branch)) == "RESET", :);
        priors_k = stage1_extract_priors(sb, rb, field_or_struct(refined.priors, 'feats', struct()), cfg);
        cfg_s = cfg;
        cfg_s.bo_n_init = field_or(cfg, 'loco_bo_n_init', 10);
        cfg_s.bo_n_iter = field_or(cfg, 'loco_bo_n_iter', 40);
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
    val.validation_note = "LOCO completed; bootstrap still skipped unless run_bootstrap=1.";

    if ~field_or(cfg, 'run_bootstrap', 0)
        return;
    end
    nB = field_or(cfg, 'bootstrap_n', 100);
    theta_bs = nan(nB, numel(refined.theta));
    for b = 1:nB
        idx = cycles(randi(numel(cycles), [numel(cycles), 1]));
        boot = data(ismember(data.representative_cycle_id, idx), :);
        bs = boot(upper(string(boot.branch)) == "SET", :);
        br = boot(upper(string(boot.branch)) == "RESET", :);
        priors_b = stage1_extract_priors(bs, br, field_or_struct(refined.priors, 'feats', struct()), cfg);
        cfg_b = cfg;
        cfg_b.bo_n_init = field_or(cfg, 'bootstrap_bo_n_init', 10);
        cfg_b.bo_n_iter = field_or(cfg, 'bootstrap_bo_n_iter', 40);
        bo_b = stage3_bayesopt_driver(priors_b, fish, bs, br, cfg_b, outdir);
        theta_bs(b, :) = bo_b.theta;
    end
    val.theta_bs = theta_bs;
    val.ci95 = [quantile(theta_bs, 0.025, 1); quantile(theta_bs, 0.975, 1)];
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

