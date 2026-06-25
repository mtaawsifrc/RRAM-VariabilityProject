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

    % Sensitivities S_ij = d log10|I_i| / d log(theta_j) are ALREADY in
    % log-parameter coordinates (the finite-difference denominator above is
    % log(tp)-log(tm)).  Hence the Fisher information is taken directly in
    % z = log(theta) coordinates, F = Sw' * Sw with Sw = S / sigma_logI, and
    % sigma_logtheta = sqrt(diag(pinv(F))) IS the (relative / multiplicative)
    % parameter uncertainty.  Do NOT divide by theta again -- that was the
    % earlier dimensional error that produced spurious "rel_sigma" values.
    Sw = S ./ sigma_logI;
    F = Sw' * Sw;

    % SVD-based spectrum / pseudo-inverse / numerical rank.  The weighted
    % sensitivity Sw is the natural object: its singular values sv are the
    % square roots of the Fisher eigenvalues, and small sv mark sloppy
    % directions that carry essentially no information at double precision.
    [~, Ssv, V] = svd(Sw, 'econ');
    sv = diag(Ssv);
    sv = sv(:);
    if isempty(sv); sv = 0; end
    lam = sv.^2;                                   % Fisher eigenvalues (desc)
    U = V;                                          % eigenvectors of F
    ratio = lam ./ max(max(lam), realmin);
    % Numerical rank: singular values above a relative tolerance.  Anything
    % below ~1e-8 of the top singular value (1e-16 in eigenvalue terms) is
    % numerical noise, not a measurable direction -- so we report a rank, not
    % an exact "orders of magnitude" span.
    sv_tol = max(sv) * 1e-8;
    num_rank = sum(sv > sv_tol);
    % Cramer-Rao bound in log coordinates via the truncated pseudo-inverse.
    keep = sv > sv_tol;
    if any(keep)
        Cov_z = V(:, keep) * diag(1 ./ lam(keep)) * V(:, keep)';
    else
        Cov_z = zeros(nP);
    end
    sigma_logtheta = sqrt(max(diag(Cov_z), 0))';   % relative uncertainty
    eff_sigma = sigma_logtheta;                     % kept for back-compat
    rel_sigma = sigma_logtheta;                     % already relative; NO /theta
    % Approximate 95% multiplicative CI factor: theta * [1/f, f], f = exp(1.96 s)
    ci95_factor = exp(1.96 * sigma_logtheta);
    % Directions with (near-)zero weighted sensitivity carry no information;
    % the truncated pseudo-inverse leaves their variance at zero, which would
    % otherwise masquerade as "identifiable".  Flag them as unbounded.
    col_norm = sqrt(sum(Sw.^2, 1));
    no_info = (col_norm <= max(1e-12, 1e-9 * max(col_norm))) | (rel_sigma <= 0);
    rel_sigma(no_info) = Inf;
    ci95_factor(no_info) = Inf;
    well_idx = find(rel_sigma < 0.5);
    nonid_idx = setdiff(1:nP, well_idx);

    fish = struct('F', F, 'eigvals', lam, 'eigvecs', U, 'ratio', ratio, ...
        'sing_vals', sv, 'num_rank', num_rank, 'sv_tol', sv_tol, ...
        'well_idx', well_idx, 'nonid_idx', nonid_idx, 'eff_sigma', eff_sigma, ...
        'rel_sigma', rel_sigma, 'sigma_logtheta', sigma_logtheta, ...
        'ci95_factor', ci95_factor, 'names', {priors.names}, 'theta0', theta0, ...
        'class', {classify_rel_sigma(rel_sigma)});
    fprintf(['[stage2] Fisher numerical rank %d/%d (sv>%.1e*svmax); ', ...
        'report rank deficiency, not an exact eigenvalue span.\n'], ...
        num_rank, nP, 1e-8);
end

function cls = classify_rel_sigma(rel_sigma)
%CLASSIFY_REL_SIGMA Three-level identifiability verdict from the CRLB.
    cls = repmat({'non_identifiable'}, 1, numel(rel_sigma));
    cls(rel_sigma < 2.0) = {'weakly_identifiable'};
    cls(rel_sigma < 0.5) = {'identifiable'};
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
    rel = priors.sigma(:)' ./ max(abs(priors.mu(:)'), realmin);
    fish = struct('F', zeros(n), 'eigvals', zeros(n, 1), 'eigvecs', eye(n), ...
        'ratio', zeros(n, 1), 'sing_vals', zeros(n, 1), 'num_rank', 0, ...
        'sv_tol', NaN, 'well_idx', active, 'nonid_idx', setdiff(1:n, active), ...
        'eff_sigma', priors.sigma(:)', 'rel_sigma', rel, 'sigma_logtheta', rel, ...
        'ci95_factor', exp(1.96 * rel), 'names', {priors.names}, 'theta0', priors.mu, ...
        'class', {repmat({'not_evaluated'}, 1, n)});
end

