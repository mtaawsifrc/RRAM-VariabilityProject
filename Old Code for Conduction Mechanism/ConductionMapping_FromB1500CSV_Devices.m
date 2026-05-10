function ConductionMapping_FromB1500CSV_Devices()
% ConductionMapping_FromB1500CSV_Devices
% One code -> generates 2 figures:
%   Fig 1: SET-side conduction map  (HRS pre-SET on + up-sweep, LRS post-SET on + down-sweep)
%   Fig 2: RESET-side conduction map (pre-RESET LRS on - sweep, post-RESET HRS after rupture)
%
% Designed for Keysight/B1500 rich CSV with blocks:
%   AnalysisSetup, Analysis.Setup.Title, Set
%   AnalysisSetup, Analysis.Setup.Title, Reset
%   DataValue, V, I
%
% ----------------------------
% USER: point to your extracted ZIP root (or your folder with deviceX subfolders)
% ----------------------------
root = "D:\DRC_ICONS_2026\Alireza\Conduction mechanism\";   % <-- change to your local path

% For now: only these devices
deviceFolders = ["device4","device14","device15"];
deviceNames   = ["Device 4","Device 14","Device 15"];  % display titles

% Use only first N cycles by timestamp (set inf for all)
maxCycles = inf;     % e.g., 20 for quick test
minPtsPerBin = 6;    % minimum points in each V-bin to classify

mechNames = ["Ohmic","Schottky","Poole-Frenkel","Fowler-Nordheim"];

