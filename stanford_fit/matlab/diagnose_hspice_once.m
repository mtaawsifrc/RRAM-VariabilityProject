function I = diagnose_hspice_once(csv_path, config_path)
%DIAGNOSE_HSPICE_ONCE Run one safe HSPICE evaluation and keep files on failure.
    cfg = read_yaml_config(config_path);
    cfg.hspice_timeout_s = 60;
    cfg.keep_failed_hspice = 1;
    cfg.sweep_rate_Vps = 1e5;
    cfg.tran_step_s = 1e-6;

    data = readtable(csv_path, 'TextType', 'string');
    V = data.voltage_V;
    names = {'I0','g0','V0','Vel0','gamma0','beta','Ea','Rth', ...
        'F_min','gap_min','gap_max','gap_ini','tox','Rs'};
    theta = [1e-4, 2.75e-10, 0.43, 10, 16.5, 1.25, 0.6, ...
        2.1e3, 1.4e9, 1e-10, 1.7e-9, 1.4e-9, 5e-9, 1.3e3];

    fprintf('[diagnose] which hspice:\n');
    system('which hspice');
    tic;
    I = run_hspice(theta, V, names, cfg);
    elapsed = toc;
    I = apply_compliance(I, cfg);
    cc = 1e-3;
    if isfield(cfg, 'I_compliance'); cc = cfg.I_compliance; end
    fprintf('[diagnose] elapsed_s=%.3f finite_points=%d/%d max|I|=%.3e cc=%.3e\n', ...
        elapsed, nnz(isfinite(I)), numel(I), max(abs(I)), cc);
end
