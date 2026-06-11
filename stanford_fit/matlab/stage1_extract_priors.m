function priors = stage1_extract_priors(setB, resetB, feats, cfg)
%STAGE1_EXTRACT_PRIORS Derive soft physics priors from the representative I-V curve.
%   If cfg.regime_map_csv points to a regime map (02c_classify_conduction_
%   regimes.py), the prior-fit voltage windows come from the classified
%   conduction regimes instead of hardcoded ranges: the LRS sinh fit uses the
%   ohmic window of SET_LRS_POST, and gamma0/Ea come from per-branch
%   Poole-Frenkel windows (SET_HRS_PRE / RESET_HRS_POST). If the map shows no
%   PF window for a branch (e.g. ohmic->FN HRS), PF defaults are kept with
%   inflated sigma rather than forcing a PF regression onto non-PF data.
    kB = 1.380649e-23;
    q = 1.602176634e-19;
    eps0 = 8.8541878128e-12;
    T = field_or(cfg, 'T_K', 300);
    tox = field_or(cfg, 'tox', 5e-9);
    eps_r = field_or(cfg, 'eps_r_TaOx', 25);
    eps_taox = eps_r * eps0;
    a0 = field_or(cfg, 'a0', 2.5e-10);
    gap_min = field_or(cfg, 'gap_min', 1e-10);

    regimes = load_regime_map(cfg);
    has_regimes = ~isempty(regimes);

    win_ohmic = regime_window(regimes, 'SET', 'SET_LRS_POST', 'ohmic');
    [A_est, V0_est, sig_A, sig_V0] = fit_lrs_sinh(setB, feats, win_ohmic);

    g0_prior = field_or(cfg, 'g0_prior_m', 2.75e-10);
    sig_g0 = field_or(cfg, 'g0_prior_sigma_m', 0.5e-10);
    % A_est is the sinh amplitude I0*exp(-gap_min/g0), so I0 = A*exp(gap_min/g0).
    I0_prior = A_est * exp(gap_min / g0_prior);
    sig_I0 = abs(I0_prior) * sqrt((sig_A / max(abs(A_est), realmin))^2 + ...
        (gap_min * sig_g0 / g0_prior^2)^2);

    win_pf_set = regime_window(regimes, 'SET', 'SET_HRS_PRE', 'poole_frenkel');
    win_pf_res = regime_window(regimes, 'RESET', 'RESET_HRS_POST', 'poole_frenkel');
    [g_set, sg_set, ea_set, sea_set, pf_ok_set] = fit_pf_priors( ...
        setB, field_or(feats, 'Vset', NaN), eps_taox, tox, T, a0, kB, q, ...
        win_pf_set, has_regimes, 'fwd');
    [g_res, sg_res, ea_res, sea_res, pf_ok_res] = fit_pf_priors( ...
        resetB, field_or(feats, 'Vreset', NaN), eps_taox, tox, T, a0, kB, q, ...
        win_pf_res, has_regimes, 'ret');

    F_min_prior = field_or(cfg, 'F_min_prior', 1.4e9);
    sig_Fmin = 0.3 * F_min_prior;

    % Series resistance (probe/parasitic + soft compliance). Prefer the
    % measured LRS resistance; otherwise size it so V_max/Rs ~ I_compliance.
    Rs_prior = abs(field_or(feats, 'R_LRS', NaN));
    if ~isfinite(Rs_prior) || Rs_prior <= 0
        Rs_prior = field_or(cfg, 'series_R_ohm', ...
            5.0 / field_or(cfg, 'I_compliance', 5e-4));
    end
    Rs_prior = min(max(Rs_prior, 10), 1e5);
    sig_Rs = 0.5 * Rs_prior;

    % Per-parameter prior as [mu, sigma, lb, ub]. Shared (polarity-independent)
    % parameters keep a plain name; polarity-split parameters are emitted twice
    % as <name>_set and <name>_res so the single-polarity Stanford model can fit
    % |Vset| != |Vreset| (see simulate_branches.m). gamma0/Ea may carry
    % branch-specific priors when the regime map provides per-branch PF windows.
    P = struct();
    P.I0   = [I0_prior, max(sig_I0, 0.25 * abs(I0_prior)), 1e-8, 9.9e-3];
    P.g0   = [g0_prior, sig_g0, 1.5e-10, 5.0e-10];
    P.beta = [field_or(cfg, 'beta_prior', 1.25), field_or(cfg, 'beta_sigma', 0.5), 0.1, 5.0];
    P.Rth  = [field_or(cfg, 'Rth_prior', 2.1e3), field_or(cfg, 'Rth_sigma', 1e3), 1, 1e6];
    P.gap_min = [gap_min, 0.05e-9, 5e-11, 1.0e-9];
    P.tox  = [tox, 0.5e-9, 2e-9, 1e-8];
    P.Rs   = [Rs_prior, sig_Rs, 10, 1e6];
    P.V0     = [V0_est, sig_V0, 0.05, 2.0];
    P.gamma0_set = [g_set, sg_set, 4, 24];
    P.gamma0_res = [g_res, sg_res, 4, 24];
    P.Ea_set     = [ea_set, sea_set, 0.1, 0.99];
    P.Ea_res     = [ea_res, sea_res, 0.1, 0.99];
    P.F_min  = [F_min_prior, sig_Fmin, 5e8, 2.99e9];
    P.Vel0   = [field_or(cfg, 'Vel0_prior', 10), field_or(cfg, 'Vel0_sigma', 5), 0.1, 19.9];
    P.gap_max = [field_or(cfg, 'gap_max', 1.7e-9), 0.3e-9, 1.0e-9, 1.0e-8];

    shared = {'I0', 'g0', 'beta', 'Rth', 'gap_min', 'tox', 'Rs'};
    split = {'V0', 'gamma0', 'Ea', 'F_min', 'Vel0', 'gap_max'};

    names = {}; mu = []; sigma = []; lb = []; ub = [];
    for k = 1:numel(shared)
        [names, mu, sigma, lb, ub] = push(names, mu, sigma, lb, ub, shared{k}, P.(shared{k}));
    end
    for k = 1:numel(split)
        % Branch-specific prior rows (e.g. gamma0_set) win over the shared row.
        for suffix = {'_set', '_res'}
            nm = [split{k} suffix{1}];
            if isfield(P, nm)
                row = P.(nm);
            else
                row = P.(split{k});
            end
            [names, mu, sigma, lb, ub] = push(names, mu, sigma, lb, ub, nm, row);
        end
    end
    % Initial gap: SET starts in HRS (large gap), RESET starts in LRS (gap_min).
    [names, mu, sigma, lb, ub] = push(names, mu, sigma, lb, ub, 'gap_ini_set', ...
        [field_or(cfg, 'gap_ini_HRS', 1.4e-9), 0.3e-9, 0.5e-9, 2.5e-9]);
    [names, mu, sigma, lb, ub] = push(names, mu, sigma, lb, ub, 'gap_ini_res', ...
        [gap_min, 0.05e-9, 5e-11, 5.0e-10]);

    priors = struct();
    priors.names = names;
    priors.sigma = sigma;
    priors.lb = lb;
    priors.ub = ub;
    priors.mu = min(max(mu, lb), ub);
    priors.feats = feats;
    % Regime map travels with the priors: eval_loss uses it for mechanism-aware
    % residual weighting, and pf_available flags which branches actually had a
    % PF window (false -> gamma0/Ea priors are defaults, not data-derived).
    priors.regimes = regimes;
    priors.pf_available = [pf_ok_set, pf_ok_res];

    % Ablation hook: 'plain' priors discard the physics guidance. Setting
    % sigma = Inf removes the prior penalty in eval_loss AND widens the Stage 3
    % search to the full physical bounds, so BO runs uninformed (same model,
    % same data, same budget) -- isolating the value of the physics priors.
    if strcmpi(field_or(cfg, 'prior_mode', 'physics'), 'plain')
        priors.sigma = inf(size(priors.sigma));
    end