% -------- Default bin templates (will auto-clip to each device's max V) --------
% SET-side: positive sweep
edges_SET_HRS_template = [0.00 0.30 0.625 0.90 1.50];   % HRS pre-SET (+ up-sweep)
edges_SET_LRS_template = [0.10 0.30 0.60  0.90 1.50];   % LRS post-SET (+ down-sweep)

% RESET-side: use |V| on negative sweep (pre/post rupture)
edges_RESET_template   = [0.00 0.30 0.60 0.90 1.50 2.50]; % |V| bins (auto-extends/clips)

% =====================================================================
% Build file lists per device
% =====================================================================
nDev = numel(deviceFolders);
filesByDev = cell(nDev,1);

for di = 1:nDev
    folder = fullfile(root, deviceFolders(di));
    L = dir(fullfile(folder,"*.csv"));
    if isempty(L)
        error("No CSV files found in: %s", folder);
    end
    files = string(fullfile({L.folder},{L.name}));

    % sort by timestamp
    t = NaT(numel(files),1);
    for k = 1:numel(files)
        t(k) = read_record_time(files(k));
        if isnat(t(k))
            d = dir(files(k));
            t(k) = datetime(d.datenum,'ConvertFrom','datenum');
        end
    end
    [~,ix] = sort(t);
    files = files(ix);

    if isfinite(maxCycles) && numel(files) > maxCycles
        files = files(1:maxCycles);
    end

    filesByDev{di} = files;
end

% =====================================================================
% Auto-clip voltage edges PER DEVICE based on data ranges
% =====================================================================
edges_SET_HRS = cell(nDev,1);
edges_SET_LRS = cell(nDev,1);
edges_RESET   = cell(nDev,1);

labels_SET_HRS = cell(nDev,1);
labels_SET_LRS = cell(nDev,1);
labels_RESET   = cell(nDev,1);

for di = 1:nDev
    [maxVset, maxVreset] = scan_max_ranges(filesByDev{di}); % maxVset: +V, maxVreset: |neg V|
    edges_SET_HRS{di} = clip_edges(edges_SET_HRS_template, maxVset);
    edges_SET_LRS{di} = clip_edges(edges_SET_LRS_template, maxVset);
    edges_RESET{di}   = clip_edges(edges_RESET_template,   maxVreset);

    labels_SET_HRS{di} = make_bin_labels(edges_SET_HRS{di});
    labels_SET_LRS{di} = make_bin_labels(edges_SET_LRS{di});
    labels_RESET{di}   = make_bin_labels(edges_RESET{di});
end

% =====================================================================
% FIGURE 1: SET-side conduction map (HRS up-sweep pre-SET, LRS down-sweep post-SET)
% =====================================================================
P_set_HRS = cell(nDev,1); n_set_HRS = cell(nDev,1);
P_set_LRS = cell(nDev,1); n_set_LRS = cell(nDev,1);

for di = 1:nDev
    [mechH, nH] = build_set_hrs_map(filesByDev{di}, edges_SET_HRS{di}, minPtsPerBin);
    [mechL, nL] = build_set_lrs_map(filesByDev{di}, edges_SET_LRS{di}, minPtsPerBin);

    P_set_HRS{di} = mech_probabilities(mechH, 4);  n_set_HRS{di} = nH;
    P_set_LRS{di} = mech_probabilities(mechL, 4);  n_set_LRS{di} = nL;
end

% figure('Color','w','Position',[120 80 1200 650]);
% tiledlayout(2, nDev, 'Padding','compact', 'TileSpacing','compact');
figure('Color','w','Position',[120 80 1200 650]);

% t = tiledlayout(2, nDev, 'TileSpacing','compact');
% t.Padding = 'compact';
% t.OuterPosition = [0 0 1 0.94];   % reserve space for sgtitle

for di = 1:nDev
    nexttile(di);
    stacked_prob_plot(P_set_HRS{di}, n_set_HRS{di}, labels_SET_HRS{di});
    title(sprintf('%s: HRS (Up-sweep, pre-SET)', deviceNames(di)));
    if di==1, ylabel("Probability"); end
end
for di = 1:nDev
    nexttile(nDev + di);
    stacked_prob_plot(P_set_LRS{di}, n_set_LRS{di}, labels_SET_LRS{di});
    title(sprintf('%s: LRS (Down-sweep, post-SET)', deviceNames(di)));
    if di==1, ylabel("Probability"); end
end

lg = legend(mechNames,'Location','southoutside','Orientation','horizontal');
lg.Layout.Tile = 'south';
sgtitle("SET-side Statistical Conduction Map (dominant mechanism per V bin)");

% =====================================================================
% FIGURE 2: RESET-side conduction map (pre-rupture LRS, post-rupture HRS)
% =====================================================================
P_pre  = cell(nDev,1); n_pre  = cell(nDev,1);
P_post = cell(nDev,1); n_post = cell(nDev,1);

for di = 1:nDev
    [mechPre,  nPre]  = build_reset_map(filesByDev{di}, edges_RESET{di}, "pre",  minPtsPerBin);
    [mechPost, nPost] = build_reset_map(filesByDev{di}, edges_RESET{di}, "post", minPtsPerBin);

    P_pre{di}  = mech_probabilities(mechPre,  4);  n_pre{di}  = nPre;
    P_post{di} = mech_probabilities(mechPost, 4);  n_post{di} = nPost;
end

% figure('Color','w','Position',[120 80 1200 650]);
% tiledlayout(2, nDev, 'Padding','compact', 'TileSpacing','compact');
figure('Color','w','Position',[120 80 1200 650]);

% t = tiledlayout(2, nDev, 'TileSpacing','compact');
% t.Padding = 'compact';
% t.OuterPosition = [0 0 1 0.94];   % reserve space for sgtitle

for di = 1:nDev
    nexttile(di);
    stacked_prob_plot(P_pre{di}, n_pre{di}, labels_RESET{di});
    title(sprintf('%s: RESET pre-rupture (LRS on - sweep)', deviceNames(di)));
    if di==1, ylabel("Probability"); end
end
for di = 1:nDev
    nexttile(nDev + di);
    stacked_prob_plot(P_post{di}, n_post{di}, labels_RESET{di});
    title(sprintf('%s: RESET post-rupture (HRS after RESET)', deviceNames(di)));
    if di==1, ylabel("Probability"); end
end

lg2 = legend(mechNames,'Location','southoutside','Orientation','horizontal');
lg2.Layout.Tile = 'south';
sgtitle("RESET-side Statistical Conduction Map (dominant mechanism per |V| bin)");

end

% =====================================================================
% ========================= CSV PARSING HELPERS ========================
% =====================================================================

function t = read_record_time(filePath)
% Reads: MetaData, TestRecord.RecordTime, 02/03/2026 16:26:08
    t = NaT;
    try
        txt = fileread(filePath);
    catch
        return;
    end
    lines = splitlines(string(txt));
    m = regexp(lines, '^MetaData,\s*TestRecord\.RecordTime,\s*(.*)$', 'tokens', 'once');
    m = m(~cellfun(@isempty,m));
    if isempty(m), return; end
    ts = strtrim(string(m{1}));
    try
        t = datetime(ts,'InputFormat','MM/dd/uuuu HH:mm:ss');
    catch
        try
            t = datetime(ts);
        catch
            t = NaT;
        end
    end
end

function blocks = read_b1500_blocks(filePath)
% Returns struct array: blocks(i).title, blocks(i).V, blocks(i).I
    txt = fileread(filePath);
    lines = splitlines(string(txt));

    titleTok = regexp(lines, '^AnalysisSetup,\s*Analysis\.Setup\.Title,\s*(.*)$', 'tokens', 'once');
    titleIdx = find(~cellfun(@isempty, titleTok));

    blocks = struct('title',{},'V',{},'I',{});

    if isempty(titleIdx)
        [V,I] = extract_DataValue_pairs(lines);
        blocks(1).title = "All";
        blocks(1).V = V; blocks(1).I = I;
        return;
    end

    for bi = 1:numel(titleIdx)
        i0 = titleIdx(bi);
        if bi < numel(titleIdx), i1 = titleIdx(bi+1)-1; else, i1 = numel(lines); end
        seg = lines(i0:i1);

        if ~any(startsWith(strtrim(seg), "DataValue,")), continue; end
        [V,I] = extract_DataValue_pairs(seg);

        blocks(end+1).title = strtrim(string(titleTok{i0}{1})); %#ok<AGROW>
        blocks(end).V = V;
        blocks(end).I = I;
    end
end

function [V,I] = extract_DataValue_pairs(lines)
% Extracts numeric pairs from lines like: "DataValue, -0.02, -5.4864E-07"
    dv = lines(startsWith(strtrim(lines), "DataValue,"));
    V = []; I = [];
    if isempty(dv), return; end

    tok = regexp(dv, '^DataValue,\s*([^,]+)\s*,\s*([^,]+)\s*$', 'tokens', 'once');
    tok = tok(~cellfun(@isempty,tok));
    if isempty(tok), return; end

    V = nan(numel(tok),1);
    I = nan(numel(tok),1);
    for k = 1:numel(tok)
        V(k) = str2double(tok{k}{1});
        I(k) = str2double(tok{k}{2});
    end

    good = isfinite(V) & isfinite(I);
    V = V(good);
    I = I(good);
end

% function [Vset, Iset, Vreset, Ireset] = get_set_reset_blocks(filePath)
% % Grabs first block whose title contains "set" and first whose title contains "reset".
%     blocks = read_b1500_blocks(filePath);
%     titles = lower(string({blocks.title}));
% 
%     iSet   = find(contains(titles,"set"),   1,'first');
%     iReset = find(contains(titles,"reset"), 1,'first');
% 
%     Vset=[]; Iset=[]; Vreset=[]; Ireset=[];
%     if ~isempty(iSet),   Vset=blocks(iSet).V;   Iset=blocks(iSet).I; end
%     if ~isempty(iReset), Vreset=blocks(iReset).V; Ireset=blocks(iReset).I; end
% end
function [Vset, Iset, Vreset, Ireset] = get_set_reset_blocks(filePath)
% Robust: choose SET/RESET blocks by voltage polarity/range (not titles)

    blocks = read_b1500_blocks(filePath);

    Vset=[]; Iset=[]; Vreset=[]; Ireset=[];
    if isempty(blocks), return; end

    % Compute max positive and min negative per block
    maxPos = -inf(numel(blocks),1);
    minNeg = +inf(numel(blocks),1);

    for i = 1:numel(blocks)
        V = blocks(i).V;
        if isempty(V), continue; end
        maxPos(i) = max(V);
        minNeg(i) = min(V);
    end

    % SET = block with largest positive swing
    [~, iSet] = max(maxPos);
    if isfinite(maxPos(iSet)) && maxPos(iSet) > 0.1
        Vset = blocks(iSet).V;
        Iset = blocks(iSet).I;
    end

    % RESET = block with most negative swing
    [~, iReset] = min(minNeg);
    if isfinite(minNeg(iReset)) && minNeg(iReset) < -0.1
        Vreset = blocks(iReset).V;
        Ireset = blocks(iReset).I;
    end
end

function [maxVset, maxVreset] = scan_max_ranges(files)
% maxVset: max positive V in SET block
% maxVreset: max |negative V| in RESET block
    maxVset = 0; maxVreset = 0;
    for k = 1:numel(files)
        [Vs, ~, Vr, ~] = get_set_reset_blocks(files(k));
        if ~isempty(Vs), maxVset   = max(maxVset,   max(Vs)); end
        if ~isempty(Vr), maxVreset = max(maxVreset, max(abs(Vr))); end
    end
    if maxVset <= 0,   maxVset = 1.5; end
    if maxVreset <= 0, maxVreset = 2.5; end
end

% =====================================================================
% ========================= SWEEP EXTRACTION ===========================
% =====================================================================

function [Vup, Iup] = extract_0_to_Vmax_sweep(V, I)
% + up-sweep: last near-zero before max(V) -> max(V)
    [~, idxVmax] = max(V);
    z = find(abs(V) < 1e-12 & (1:numel(V))' < idxVmax);
    if isempty(z), s = 1; else, s = z(end); end
    Vup = V(s:idxVmax);
    Iup = I(s:idxVmax);
end

function [Vdown, Idown] = extract_Vmax_to_0_sweep(V, I)
% + down-sweep: max(V) -> first near-zero after that
    [~, idxVmax] = max(V);
    z = find(abs(V) < 1e-12 & (1:numel(V))' > idxVmax, 1,'first');
    if isempty(z), e = numel(V); else, e = z; end
    Vdown = V(idxVmax:e);
    Idown = I(idxVmax:e);
end

function [Vneg, Ineg] = extract_0_to_Vmin_sweep(V, I)
% - sweep: last near-zero before min(V) -> min(V)
    [~, idxVmin] = min(V);
    z = find(abs(V) < 1e-12 & (1:numel(V))' < idxVmin);
    if isempty(z), s = 1; else, s = z(end); end
    Vneg = V(s:idxVmin);
    Ineg = I(s:idxVmin);
end

function Vset = detect_Vset(V, I)
% SET event ~ max slope in log|I| vs V
    m = V > 0.05;
    Vp = V(m); Ip = abs(I(m)) + 1e-18;
    if numel(Vp) < 6, Vset = nan; return; end
    dlog = diff(log10(Ip)) ./ diff(Vp);
    [~,k] = max(dlog);
    Vset = Vp(min(k+1, numel(Vp)));
end

function Vreset_mag = detect_Vreset_mag(Vmag, Imag)
% RESET event ~ most negative slope in log|I| vs |V| (current drop)
    m = Vmag > 0.05;
    Vp = Vmag(m); Ip = Imag(m);
    if numel(Vp) < 6, Vreset_mag = nan; return; end
    dlog = diff(log10(Ip)) ./ diff(Vp);
    [~,k] = min(dlog);
    Vreset_mag = Vp(min(k+1, numel(Vp)));
end

% =====================================================================
% ========================= MAP BUILDERS ===============================
% =====================================================================

function [mechMap, nPerBin] = build_set_hrs_map(files, edges, minPtsPerBin)
% HRS pre-SET: + up-sweep, V in [edge1 .. Vset-margin]
    nC = numel(files);
    nB = numel(edges)-1;
    mechMap = zeros(nC,nB);

    for c = 1:nC
        [V,I,~,~] = get_set_reset_blocks(files(c));
        if numel(V) < 12, continue; end

        [Vup, Iup] = extract_0_to_Vmax_sweep(V,I);
        if numel(Vup) < 12, continue; end

        Vset = detect_Vset(Vup, Iup);
        if isnan(Vset), continue; end

        margin = 0.03;
        mask = (Vup >= edges(1)) & (Vup <= (Vset - margin));
        Vhrs = Vup(mask);
        Ihrs = abs(Iup(mask)) + 1e-18;

        for b = 1:nB
            lo = edges(b); hi = edges(b+1);
            w = (Vhrs >= lo) & (Vhrs < hi);
            if nnz(w) < minPtsPerBin, continue; end
            mechMap(c,b) = classify_mechanism(Vhrs(w), Ihrs(w));
        end
    end
    nPerBin = sum(mechMap>0,1);
end

function [mechMap, nPerBin] = build_set_lrs_map(files, edges, minPtsPerBin)
% LRS post-SET: + down-sweep, V >= edges(1)
    nC = numel(files);
    nB = numel(edges)-1;
    mechMap = zeros(nC,nB);

    for c = 1:nC
        [V,I,~,~] = get_set_reset_blocks(files(c));
        if numel(V) < 12, continue; end

        [Vdown, Idown] = extract_Vmax_to_0_sweep(V,I);
        if isempty(Vdown), continue; end

        mask = (Vdown >= edges(1));
        Vuse = Vdown(mask);
        Iuse = abs(Idown(mask)) + 1e-18;

        for b = 1:nB
            lo = edges(b); hi = edges(b+1);
            w = (Vuse >= lo) & (Vuse < hi);
            if nnz(w) < minPtsPerBin, continue; end
            mechMap(c,b) = classify_mechanism(Vuse(w), Iuse(w));
        end
    end
    nPerBin = sum(mechMap>0,1);
end

function [mechMap, nPerBin] = build_reset_map(files, edges, mode, minPtsPerBin)
% mode="pre":  pre-RESET LRS on negative sweep (|V| < Vreset)
% mode="post": post-RESET HRS after rupture      (|V| > Vreset)
    nC = numel(files);
    nB = numel(edges)-1;
    mechMap = zeros(nC,nB);

    for c = 1:nC
        [~,~,V,I] = get_set_reset_blocks(files(c));
        if numel(V) < 12, continue; end

        [Vneg, Ineg] = extract_0_to_Vmin_sweep(V,I);
        if numel(Vneg) < 12, continue; end

        Vmag = abs(Vneg(:));
        Imag = abs(Ineg(:)) + 1e-18;

        Vreset_mag = detect_Vreset_mag(Vmag, Imag);
        if isnan(Vreset_mag), continue; end

        margin = 0.05;

        if mode == "pre"
            mask = (Vmag >= edges(1)) & (Vmag <= (Vreset_mag - margin));
        else
            mask = (Vmag >= (Vreset_mag + margin)) & (Vmag <= edges(end));
        end

        Vuse = Vmag(mask);
        Iuse = Imag(mask);

        for b = 1:nB
            lo = edges(b); hi = edges(b+1);
            w = (Vuse >= lo) & (Vuse < hi);
            if nnz(w) < minPtsPerBin, continue; end
            mechMap(c,b) = classify_mechanism(Vuse(w), Iuse(w));
        end
    end

    nPerBin = sum(mechMap>0,1);
end

% =====================================================================
% ========================= MECH CLASSIFICATION ========================
% =====================================================================

function best = classify_mechanism(V, I)
% Returns:
%  1=Ohmic, 2=Schottky, 3=Poole-Frenkel, 4=Fowler-Nordheim
    V = V(:); I = abs(I(:)) + 1e-18;
    m = (V > 0);
    V = V(m); I = I(m);
    if numel(V) < 6, best = 0; return; end

    r2_ohm = lin_r2(V, I);                          % I vs V
    r2_sch = lin_r2(sqrt(V), log(I));               % ln(I) vs sqrt(V)
    r2_pf  = lin_r2(sqrt(V), log(I ./ V));          % ln(I/V) vs sqrt(V)
    r2_fn  = lin_r2(1./V, log(I ./ (V.^2)));        % ln(I/V^2) vs 1/V

    [~, best] = max([r2_ohm, r2_sch, r2_pf, r2_fn]); % 1..4
end

function r2 = lin_r2(x, y)
    x = x(:); y = y(:);
    A = [x, ones(size(x))];
    coef = A \ y;
    yhat = A * coef;
    ss_res = sum((y - yhat).^2);
    ss_tot = sum((y - mean(y)).^2);
    if ss_tot == 0, r2 = -Inf; else, r2 = 1 - ss_res/ss_tot; end
end

function P = mech_probabilities(mechMap, nMech)
% P(bin, mech) = fraction of cycles with that dominant mech
    nB = size(mechMap,2);
    P = zeros(nB, nMech);
    for b = 1:nB
        v = mechMap(:,b);
        v = v(v > 0);
        if isempty(v), continue; end
        for k = 1:nMech
            P(b,k) = mean(v == k);
        end
    end
end

function stacked_prob_plot(P, nPerBin, binLabels)
    bar(P,'stacked');
    ylim([0 1]);
    xticks(1:size(P,1));
    xticklabels(binLabels);
    xtickangle(25);
    grid on;

    for b = 1:size(P,1)
        text(b, 1.02, sprintf("n=%d", nPerBin(b)), ...
            'HorizontalAlignment','center','FontSize',9);
    end
end

% =====================================================================
% ========================= BIN HELPERS ================================
% =====================================================================

function edgesOut = clip_edges(edgesIn, vmax)
% keeps edges <= vmax, and snaps/extends last edge to vmax
    edgesIn = edgesIn(:)';
    edgesOut = edgesIn(edgesIn <= vmax + 1e-12);

    if numel(edgesOut) < 2
        edgesOut = [0 vmax];
    end

    % if vmax > edgesOut(end) + 0.05
    %     edgesOut(end+1) = vmax;
    % else
    edgesOut(end) = min(edgesOut(end), vmax);
    % end

    edgesOut = unique(edgesOut,'stable');
end

function labels = make_bin_labels(edges)
    labels = arrayfun(@(a,b) sprintf('%.3g–%.3g V', a, b), ...
        edges(1:end-1), edges(2:end), 'UniformOutput', false);
end