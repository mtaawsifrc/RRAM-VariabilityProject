function L = eval_loss(t, priors, active_names, setB, resetB, cfg)
%EVAL_LOSS Variance-scaled log-current loss plus threshold and prior terms.
    if isfield(priors, 'theta_base')
        theta = priors.theta_base;
    else
        theta = priors.mu;
    end
    for k = 1:numel(active_names)
        j = find(strcmp(priors.names, active_names{k}), 1);
        theta(j) = t.(active_names{k});
    end

    [Iset, Ires] = simulate_branches(theta, priors.names, setB, resetB, cfg);
    if any(~isfinite(Iset)) || any(~isfinite(Ires))
        L = 1e6;
        return;
    end

    sigS = current_sigma_log(setB);
    sigR = current_sigma_log(resetB);
    rS = (log10(max(abs(Iset), 1e-14)) - setB.median_log10_abs_current) ./ sigS;
    rR = (log10(max(abs(Ires), 1e-14)) - resetB.median_log10_abs_current) ./ sigR;
    % Mechanism-aware weighting: down-weight residuals in voltage windows whose
    % dominant conduction mechanism (Schottky / Fowler-Nordheim, per the 02c
    % regime map) the Stanford bulk current law cannot represent.
    wS = regime_weights(setB, 'SET', priors, cfg);
    wR = regime_weights(resetB, 'RESET', priors, cfg);
    Lset = weighted_mean_sq(rS, wS);
    Lreset = weighted_mean_sq(rR, wR);

    Vset_sim = detect_threshold(setB.voltage_V, Iset, 'set');
    Vreset_sim = detect_threshold(resetB.voltage_V, Ires, 'reset');
    sigV = voltage_step_sigma(setB, resetB);
    Lv = ((Vset_sim - priors.feats.Vset)^2 + (Vreset_sim - priors.feats.Vreset)^2) / sigV^2;

    if isfield(priors, 'loss_mu')
        loss_mu = priors.loss_mu;
    else
        loss_mu = priors.mu;
    end
    finitePrior = isfinite(priors.sigma) & priors.sigma > 0;
    Lprior = sum(((theta(finitePrior) - loss_mu(finitePrior)) ./ priors.sigma(finitePrior)).^2, 'omitnan');
    L = Lset + Lreset + 0.5 * Lv + 0.1 * Lprior;
    if ~isfinite(L)
        L = 1e6;
    end
end

function m = weighted_mean_sq(r, w)
    ok = isfinite(r) & isfinite(w);
    if ~any(ok)
        m = NaN;
        return;
    end
    m = sum(w(ok) .* r(ok).^2) / max(sum(w(ok)), realmin);
end

function w = regime_weights(B, branch, priors, cfg)
%REGIME_WEIGHTS Per-point weights from the conduction-regime map.
%   1.0 for points covered by a Stanford-representable regime (ohmic/PF) or by
%   no classified regime; cfg.nonbulk_weight for points covered only by
%   Schottky/Fowler-Nordheim regimes. B must be sorted by sequence index
%   (split_and_featurize / aggregate_cycles guarantee this).
    w = ones(height(B), 1);
    if ~isfield(priors, 'regimes') || isempty(priors.regimes) || ...
            ~field_or(cfg, 'mechanism_weighting', 1)
        return;
    end
    R = priors.regimes;
    R = R(strcmpi(string(R.branch), branch), :);
    if isempty(R)
        return;
    end
    valid = ismember(lower(string(R.mechanism)), ["ohmic", "poole_frenkel"]);
    w_low = field_or(cfg, 'nonbulk_weight', 0.3);
    if strcmpi(branch, 'SET')
        states = ["SET_HRS_PRE", "SET_LRS_POST"];
    else
        states = ["RESET_LRS_PRE", "RESET_HRS_POST"];
    end
    Vabs = abs(B.voltage_V);
    [~, ipk] = max(Vabs);            % forward/return pivot at |V| extremum
    isRet = (1:height(B))' > ipk;
    stateMatch = strcmpi(string(R.state), states(1)) .* ~isRet' + ...
        strcmpi(string(R.state), states(2)) .* isRet';   % nR x nPts
    for k = 1:height(B)
        rows = stateMatch(:, k) > 0 & R.v_lo <= Vabs(k) & Vabs(k) <= R.v_hi;
        if any(rows) && ~any(rows & valid)
            w(k) = w_low;
        end
    end
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

function sig = current_sigma_log(T)
    sig = (T.q75_current_A - T.q25_current_A) / 1.35 ./ ...
        max(abs(T.median_current_A), 1e-14) / log(10);
    sig(~isfinite(sig) | sig <= 0) = 0.2;
    sig = max(sig, 0.05);
end

function Vth = detect_threshold(V, I, kind)
    V = V(:);
    logI = log10(max(abs(I(:)), 1e-14));
    if numel(V) < 3 || any(~isfinite(V)) || any(~isfinite(logI))
        Vth = NaN;
        return;
    end
    [Vu, ia] = unique(V, 'stable');
    logIu = logI(ia);
    dlogI = gradient(logIu, Vu);
    if strcmp(kind, 'set')
        [~, ix] = max(dlogI);
    else
        [~, ix] = min(dlogI);
    end
    Vth = Vu(ix);
end

function sigV = voltage_step_sigma(setB, resetB)
    V = unique([setB.voltage_V; resetB.voltage_V]);
    dV = abs(diff(sort(V)));
    dV = dV(dV > 0);
    if isempty(dV)
        sigV = 0.05;
    else
        sigV = max(median(dV), 0.01);
    end
end
