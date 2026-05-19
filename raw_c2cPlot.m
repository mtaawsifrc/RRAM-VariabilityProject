clc; clear; close all;

% ============================
% USER SETTINGS
% ============================
folderPath = '/home/hm5701/Documents/PINN/Variability_Project/DC endurance-DOE/S1/S1-set-reset/'; % <-- change
[~, foldername] = fileparts(folderPath);
baseColor = [0.60 0.00 0.00];   % darkest = dark red (last cycle)
% baseColor = [0.00 0.00 0.70];   % darkest = blue (last cycle)
% baseColor = [0.30 0.30 0.30];   % darkest = grey (last cycle)
% baseColor = [0.00 0.60 0.00]; % Green
% baseColor = [0.1 0.6 0.3]; % muted nature green
useAbsI   = true;              % plot |I| (typical butterfly)
wantLegend = false;

% OPTIONAL (recommended): set a log-safe floor instead of dropping zeros
useFloorInsteadOfNaN = false;
I_floor = 1e-12;  % used only if useFloorInsteadOfNaN=true

% ============================
% LIST FILES
% ============================
fileList = dir(fullfile(folderPath, '*.csv'));
N = numel(fileList);
if N == 0
    error('No CSV files found in: %s', folderPath);
end

% ============================
% PARSE ALL FILES
% ============================
allFiles(N) = struct('path',"",'name',"",'t',NaT,'blocks',[]);
for k = 1:N
    fp = fullfile(folderPath, fileList(k).name);
    [t, blocks] = parseB1500_SetResetCSV(fp);

    % Fallback if timestamp missing
    if isnat(t)
        t = datetime(fileList(k).datenum, 'ConvertFrom','datenum');
    end

    allFiles(k).path   = string(fp);
    allFiles(k).name   = string(fileList(k).name);
    allFiles(k).t      = t;
    allFiles(k).blocks = blocks;
end

% ============================
% SORT BY TIMESTAMP (EARLY->LATE)
% ============================
[~, idx] = sort([allFiles.t]);
allFiles = allFiles(idx);

% ============================
% PLOT
% ============================
figure('Color','w'); hold on;

for i = 1:N
    % Color ramp: lightest (near white) -> darkest (baseColor)
    tt = (i-1) / max(N-1, 1);                  % 0..1
    c  = (1-tt)*[1 1 1] + tt*baseColor;         % blend with white

    % Visual emphasis
    if i == 1
        lw = 1.0;  a = 0.75;
    elseif i == N
        lw = 2.2;  a = 1.00;
    else
        lw = 0.8;  a = 0.35;
    end

    blocks = allFiles(i).blocks;
    for b = 1:numel(blocks)
        V = blocks(b).V;
        I = blocks(b).I;
        if isempty(V) || isempty(I), continue; end

        % ====== KEY FIXES FOR BUTTERFLY LOG PLOT ======
        if useAbsI
            I = abs(I);
        end

        % Remove invalid values for log plotting (I must be > 0)
        bad = (~isfinite(I)) | (I <= 0);
        if useFloorInsteadOfNaN
            I(bad) = I_floor;      % clamp to a small positive current
        else
            I(bad) = NaN;          % drop them (recommended)
        end
        % =============================================

        semilogy(V, I, 'LineWidth', lw, 'Color', [c a]);
    end
end

% Force log axis (in case anything overrides)
set(gca,'YScale','log');
% ax = gca;
xlabel('Voltage (V)');
ylabel('Current (A)');
title(sprintf('Set-Reset I–V (N=%d)', N));
box on;
grid on;
% grid minor off;
if wantLegend
    legend(foldername, 'Location','best','FontWeight','bold','FontSize',18);
end
figfilename = [foldername '.png'];
% exportgraphics(gcf, figfilename, 'Resolution', 300);

% OPTIONAL: set typical RRAM log range (edit if you want)
% ylim([1e-10 1e-2]);
xlim([-5 5]);
% ylim([1e-10 1e-2]);
% ============================
% ======= LOCAL FUNCTIONS =====
% ============================
function [t, blocks] = parseB1500_SetResetCSV(filePath)
% Parses Keysight/B1500-style CSV:
% - timestamp from: "MetaData, TestRecord.RecordTime, ..."
% - blocks separated by: "AnalysisSetup, Analysis.Setup.Title, <name>"
% - I-V points from: "DataValue, V, I"

    txt = fileread(filePath);
    lines = splitlines(string(txt));

    % ---------- timestamp ----------
    t = NaT;
    m = regexp(lines, '^MetaData,\s*TestRecord\.RecordTime,\s*(.*)$', 'tokens', 'once');
    m = m(~cellfun(@isempty,m));
    if ~isempty(m)
        ts = strtrim(string(m{1}));
        try
            t = datetime(ts, 'InputFormat','MM/dd/uuuu HH:mm:ss');
        catch
            try
                t = datetime(ts); % fallback guess
            catch
                t = NaT;
            end
        end
    end

    % ---------- find block starts ----------
    titleTok = regexp(lines, '^AnalysisSetup,\s*Analysis\.Setup\.Title,\s*(.*)$', 'tokens', 'once');
    titleIdx = find(~cellfun(@isempty, titleTok));

    % If no titles exist, still try to parse all DataValue as one block
    if isempty(titleIdx)
        blocks = struct('title',"All",'V',[],'I',[]);
        [V,I] = extractDataValuePairs(lines);
        blocks(1).V = V; blocks(1).I = I;
        return;
    end

    % ---------- build blocks ----------
    blocks = struct('title',{},'V',{},'I',{});
    for bi = 1:numel(titleIdx)
        i0 = titleIdx(bi);
        if bi < numel(titleIdx)
            i1 = titleIdx(bi+1) - 1;
        else
            i1 = numel(lines);
        end

        titleStr = strtrim(string(titleTok{i0}{1}));
        segLines = lines(i0:i1);

        % Only keep segments that actually contain DataValue lines
        if ~any(startsWith(strtrim(segLines), "DataValue,"))
            continue;
        end

        [V,I] = extractDataValuePairs(segLines);

        blk.title = titleStr;
        blk.V = V;
        blk.I = I;
        blocks(end+1) = blk; %#ok<AGROW>
    end
end

function [V,I] = extractDataValuePairs(lines)
% Extracts numeric pairs from lines like:
% "DataValue, -0.02, -5.4864E-07"

    dv = lines(startsWith(strtrim(lines), "DataValue,"));

    V = [];
    I = [];
    if isempty(dv), return; end

    tok = regexp(dv, '^DataValue,\s*([^,]+)\s*,\s*([^,]+)\s*$', 'tokens', 'once');
    tok = tok(~cellfun(@isempty, tok));
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