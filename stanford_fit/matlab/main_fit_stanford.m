function out = main_fit_stanford(csv_path, config_path, outdir, ensemble_path)
%MAIN_FIT_STANFORD Entry point for the TaO-Fit pipeline.
%   ENSEMBLE_PATH (optional): per-cycle ensemble CSV used ONLY by Stage 5 for
%   LOCO / bootstrap cross-cycle uncertainty. Stages 1-4 always fit the
%   representative curve in CSV_PATH, so the published point estimate is
%   unchanged; the ensemble only supplies the cycle distribution for CIs.
    if nargin < 4; ensemble_path = ''; end
    if ~isfolder(outdir); mkdir(outdir); end
    cfg = taofit_read_yaml(config_path);

    fprintf('[main] loading data from %s\n', csv_path);
    data = readtable(csv_path, 'TextType', 'string');
    data = normalize_input_table(data);
    [setBranch, resetBranch, feats] = split_and_featurize(data);

    if ~isempty(ensemble_path) && isfile(ensemble_path)
        fprintf('[main] loading per-cycle ensemble from %s\n', ensemble_path);
        ensemble = normalize_input_table(readtable(ensemble_path, 'TextType', 'string'));
    else
        ensemble = data;
    end

    fprintf('[main] Stage 1: physics-informed priors\n');
    priors = stage1_extract_priors(setBranch, resetBranch, feats, cfg);
    save(fullfile(outdir, 'priors.mat'), 'priors');

    fprintf('[main] Stage 3: Bayesian optimization with HSPICE\n');
    bo_result = stage3_bayesopt_driver(priors, [], setBranch, resetBranch, cfg, outdir);
    save(fullfile(outdir, 'bo_result.mat'), 'bo_result');

    fprintf('[main] Stage 4: local refinement\n');
    refined = stage4_local_refine(bo_result, [], setBranch, resetBranch, cfg);
    save(fullfile(outdir, 'refined.mat'), 'refined');

    % Stage 2 (Fisher) runs LAST, evaluated at the fitted optimum refined.theta.
    % The Cramer-Rao bound / identifiability is defined at the estimate, not the
    % prior mean; this is both statistically correct and far faster, since the
    % model sims are well-conditioned at the fit (stiff/slow at the prior mean).
    fprintf('[main] Stage 2: Fisher identifiability (at fitted optimum)\n');
    fish = stage2_identifiability(priors, setBranch, resetBranch, cfg, refined.theta);
    writematrix(fish.F, fullfile(outdir, 'fisher_matrix.csv'));
    save(fullfile(outdir, 'fisher_report.mat'), 'fish');

    fprintf('[main] Stage 4b: profile likelihood (practical identifiability)\n');
    prof = stage4b_profile_likelihood(refined, setBranch, resetBranch, cfg, outdir);
    save(fullfile(outdir, 'profile_likelihood.mat'), 'prof');

    write_identifiability_report(outdir, priors, refined, fish, prof);

    fprintf('[main] Stage 5: validation\n');
    val = stage5_validate(refined, fish, setBranch, resetBranch, ensemble, cfg, outdir);
    save(fullfile(outdir, 'validation.mat'), 'val');

    plot_fit_quality(refined, val, setBranch, resetBranch, fullfile(outdir, 'fit_quality.png'));

    out = struct('theta_best', refined.theta, 'ci95', val.ci95, ...
        'fisher', fish, 'profile', prof, 'loco_rmse', val.loco_rmse, 'cfg', cfg);
    save(fullfile(outdir, 'main_out.mat'), 'out');
    fprintf('[main] done. results in %s\n', outdir);
end

function write_identifiability_report(outdir, priors, refined, fish, prof)
%WRITE_IDENTIFIABILITY_REPORT Merge Fisher CRLB and profile-likelihood verdicts.
%   One row per model parameter; this is the headline "which parameters are
%   actually extractable" table, also consumed by stage3 auto_active refits.
    lines = {'parameter,theta,active,fisher_rel_sigma,class,profile_verdict,pf_prior_available'};
    pfa = '';
    if isfield(priors, 'pf_available')
        pfa = sprintf('%d/%d', priors.pf_available(1), priors.pf_available(2));
    end
    for j = 1:numel(priors.names)
        nm = priors.names{j};
        isActive = ismember(nm, refined.active_names);
        verdict = '';
        if isfield(prof, 'names') && ~isempty(prof.names)
            pk = find(strcmp(prof.names, nm), 1);
            if ~isempty(pk)
                verdict = prof.verdict{pk};
            end
        end
        lines{end + 1} = sprintf('%s,%.8g,%d,%.6g,%s,%s,%s', nm, ...
            refined.theta(j), isActive, fish.rel_sigma(j), fish.class{j}, ...
            verdict, pfa); %#ok<AGROW>
    end
    fid = fopen(fullfile(outdir, 'identifiability_report.csv'), 'w');
    if fid ~= -1
        fprintf(fid, '%s\n', lines{:});
        fclose(fid);
    end
