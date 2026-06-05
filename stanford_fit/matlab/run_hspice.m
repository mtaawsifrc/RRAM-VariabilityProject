function I = run_hspice(theta, V, names, cfg)
%RUN_HSPICE Write a temporary deck, run HSPICE, and interpolate current to V.
    tmpdir = tempname;
    mkdir(tmpdir);
    sp_path = fullfile(tmpdir, 'rram.sp');
    % Canonical PWL time stamp for every measured sample. The same vector is
    % used to drive the source (write_netlist) and to map the simulated
    % transient back onto the measured points by TIME (parse_lis), which is
    % robust to HSPICE's adaptive time stepping.
    t = pwl_times(V, field_or(cfg, 'sweep_rate_Vps', 1e5));
    write_netlist(sp_path, theta, names, V, t, cfg);

    hspice_bin = field_or(cfg, 'hspice_bin', 'hspice');
    out_prefix = fullfile(tmpdir, 'rram');
    timeout_s = field_or(cfg, 'hspice_timeout_s', 30);
    cmd = sprintf('timeout %.0f "%s" -i "%s" -o "%s" 2>&1', ...
        timeout_s, hspice_bin, sp_path, out_prefix);
    [status, cmdout] = system(cmd);
    if status ~= 0
        write_text(fullfile(tmpdir, 'hspice_error.log'), cmdout);
        fprintf('[hspice FAIL] status=%d, files kept at %s\n', status, tmpdir);
        if ~isempty(cmdout)
            fprintf('[hspice output] %s\n', cmdout(1:min(500, end)));
        end
        I = nan(size(V));
        if ~field_or(cfg, 'keep_failed_hspice', 1)
            safe_rmdir(tmpdir);
        end
        return;
    end

    lis_path = fullfile(tmpdir, 'rram.lis');
    if ~isfile(lis_path)
        lis_path = fullfile(tmpdir, 'rram.mt0');
    end
    try
        I = parse_lis(lis_path, t);
    catch
        I = nan(size(V));
    end
    I = reshape(I, size(V));
    if any(~isfinite(I)) && field_or(cfg, 'keep_failed_hspice', 1)
        fprintf('[hspice PARSE FAIL] files kept at %s\n', tmpdir);
    else
        safe_rmdir(tmpdir);
    end
end

function t = pwl_times(V, sweep_rate)
%PWL_TIMES Monotone time stamp per sample at constant |dV/dt| sweep rate.
    V = V(:);
    if sweep_rate <= 0 || ~isfinite(sweep_rate)
        sweep_rate = 1e5;
    end
    t = zeros(numel(V), 1);
    for i = 2:numel(V)
        t(i) = t(i - 1) + max(abs(V(i) - V(i - 1)) / sweep_rate, 1e-12);
    end
end

function safe_rmdir(path)
    if isfolder(path)
        try
            rmdir(path, 's');
        catch
        end
    end
end

function write_text(path, txt)
    fid = fopen(path, 'w');
    if fid >= 0
        fprintf(fid, '%s', txt);
        fclose(fid);
    end
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end
