function prof = stage4b_profile_likelihood(refined, setB, resetB, cfg, outdir)
%STAGE4B_PROFILE_LIKELIHOOD 1-D loss profiles around the fitted optimum.
%   Fisher (Stage 2) is a local, linearized bound; a flat 1-D profile is the
%   direct, journal-grade evidence of *practical* non-identifiability. For each
%   active parameter, scan n_profile points across
%   [max(lb, theta-2sigma), min(ub, theta+2sigma)] with every other parameter
%   fixed at the optimum, then classify by the loss rise at the window edges
%   (chi^2-style thresholds): min-edge rise < 1 -> flat (practically
%   non-identifiable), < 4 -> weak, otherwise identifiable.
%
%   Gated by cfg.run_profile (default 0): each grid point costs one SET + one
%   RESET HSPICE simulation, so enable this for final/publication runs only.
%
%   Outputs in OUTDIR:
%     profile_likelihood.csv  long format: parameter,value,loss
%     profile_summary.csv     parameter,theta_hat,loss_opt,delta_lo,delta_hi,verdict
    prof = struct('names', {{}}, 'theta_hat', [], 'loss_opt', NaN, ...
        'delta_lo', [], 'delta_hi', [], 'verdict', {{}}, 'grids', {{}}, 'losses', {{}});
    if ~field_or(cfg, 'run_profile', 0)
        return;
    end
    priors = refined.priors;
    names = refined.active_names;
    nG = max(3, round(field_or(cfg, 'n_profile', 7)));

    priors_local = priors;
    priors_local.theta_base = refined.theta;
    priors_local.loss_mu = priors.mu;

    % Loss at the optimum (reference for the profile deltas).
    j1 = find(strcmp(priors.names, names{1}), 1);
    t0 = table();
    t0.(names{1}) = refined.theta(j1);
    L0 = eval_loss(t0, priors_local, names(1), setB, resetB, cfg);
    fprintf('[stage4b] profiling %d parameters, %d points each (loss_opt=%.4g)\n', ...
        numel(names), nG, L0);

    long_lines = {'parameter,value,loss'};
    summ_lines = {'parameter,theta_hat,loss_opt,delta_lo,delta_hi,verdict'};
    for k = 1:numel(names)
        nm = names{k};
        j = find(strcmp(priors.names, nm), 1);
        th = refined.theta(j);
        sg = priors.sigma(j);
        if ~isfinite(sg) || sg <= 0
            sg = 0.5 * max(abs(th), realmin);
        end
        lo = max(priors.lb(j), th - 2 * sg);
        hi = min(priors.ub(j), th + 2 * sg);
        if ~(hi > lo)
            continue;
        end
        g = linspace(lo, hi, nG);
        [~, inear] = min(abs(g - th));
        g(inear) = th;                      % include the optimum exactly
        L = nan(1, nG);
        for m = 1:nG
            if g(m) == th
                L(m) = L0;
                continue;
            end
            t = table();
            t.(nm) = g(m);
            L(m) = eval_loss(t, priors_local, names(k), setB, resetB, cfg);
        end
        d_lo = L(1) - L0;
        d_hi = L(end) - L0;
        if min(L) < L0 - 1e-6
            % The 1-D scan found a lower loss than the reported optimum: the
            % local refinement did not converge. The profile verdict for this
            % parameter is unreliable; refit with a larger refine budget.
            warning('stage4b:notConverged', ...
                '%s: scan found loss %.6g < optimum %.6g; refine not converged', ...
                nm, min(L), L0);
        end
        d_min = min(d_lo, d_hi);
        if d_min < 1
            verdict = 'flat_non_identifiable';
        elseif d_min < 4
            verdict = 'weakly_identifiable';
        else
            verdict = 'identifiable';
        end
        fprintf('[stage4b] %-12s dlo=%.3g dhi=%.3g -> %s\n', nm, d_lo, d_hi, verdict);
        prof.names{end + 1} = nm;
        prof.theta_hat(end + 1) = th;
        prof.delta_lo(end + 1) = d_lo;
        prof.delta_hi(end + 1) = d_hi;
        prof.verdict{end + 1} = verdict;
        prof.grids{end + 1} = g;
        prof.losses{end + 1} = L;
        for m = 1:nG
            long_lines{end + 1} = sprintf('%s,%.8g,%.8g', nm, g(m), L(m)); %#ok<AGROW>
        end
        summ_lines{end + 1} = sprintf('%s,%.8g,%.8g,%.6g,%.6g,%s', ...
            nm, th, L0, d_lo, d_hi, verdict); %#ok<AGROW>
    end
    prof.loss_opt = L0;

    write_lines(fullfile(outdir, 'profile_likelihood.csv'), long_lines);
    write_lines(fullfile(outdir, 'profile_summary.csv'), summ_lines);
end

function write_lines(path, lines)
    fid = fopen(path, 'w');
    if fid == -1
        warning('stage4b:io', 'Could not write %s', path);
        return;
    end
    fprintf(fid, '%s\n', lines{:});
    fclose(fid);
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end
