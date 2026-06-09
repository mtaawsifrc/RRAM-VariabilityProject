function fish = stage2_identifiability(priors, setB, resetB, cfg, theta0_in)
%STAGE2_IDENTIFIABILITY Finite-difference Fisher report at a chosen point.
%   THETA0_IN (optional): point at which to evaluate the Fisher information /
%   Cramer-Rao bound. main_fit passes the fitted optimum (refined.theta) so the
%   identifiability reflects the estimate, not the prior mean. Informational
%   only (does not gate the active set); skipped unless run_fisher=1.
    if nargin < 5; theta0_in = []; end
    if ~field_or(cfg, 'run_fisher', 0)
        fish = empty_fisher(priors);
        return;
    end
    sigma_logI = max(local_sigma_logI(setB, resetB), 0.05);
    if ~isempty(theta0_in)
        theta0 = theta0_in(:)';
    else
        theta0 = priors.mu(:)';
    end
    nP = numel(theta0);
    nV = height(setB) + height(resetB);

    [bS, bR] = simulate_branches(theta0, priors.names, setB, resetB, cfg);
    base = [bS(:); bR(:)];
    if all(~isfinite(base))
        fish = empty_fisher(priors);
        return;
    end

    S = zeros(nV, nP);
    relStep = 1e-3;
    for j = 1:nP
        tp = theta0;
        tm = theta0;
        dp = max(abs(theta0(j)) * relStep, 1e-12);
        tp(j) = theta0(j) + dp;
        tm(j) = max(theta0(j) - dp, priors.lb(j));
        [IpS, IpR] = simulate_branches(tp, priors.names, setB, resetB, cfg);
        [ImS, ImR] = simulate_branches(tm, priors.names, setB, resetB, cfg);
        Ip = [IpS(:); IpR(:)];
        Im = [ImS(:); ImR(:)];
        if any(~isfinite(Ip)) || any(~isfinite(Im))
            S(:, j) = 0;
        else
            S(:, j) = (log10(max(abs(Ip), 1e-14)) - log10(max(abs(Im), 1e-14))) ./ ...
                (log(max(tp(j), realmin)) - log(max(tm(j), realmin)));
        end
    end

    Sw = S ./ sigma_logI;
    F = Sw' * Sw;
    [U, Lam] = eig((F + F') / 2);
    lam = real(diag(Lam));
    [lam, idx] = sort(lam, 'descend');
    U = U(:, idx);
    ratio = lam ./ max(max(lam), realmin);
    eff_sigma = sqrt(max(diag(pinv(F)), 0))';
    rel_sigma = eff_sigma ./ max(abs(theta0), realmin);
    well_idx = find(rel_sigma < 0.5);
    nonid_idx = setdiff(1:nP, well_idx);

    fish = struct('F', F, 'eigvals', lam, 'eigvecs', U, 'ratio', ratio, ...
        'well_idx', well_idx, 'nonid_idx', nonid_idx, 'eff_sigma', eff_sigma, ...
        'rel_sigma', rel_sigma, 'names', {priors.names}, 'theta0', theta0);
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

function s = local_sigma_logI(setB, resetB)
    q25 = [setB.q25_current_A; resetB.q25_current_A];
    q75 = [setB.q75_current_A; resetB.q75_current_A];
    med = abs([setB.median_current_A; resetB.median_current_A]);
    s = (abs(q75 - q25) / 1.35) ./ max(med, 1e-14) / log(10);
    s(~isfinite(s) | s <= 0) = 0.2;
end

function fish = empty_fisher(priors)
    n = numel(priors.mu);
    names = priors.names;
    active = find(ismember(names, {'I0', 'g0', 'V0', 'gamma0'}));
    fish = struct('F', zeros(n), 'eigvals', zeros(n, 1), 'eigvecs', eye(n), ...
        'ratio', zeros(n, 1), 'well_idx', active, 'nonid_idx', setdiff(1:n, active), ...
        'eff_sigma', priors.sigma(:)', 'rel_sigma', priors.sigma(:)' ./ max(abs(priors.mu(:)'), realmin), ...
        'names', {priors.names}, 'theta0', priors.mu);
end

