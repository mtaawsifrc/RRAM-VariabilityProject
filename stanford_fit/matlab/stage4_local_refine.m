function refined = stage4_local_refine(bo_result, fish, setB, resetB, cfg)
%STAGE4_LOCAL_REFINE Nelder-Mead polish on the active subspace.
    active_names = bo_result.active_names;
    priors = bo_result.priors;
    j_active = zeros(1, numel(active_names));
    for k = 1:numel(active_names)
        j_active(k) = find(strcmp(fish.names, active_names{k}), 1);
    end

    x0 = bo_result.theta(j_active);
    z0 = encode_params(x0);
    f = @(z) wrap_loss(z, j_active, bo_result.theta, priors, active_names, setB, resetB, cfg);
    max_fun_evals = field_or(cfg, 'refine_max_fun_evals', 100);
    opts = optimset('Display', 'iter', 'MaxFunEvals', max_fun_evals, 'TolX', 1e-5, 'TolFun', 1e-5);
    [zopt, fval] = fminsearch(f, z0, opts);
    xopt = decode_params(zopt);
    theta = bo_result.theta;
    theta(j_active) = xopt;
    refined = struct('theta', theta, 'fval', fval, 'active_names', {active_names}, 'priors', priors);
end

function L = wrap_loss(z, j_active, theta_base, priors, active_names, setB, resetB, cfg)
    x = decode_params(z);
    if any(x < priors.lb(j_active)) || any(x > priors.ub(j_active)) || any(~isfinite(x))
        L = 1e6 + sum(abs(x(~isfinite(x))));
        return;
    end
    theta = theta_base;
    theta(j_active) = x;
    t = table();
    for k = 1:numel(active_names)
        t.(active_names{k}) = x(k);
    end
    priors_local = priors;
    priors_local.theta_base = theta_base;
    priors_local.loss_mu = priors.mu;
    L = eval_loss(t, priors_local, active_names, setB, resetB, cfg);
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end

function z = encode_params(x)
    z = log(max(x, realmin));
end

function x = decode_params(z)
    x = exp(z);
end