end

function [names, mu, sigma, lb, ub] = push(names, mu, sigma, lb, ub, name, row)
    names{end + 1} = name; %#ok<AGROW>
    mu(end + 1) = row(1); %#ok<AGROW>
    sigma(end + 1) = row(2); %#ok<AGROW>
    lb(end + 1) = row(3); %#ok<AGROW>
    ub(end + 1) = row(4); %#ok<AGROW>
end

function regimes = load_regime_map(cfg)
%LOAD_REGIME_MAP Read the 02c regime map table, or return [] when not configured.
    regimes = [];
    path = field_or(cfg, 'regime_map_csv', '');
    if isempty(path) || ~(ischar(path) || isstring(path)) || ~isfile(path)
        return;
    end
    try
        regimes = readtable(path, 'TextType', 'string');
    catch err
        warning('stage1:regimeMap', 'Failed to read regime map %s: %s', ...
            char(path), err.message);
        regimes = [];
    end
end

function win = regime_window(regimes, branch, state, mech)
%REGIME_WINDOW [v_lo v_hi] of the best (highest R^2) matching regime, else NaN.
    win = [NaN, NaN];
    if isempty(regimes)
        return;
    end
    rows = strcmpi(string(regimes.branch), branch) & ...
        strcmpi(string(regimes.state), state) & ...
        strcmpi(string(regimes.mechanism), mech);
    if ~any(rows)
        return;
    end
    sub = regimes(rows, :);
    [~, ix] = max(sub.r2);
    win = [sub.v_lo(ix), sub.v_hi(ix)];
end

