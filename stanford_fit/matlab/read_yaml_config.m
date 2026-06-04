function cfg = read_yaml_config(path)
%READ_YAML_CONFIG Minimal flat YAML reader for TaO-Fit config files.
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

