function I = apply_compliance(I, cfg)
%APPLY_COMPLIANCE Clamp simulated current magnitude to the SMU compliance.
%   The B1500 enforces a hard current limit (compliance), so the measured
%   LRS branch is flat at I_compliance. The Stanford model has no such limit,
%   so we impose it on the simulated current before computing residuals.
    cc = 1e-3;
    if isfield(cfg, 'I_compliance') && isfinite(cfg.I_compliance) && cfg.I_compliance > 0
        cc = cfg.I_compliance;
    end
    I = sign(I) .* min(abs(I), cc);
end