function [A_est, V0_est, sig_A, sig_V0] = fit_lrs_sinh(setB, feats, win)
    A_default = max(abs(field_or(feats, 'G_LRS', NaN)), 1e-7);
    if ~isfinite(A_default)
        A_default = 1e-7;
    end
    V0_default = 0.25;
    if height(setB) < 6
        A_est = A_default;
        V0_est = V0_default;
        sig_A = 0.5 * A_est;
        sig_V0 = 0.15;
        return;
    end

    % Fit the LRS sinh on the genuine low-voltage ohmic region of the SET
    % return sweep (below compliance), NOT the high-V plateau where current
    % is pinned at the SMU limit (which is ill-posed for sinh and inflates A).
    % The window comes from the classified ohmic regime when available.
    if all(isfinite(win))
        v_lo = win(1);
        v_hi = win(2);
    else
        v_lo = 0.02;
        v_hi = 0.6;
    end
    Imax = max(setB.median_abs_current_A, [], 'omitnan');
    bsi = setB.butterfly_sequence_index;
    isReturn = bsi > median(bsi, 'omitnan');
    mask = isReturn & setB.voltage_V >= v_lo & setB.voltage_V <= v_hi & ...
        setB.median_abs_current_A > 0 & setB.median_abs_current_A < 0.95 * Imax;
    if nnz(mask) < 6
        mask = setB.voltage_V >= v_lo & setB.voltage_V <= v_hi & ...
            setB.median_abs_current_A > 0 & setB.median_abs_current_A < 0.95 * Imax;
    end
    if nnz(mask) < 6
        A_est = A_default;
        V0_est = V0_default;
        sig_A = 0.5 * A_est;
        sig_V0 = 0.15;
        return;
    end

    V = setB.voltage_V(mask);
    I = setB.median_current_A(mask);
    x0 = log([A_default, V0_default]);
    obj = @(x) mean((I - exp(x(1)) .* sinh(V ./ exp(x(2)))).^2, 'omitnan');
    x = fminsearch(obj, x0, optimset('Display', 'off', 'MaxFunEvals', 300));
    A_est = min(max(exp(x(1)), 1e-8), 1e-2);
    V0_est = min(max(exp(x(2)), 0.05), 2.0);
    res = I - A_est .* sinh(V ./ V0_est);
    rel = max(std(res, 'omitnan') / max(mean(abs(I), 'omitnan'), realmin), 0.1);
    sig_A = rel * A_est;
    sig_V0 = max(0.05, rel * V0_est);
end

function [gamma0_prior, sig_gamma0, Ea_prior, sig_Ea, pf_ok] = fit_pf_priors( ...
        B, Vth, eps, tox, T, a0, kB, q, win, has_regimes, half)
%FIT_PF_PRIORS gamma0/Ea priors from a Poole-Frenkel regression on one branch.
%   WIN: PF voltage window from the regime map ([NaN NaN] if none).
%   HAS_REGIMES: a regime map was provided. If it shows no PF window for this
%   branch, do NOT force a PF fit onto non-PF (ohmic/Schottky/FN) data --
%   return the defaults with inflated sigma and pf_ok = false.
%   HALF: 'fwd' fits the pre-switching half (SET HRS), 'ret' the post-switching
%   half (RESET HRS); only enforced when a regime window is used.
    gamma0_prior = 16.5;
    sig_gamma0 = 6;
    Ea_prior = 0.6;
    sig_Ea = 0.25;
    pf_ok = false;

    if has_regimes && ~all(isfinite(win))
        sig_gamma0 = 12;
        sig_Ea = 0.4;
        return;
    end
    if height(B) < 6
        return;
    end

    Vabs = abs(B.voltage_V);
    if all(isfinite(win))
        mask = Vabs >= win(1) & Vabs <= win(2);
        bsi = B.butterfly_sequence_index;
        if strcmpi(half, 'fwd')
            mask = mask & bsi <= median(bsi, 'omitnan');
        else
            mask = mask & bsi > median(bsi, 'omitnan');
        end
    else
        if ~isfinite(Vth)
            return;
        end
        mask = Vabs > 0.3 & Vabs < 0.9 * max(abs(Vth), 0.5);
    end
    V = Vabs(mask);
    I = B.median_abs_current_A(mask);
    keep = isfinite(V) & isfinite(I) & V > 0 & I > 0;
    if nnz(keep) < 5
        if has_regimes
            sig_gamma0 = 12;
            sig_Ea = 0.4;
        end
        return;
    end

    y = log(max(I(keep), 1e-14) ./ max(V(keep), 1e-3));
    x = sqrt(V(keep));
    p_pf = polyfit(x, y, 1);
    kappa = p_pf(1);
    gamma0_prior = 2 * kappa * sqrt(pi * eps * tox) * (kB * T / q) * (tox / a0^2);
    gamma0_prior = max(min(gamma0_prior, 24), 4);
    sig_gamma0 = 0.4 * gamma0_prior;
    Ea_prior = max(0.1, min(1.0, -p_pf(2) * kB * T / q));
    pf_ok = true;
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end