end

function cfg = taofit_read_yaml(path)
    txt = fileread(path);
    cfg = struct();
    lines = splitlines(string(txt));
    for i = 1:numel(lines)
        line = strtrim(lines(i));
        if strlength(line) == 0 || startsWith(line, "#")
            continue;
        end
        parts = split(line, ":");
        if numel(parts) < 2
            continue;
        end
        key = char(strtrim(parts(1)));
        val = strtrim(strjoin(parts(2:end), ":"));
        comment = strfind(char(val), "#");
        if ~isempty(comment)
            val = strtrim(extractBefore(val, comment(1)));
        end
        val = strip(val, "both", "'");
        val = strip(val, "both", '"');
        num = str2double(val);
        if ~isnan(num)
            cfg.(key) = num;
        else
            cfg.(key) = char(val);
        end
    end
end

function data = normalize_input_table(data)
    required = ["branch", "voltage_V", "median_log10_abs_current", ...
        "median_abs_current_A", "median_current_A"];
    for k = 1:numel(required)
        if ~ismember(required(k), string(data.Properties.VariableNames))
            error('main_fit_stanford:missingColumn', 'Missing required column: %s', required(k));
        end
    end
    if ~ismember("butterfly_sequence_index", string(data.Properties.VariableNames))
        data.butterfly_sequence_index = (1:height(data))';
    end
    if ~ismember("q25_current_A", string(data.Properties.VariableNames))
        data.q25_current_A = data.median_current_A;
    end
    if ~ismember("q75_current_A", string(data.Properties.VariableNames))
        data.q75_current_A = data.median_current_A;
    end
    if ~ismember("representative_cycle_id", string(data.Properties.VariableNames))
        data.representative_cycle_id = ones(height(data), 1);
    end
end

function [setB, resetB, feats] = split_and_featurize(data)
    setB = data(upper(string(data.branch)) == "SET", :);
    resetB = data(upper(string(data.branch)) == "RESET", :);
    setB = sortrows(setB, 'butterfly_sequence_index');
    resetB = sortrows(resetB, 'butterfly_sequence_index');

    feats = struct('G_LRS', NaN, 'R_LRS', NaN, 'Vset', NaN, ...
        'Vreset', NaN, 'I_HRS_read', NaN, 'hysteresis_area', NaN);

    if height(setB) >= 5
        v = setB.voltage_V;
        logI = setB.median_log10_abs_current;
        dlogI = safe_gradient(logI, v);
        [~, ix] = max(dlogI);
        feats.Vset = v(ix);
    end

    if height(resetB) >= 5
        v = resetB.voltage_V;
        logI = resetB.median_log10_abs_current;
        dlogI = safe_gradient(logI, v);
        [~, ix] = min(dlogI);
        feats.Vreset = v(ix);
    end

    if height(setB) >= 6
        idx = setB.butterfly_sequence_index > median(setB.butterfly_sequence_index);
        lrsMask = abs(setB.voltage_V) < 0.3 & idx;
        if nnz(lrsMask) < 4
            cutoff = quantile(setB.voltage_V, 0.7);
            lrsMask = setB.voltage_V >= cutoff;
        end
        if nnz(lrsMask) >= 4
            p = polyfit(setB.voltage_V(lrsMask), setB.median_current_A(lrsMask), 1);
            feats.G_LRS = p(1);
            if p(1) ~= 0
                feats.R_LRS = 1 / p(1);
            end
        end
    end

    if height(setB) >= 2 && height(resetB) >= 2
        vAll = [setB.voltage_V; resetB.voltage_V];
        iAll = [setB.median_log10_abs_current; resetB.median_log10_abs_current];
        feats.hysteresis_area = trapz(vAll, iAll);
    end

    readMask = abs(setB.voltage_V - 0.1) < 0.02;
    if any(readMask)
        feats.I_HRS_read = mean(setB.median_abs_current_A(readMask), 'omitnan');
    end
end

function g = safe_gradient(y, x)
    x = x(:);
    y = y(:);
    [xUnique, ia] = unique(x, 'stable');
    yUnique = y(ia);
    if numel(xUnique) < 3 || any(~isfinite(xUnique)) || any(~isfinite(yUnique))
        g = zeros(size(y));
        return;
    end
    gu = gradient(yUnique, xUnique);
    g = interp1(xUnique, gu, x, 'linear', 'extrap');
end
