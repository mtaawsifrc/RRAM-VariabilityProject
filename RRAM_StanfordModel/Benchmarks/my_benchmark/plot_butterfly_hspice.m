clear; clc; close all;

filename = "butterfly_array.log";   % change if your log name is different

txt = fileread(filename);
lines = splitlines(txt);

time = [];
V = [];
Ivin = [];

numPattern = '^\s*([+-]?\d*\.?\d+(?:[eEdD][+-]?\d+)?[fpnumkKMG]?)\s+([+-]?\d*\.?\d+(?:[eEdD][+-]?\d+)?[fpnumkKMG]?)\s+([+-]?\d*\.?\d+(?:[eEdD][+-]?\d+)?[fpnumkKMG]?)\s*$';

for k = 1:numel(lines)
    tok = regexp(lines{k}, numPattern, 'tokens', 'once');

    if ~isempty(tok)
        time(end+1,1) = hspiceNum(tok{1});
        V(end+1,1)    = hspiceNum(tok{2});
        Ivin(end+1,1) = hspiceNum(tok{3});
    end
end

fprintf("Read %d transient data points\n", numel(time));

% HSPICE source current convention: use -I(Vin) as device current
Idev = -Ivin;

% Remove duplicate or invalid entries if any
valid = isfinite(time) & isfinite(V) & isfinite(Idev);
time = time(valid);
V = V(valid);
Idev = Idev(valid);

%% Voltage vs time
figure;
plot(time*1e3, V, 'LineWidth', 1.5);
grid on;
xlabel('Time (ms)');
ylabel('Voltage V(in) (V)');
title('Applied Bipolar Voltage Sweep');

%% Current vs time
figure;
plot(time*1e3, Idev, 'LineWidth', 1.5);
grid on;
xlabel('Time (ms)');
ylabel('Device Current -I(Vin) (A)');
title('RRAM Current vs Time');

%% Butterfly I-V curve, linear scale
figure;
plot(V, Idev, 'LineWidth', 1.5);
grid on;
xlabel('Voltage V(in) (V)');
ylabel('Device Current -I(Vin) (A)');
title('RRAM Bipolar Butterfly I-V Curve');

%% Butterfly I-V curve, semilog absolute current
figure;
semilogy(V, abs(Idev), 'LineWidth', 1.5,'Color','r');
grid on;
xlabel('Voltage V(in) (V)');
ylabel('|Device Current| (A)');
title('RRAM Bipolar Butterfly I-V Curve (Semilog)');

%% Optional: export parsed data
T = table(time, V, Idev, 'VariableNames', {'Time_s','Voltage_V','Current_A'});
writetable(T, 'BUTTERFLY_parsed.csv');

fprintf("Saved parsed data to BUTTERFLY_parsed.csv\n");

function val = hspiceNum(s)
    s = strtrim(strrep(s, 'D', 'E'));

    suffix = regexp(s, '[fpnumkKMG]$', 'match', 'once');

    if isempty(suffix)
        scale = 1;
        numstr = s;
    else
        numstr = extractBefore(s, strlength(s));
        switch suffix
            case 'f'
                scale = 1e-15;
            case 'p'
                scale = 1e-12;
            case 'n'
                scale = 1e-9;
            case 'u'
                scale = 1e-6;
            case 'm'
                scale = 1e-3;
            case {'k','K'}
                scale = 1e3;
            case 'M'
                scale = 1e6;
            case 'G'
                scale = 1e9;
            otherwise
                scale = 1;
        end
    end

    val = str2double(numstr) * scale;
end