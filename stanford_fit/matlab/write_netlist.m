function write_netlist(path, theta, names, V, t, cfg)
%WRITE_NETLIST Emit a transient PWL HSPICE deck matching the measured sweep.
%   The device is driven through a series resistor Rs (probe/parasitic +
%   soft current limiting); the SMU compliance is enforced on the simulated
%   current downstream (eval_loss / stage5_validate), not in the deck.
    p = struct();
    for k = 1:numel(names)
        p.(names{k}) = theta(k);
    end

    V = V(:);
    t = t(:);
    if isempty(t) || t(end) <= 0
        tEnd = 1e-9;
    else
        tEnd = t(end);
    end

    Rs = field_or(p, 'Rs', field_or(cfg, 'series_R_ohm', 0));
    Rs = max(Rs, 1e-6);   % keep the resistor non-degenerate for HSPICE
    tran_step = field_or(cfg, 'tran_step_s', 1e-6);
    va_path = resolve_path(field_or(cfg, 'va_path', '../templates/rram_v_1_0_0_hspice.va'));
    fid = fopen(path, 'w');
    if fid < 0
        error('write_netlist:openFailed', 'Could not open %s for writing.', path);
    end
    finish = onCleanup(@() fclose(fid));

    fprintf(fid, '* TaO-Fit HSPICE transient sweep\n');
    fprintf(fid, '.option post=0 ingold=2 numdgt=8 nomod measform=3 runlvl=3\n');
    fprintf(fid, '.hdl "%s"\n', va_path);
    fprintf(fid, '.param I0=%.8e g0=%.8e V0=%.8e Vel0=%.8e gamma0=%.8e\n', ...
        p.I0, p.g0, p.V0, p.Vel0, p.gamma0);
    fprintf(fid, '.param beta=%.8e Ea=%.8e Rth=%.8e F_min=%.8e\n', ...
        p.beta, p.Ea, p.Rth, p.F_min);
    fprintf(fid, '.param gap_min=%.8e gap_max=%.8e gap_ini=%.8e tox=%.8e\n', ...
        p.gap_min, p.gap_max, p.gap_ini, p.tox);
    fprintf(fid, '.param a0=%.8e T_ini=%.8e\n', ...
        field_or(cfg, 'a0', 2.5e-10), field_or(cfg, 'T_K', 300));
    fprintf(fid, '.param Rs=%.8e\n', Rs);
    % Source -> series resistor -> device. Rs models probe/parasitic series
    % resistance and softens the LRS branch; the device sits between TE and 0.
    fprintf(fid, 'Vsrc NSRC 0 PWL(\n');
    for i = 1:numel(V)
        fprintf(fid, '+ %.8e %.8e\n', t(i), V(i));
    end
    fprintf(fid, '+ )\n');
    fprintf(fid, 'Rrs NSRC TE Rs\n');
    fprintf(fid, 'Xrram TE 0 rram_v_1_0_0\n');
    fprintf(fid, '+ I0=I0 g0=g0 V0=V0 Vel0=Vel0 gamma0=gamma0\n');
    fprintf(fid, '+ beta=beta Ea=Ea Rth=Rth F_min=F_min\n');
    fprintf(fid, '+ gap_min=gap_min gap_max=gap_max gap_ini=gap_ini tox=tox a0=a0 T_ini=T_ini model_switch=0\n');
    fprintf(fid, '.tran %.8e %.8e uic\n', tran_step, tEnd);
    fprintf(fid, '.print tran V(TE) I(Vsrc)\n');
    fprintf(fid, '.end\n');
end

function path = resolve_path(path)
    if isempty(path) || is_absolute_path(path)
        return;
    end
    here = fileparts(mfilename('fullpath'));
    path = char(java.io.File(fullfile(here, path)).getCanonicalPath());
end

function tf = is_absolute_path(path)
    tf = startsWith(path, '/') || ~isempty(regexp(path, '^[A-Za-z]:[\\/]', 'once'));
end

function v = field_or(s, fn, default)
    if isfield(s, fn)
        v = s.(fn);
    else
        v = default;
    end
end
