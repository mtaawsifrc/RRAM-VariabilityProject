function [Iset, Ires] = simulate_branches(theta, names, setB, resetB, cfg)
%SIMULATE_BRANCHES Polarity-split forward model.
%   The Stanford-PKU model is single-polarity, so |Vset| != |Vreset| cannot be
%   captured with one parameter set. We run two short transients: the SET branch
%   (starting in HRS) with its own {V0,gamma0,Ea,F_min,Vel0,gap_max,gap_ini}_set,
%   and the RESET branch (starting in LRS) with the *_res set. Scale/parasitic
%   parameters (I0,g0,beta,Rth,gap_min,tox,Rs) are shared. Both currents are
%   clamped to the SMU compliance.
    model_names = {'I0', 'g0', 'V0', 'Vel0', 'gamma0', 'beta', 'Ea', 'Rth', ...
        'F_min', 'gap_min', 'gap_max', 'gap_ini', 'tox', 'Rs'};
    theta_set = assemble_branch(theta, names, model_names, 'set', cfg);
    theta_res = assemble_branch(theta, names, model_names, 'res', cfg);
    Iset = apply_compliance(run_hspice(theta_set, setB.voltage_V, model_names, cfg), cfg);
    Ires = apply_compliance(run_hspice(theta_res, resetB.voltage_V, model_names, cfg), cfg);
end

function tvec = assemble_branch(theta, names, model_names, branch, cfg)
%ASSEMBLE_BRANCH Map a (possibly split) theta onto the canonical model vector.
%   For each model parameter, prefer the branch-specific entry "<name>_<branch>",
%   then a shared entry "<name>", then a cfg override, then a hard default.
    defaults = struct('I0', 1e-4, 'g0', 2.75e-10, 'V0', 0.43, 'Vel0', 10, ...
        'gamma0', 16.5, 'beta', 1.25, 'Ea', 0.6, 'Rth', 2.1e3, 'F_min', 1.4e9, ...
        'gap_min', 1e-10, 'gap_max', 1.7e-9, 'gap_ini', 1.4e-9, 'tox', 5e-9, 'Rs', 1e4);
    tvec = zeros(1, numel(model_names));
    for i = 1:numel(model_names)
        m = model_names{i};
        j = find(strcmp(names, [m '_' branch]), 1);
        if isempty(j)
            j = find(strcmp(names, m), 1);
        end
        if ~isempty(j)
            tvec(i) = theta(j);
        elseif isfield(cfg, m)
            tvec(i) = cfg.(m);
        else
            tvec(i) = defaults.(m);
        end
    end
end
