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
    Lset = mean(rS.^2, 'omitnan');
    Lreset = mean(rR.^2, 'omitnan');

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
