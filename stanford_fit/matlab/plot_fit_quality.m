function plot_fit_quality(refined, val, setB, resetB, out_png)
%PLOT_FIT_QUALITY Save measured-vs-fit, residual, CI, and LOCO panels.
    fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1200 900]);
    tl = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

    nexttile(tl);
    semilogy(setB.voltage_V, abs(setB.median_current_A), 'k.', 'DisplayName', 'Measured SET');
    hold on;
    semilogy(resetB.voltage_V, abs(resetB.median_current_A), 'b.', 'DisplayName', 'Measured RESET');
    if isfield(val, 'r_set') && any(isfinite(val.r_set))
        semilogy(setB.voltage_V, 10 .^ (setB.median_log10_abs_current + val.r_set), ...
            'r-', 'DisplayName', 'Fit SET');
        semilogy(resetB.voltage_V, 10 .^ (resetB.median_log10_abs_current + val.r_res), ...
            'r--', 'DisplayName', 'Fit RESET');
    end
    xlabel('V (V)');
    ylabel('|I| (A)');
    legend('Location', 'best');
    grid on;
    title('Measured vs fitted I-V');

    nexttile(tl);
    plot(setB.voltage_V, val.r_set, 'k.');
    hold on;
    plot(resetB.voltage_V, val.r_res, 'b.');
    yline(0);
    xlabel('V (V)');
    ylabel('log_{10}|I| residual');
    grid on;
    title(sprintf('Residuals (DW_{SET}=%.2f, DW_{RESET}=%.2f)', val.dw_set, val.dw_res));

    nexttile(tl);
    if isfield(val, 'theta_bs') && ~isempty(val.theta_bs)
        boxplot(val.theta_bs);
        xlabel('parameter index');
        ylabel('value');
        title('Bootstrap posterior');
    else
        text(0.05, 0.5, 'Bootstrap skipped', 'Units', 'normalized');
        axis off;
    end
    grid on;

    nexttile(tl);
    if isfield(val, 'loco_rmse') && ~isempty(val.loco_rmse)
        bar(val.loco_rmse);
        legend({'SET', 'RESET'});
        xlabel('held-out cycle');
        ylabel('RMSE log_{10}|I|');
        title('Leave-one-cycle-out validation');
    else
        text(0.05, 0.5, 'LOCO skipped', 'Units', 'normalized');
        axis off;
    end
    grid on;

    exportgraphics(fig, out_png, 'Resolution', 300);
    close(fig);
end

