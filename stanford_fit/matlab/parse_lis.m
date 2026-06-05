function I = parse_lis(lis_path, tquery)
%PARSE_LIS Parse ASCII HSPICE .lis/.mt0 print tables and interpolate current
%   onto the requested transient TIME stamps tquery. Columns are
%   (time, V(TE), I(Vsrc)); mapping by time is robust to adaptive stepping.
    if ~isfile(lis_path)
        I = nan(size(tquery));
        return;
    end

    lines = splitlines(string(fileread(lis_path)));
    rows = [];
    inTable = false;
    for k = 1:numel(lines)
        line = char(lines(k));
        low = lower(line);
        if contains(low, 'time') && (contains(low, 'v(te)') || contains(low, 'i(vsrc)'))
            inTable = true;
            continue;
        end
        if ~inTable
            continue;
        end
        nums = regexp(line, '[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?', 'match');
        if numel(nums) < 3
            if ~isempty(rows)
                break;
            end
            continue;
        end
        vals = [hnum(nums{1}), hnum(nums{2}), hnum(nums{3})];
        if all(isfinite(vals))
            rows(end + 1, :) = vals; %#ok<AGROW>
        end
    end

    if isempty(rows)
        rows = parse_any_numeric_triplets(lines);
    end
    if isempty(rows)
        I = nan(size(tquery));
        return;
    end

    tsim = rows(:, 1);
    Iraw = -rows(:, 3);
    keep = isfinite(tsim) & isfinite(Iraw);
    tsim = tsim(keep);
    Iraw = Iraw(keep);
    [tsim, iu] = unique(tsim, 'stable');
    Iraw = Iraw(iu);
    [tsim, is] = sort(tsim);
    Iraw = Iraw(is);
    if numel(tsim) < 2
        I = nan(size(tquery));
        return;
    end

    I = interp1(tsim, Iraw, tquery(:), 'linear', 'extrap');
    I = reshape(I, size(tquery));
end

function rows = parse_any_numeric_triplets(lines)
    rows = [];
    for k = 1:numel(lines)
        nums = regexp(char(lines(k)), '^\s*([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?)\s+([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?)\s+([-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?)\s*$', 'tokens');
        if isempty(nums)
            continue;
        end
        vals = [hnum(nums{1}{1}), hnum(nums{1}{2}), hnum(nums{1}{3})];
        if all(isfinite(vals))
            rows(end + 1, :) = vals; %#ok<AGROW>
        end
    end
end

function x = hnum(value)
    value = strrep(value, 'D', 'E');
    value = strrep(value, 'd', 'e');
    suffix = value(end);
    scale = 1;
    switch suffix
        case 'f'
            scale = 1e-15; value = value(1:end-1);
        case 'p'
            scale = 1e-12; value = value(1:end-1);
        case 'n'
            scale = 1e-9; value = value(1:end-1);
        case 'u'
            scale = 1e-6; value = value(1:end-1);
        case 'm'
            scale = 1e-3; value = value(1:end-1);
        case {'k', 'K'}
            scale = 1e3; value = value(1:end-1);
        case 'M'
            scale = 1e6; value = value(1:end-1);
        case 'G'
            scale = 1e9; value = value(1:end-1);
    end
    x = str2double(value) * scale;
end
