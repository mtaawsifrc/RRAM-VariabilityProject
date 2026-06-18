#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


HSPICE_NUM_RE = re.compile(
    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?"
)
HSPICE_NUM_LINE_RE = re.compile(
    rf"^\s*({HSPICE_NUM_RE.pattern})\s+"
    rf"({HSPICE_NUM_RE.pattern})\s+"
    rf"({HSPICE_NUM_RE.pattern})\s*$"
)

HSPICE_SUFFIX_SCALE = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}


def hnum(x):
    return f"{x:.8e}"


def hspice_num(value):
    value = value.strip().replace("D", "E").replace("d", "e")
    suffix = value[-1] if value else ""
    if suffix in HSPICE_SUFFIX_SCALE:
        return float(value[:-1]) * HSPICE_SUFFIX_SCALE[suffix]
    return float(value)


def model_parameter_rows(args):
    rows = [
        ("deck_mode", args.deck_mode),
        ("model_switch", 1 if args.deck_mode == "butterfly" else 0),
        ("set_vmax", args.set_vmax),
        ("reset_vmin", args.reset_vmin),
        ("gap_ini", args.gap_max if args.deck_mode == "butterfly" else np.nan),
        ("gap_min", args.gap_min),
        ("gap_max", args.gap_max),
        ("g0", args.g0),
        ("V0", args.V0),
        ("Vel0", args.Vel0),
        ("I0", args.I0),
        ("beta", args.beta),
        ("gamma0", args.gamma0),
        ("Rth", args.Rth),
        ("tox", args.tox),
        ("deltaGap0", args.deltaGap0),
        ("set_compliance_current", args.set_compliance_current),
        ("auto_set_compliance_current", args.auto_set_compliance_current),
        ("tstep", args.tstep),
        ("butterfly_set_time", args.butterfly_set_time),
        ("butterfly_zero_after_set_time", args.butterfly_zero_after_set_time),
        ("butterfly_reset_time", args.butterfly_reset_time),
        ("butterfly_final_time", args.butterfly_final_time),
        ("butterfly_tstop", args.butterfly_tstop),
    ]
    return pd.DataFrame(rows, columns=["parameter", "value"])


def make_deck(branch, va_path, out_dir, args):
    if branch == "SET":
        vfinal = args.set_vmax
        gap_ini = args.gap_max
        title = "Stanford RRAM SET baseline"
    else:
        vfinal = args.reset_vmin
        gap_ini = args.gap_min
        title = "Stanford RRAM RESET baseline"

    deck = f"""\
{title}

.OPTION POST=2
.OPTION RUNLVL=5
.OPTION INGOLD=2 MEASFORM=3

.hdl "{va_path}"

X1 in 0 rram_v_1_0_0 model_switch=0 gap_ini={hnum(gap_ini)} gap_min={hnum(args.gap_min)} gap_max={hnum(args.gap_max)} g0={hnum(args.g0)} V0={hnum(args.V0)} Vel0={hnum(args.Vel0)} I0={hnum(args.I0)} beta={hnum(args.beta)} gamma0={hnum(args.gamma0)} Rth={hnum(args.Rth)} tox={hnum(args.tox)} deltaGap0={hnum(args.deltaGap0)}

Vin in 0 PULSE(0 {hnum(vfinal)} 1u {args.ramp_time} 1u {args.hold_time} {args.period})

.tran {args.tstep} {args.tstop} START=0

.probe V(in) I(Vin)
.print tran V(in) I(Vin)

.end
"""

    path = out_dir / f"{branch.lower()}_baseline.sp"
    path.write_text(deck)
    return path


def make_butterfly_deck(va_path, out_dir, args):
    title = "Stanford RRAM bipolar butterfly baseline"
    deck = f"""\
{title}

.OPTION POST=2
.OPTION RUNLVL=5
.OPTION INGOLD=2 MEASFORM=3

.hdl "{va_path}"

X1 in 0 rram_v_1_0_0 gap_ini={hnum(args.gap_max)} model_switch=1 deltaGap0={hnum(args.deltaGap0)} g0={hnum(args.g0)} V0={hnum(args.V0)} Vel0={hnum(args.Vel0)} I0={hnum(args.I0)} beta={hnum(args.beta)} gamma0={hnum(args.gamma0)} gap_min={hnum(args.gap_min)} gap_max={hnum(args.gap_max)} Rth={hnum(args.Rth)} tox={hnum(args.tox)}

Vin in 0 PWL(0 0 {args.butterfly_set_time} {hnum(args.set_vmax)} {args.butterfly_zero_after_set_time} 0 {args.butterfly_reset_time} {hnum(args.reset_vmin)} {args.butterfly_final_time} 0)

.tran {args.tstep} {args.butterfly_tstop}

.probe V(in) I(Vin)
.print tran V(in) I(Vin)

.end
"""

    path = out_dir / "butterfly_baseline.sp"
    path.write_text(deck)
    return path


def run_hspice(deck_path, hspice_cmd):
    cmd = [hspice_cmd, str(deck_path.name)]
    result = subprocess.run(
        cmd,
        cwd=deck_path.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    log_path = deck_path.with_suffix(".runlog")
    log_path.write_text(result.stdout)

    return result.returncode, log_path


def parse_hspice_lis(lis_path):
    text = lis_path.read_text(errors="replace").splitlines()

    rows = []
    in_table = False

    for line in text:
        low = line.lower()

        if "time" in low and ("v(in)" in low or "i(vin)" in low):
            in_table = True
            continue

        if not in_table:
            continue

        match = HSPICE_NUM_LINE_RE.match(line)
        if not match:
            if rows:
                break
            continue

        try:
            rows.append([hspice_num(value) for value in match.groups()])
        except ValueError:
            pass

    if len(rows) == 0:
        rows = parse_numeric_triplets(text)

    if len(rows) == 0:
        return pd.DataFrame(columns=["time_s", "voltage_V", "current_A", "abs_current_A"])

    df = pd.DataFrame(rows, columns=["time_s", "voltage_V", "current_A"])
    df = apply_hspice_current_convention(df)
    df = df.drop_duplicates(subset=["time_s", "voltage_V"])
    return df


def fallback_parse_stdout(runlog_path):
    text = runlog_path.read_text(errors="replace").splitlines()

    rows = []
    in_table = False

    for line in text:
        low = line.lower()

        if "time" in low and ("v(in)" in low or "i(vin)" in low):
            in_table = True
            continue

        if not in_table:
            continue

        match = HSPICE_NUM_LINE_RE.match(line)
        if not match:
            continue

        try:
            rows.append([hspice_num(value) for value in match.groups()])
        except ValueError:
            pass

    if len(rows) == 0:
        rows = parse_numeric_triplets(text)

    if len(rows) == 0:
        return pd.DataFrame(columns=["time_s", "voltage_V", "current_A", "abs_current_A"])

    df = pd.DataFrame(rows, columns=["time_s", "voltage_V", "current_A"])
    df = apply_hspice_current_convention(df)
    return df


def apply_hspice_current_convention(df):
    df = df.copy()
    df["current_A"] = -pd.to_numeric(df["current_A"], errors="coerce")
    df["abs_current_A"] = np.abs(df["current_A"])
    return df


def parse_numeric_triplets(lines):
    rows = []
    for line in lines:
        match = HSPICE_NUM_LINE_RE.match(line)
        if not match:
            continue
        try:
            rows.append([hspice_num(value) for value in match.groups()])
        except ValueError:
            pass
    return rows


def require_hspice_success(branch, code, runlog):
    if code == 0:
        return

    tail = "\n".join(runlog.read_text(errors="replace").splitlines()[-30:])
    raise RuntimeError(
        f"{branch}: HSPICE failed with return_code={code}. "
        f"See run log: {runlog}\n\nLast run-log lines:\n{tail}"
    )


def require_sim_points(branch, sim, lis_path, runlog):
    required = ["time_s", "voltage_V", "current_A", "abs_current_A"]
    missing = [name for name in required if name not in sim.columns]
    if missing:
        raise RuntimeError(f"{branch}: parsed simulation data is missing columns: {missing}")

    sim = sim.copy()
    for column in required:
        sim[column] = pd.to_numeric(sim[column], errors="coerce")

    sim = sim.replace([np.inf, -np.inf], np.nan)
    sim = sim.dropna(subset=["time_s", "voltage_V", "current_A", "abs_current_A"])
    sim = sim[sim["abs_current_A"] > 0]

    if sim.empty:
        sources = []
        if lis_path.exists():
            sources.append(str(lis_path))
        sources.append(str(runlog))
        raise RuntimeError(
            f"{branch}: HSPICE completed but no numeric simulation points were parsed. "
            "The run may have produced only binary .tr0 output instead of an ASCII table. "
            f"Checked: {', '.join(sources)}"
        )

    return sim


def remove_stale_outputs(output_dir):
    names = [
        "03_set_sim.csv",
        "03_reset_sim.csv",
        "03_butterfly_sim.csv",
        "03_all_sim.csv",
        "03_exp_vs_baseline_comparison.csv",
        "03_baseline_overlay.png",
        "03_baseline_overlay_linear.png",
        "03_fit_parameters.csv",
        "03_fit_metrics.csv",
        "03_read_ratio_summary.csv",
    ]
    for name in names:
        path = output_dir / name
        if path.exists():
            path.unlink()


def filter_rep(rep, args):
    out = []

    set_df = rep[
        (rep["branch"] == "SET")
        & (rep["voltage_V"] >= args.set_vmin)
        & (rep["voltage_V"] <= args.set_vmax)
    ].copy()

    reset_df = rep[
        (rep["branch"] == "RESET")
        & (rep["voltage_V"] >= args.reset_vmin)
        & (rep["voltage_V"] <= args.reset_vmax)
    ].copy()

    if len(set_df):
        out.append(set_df)

    if len(reset_df):
        out.append(reset_df)

    return pd.concat(out, ignore_index=True)


def apply_rep_voltage_limits(rep, args):
    positive = pd.to_numeric(rep.loc[rep["voltage_V"] > 0, "voltage_V"], errors="coerce")
    negative = pd.to_numeric(rep.loc[rep["voltage_V"] < 0, "voltage_V"], errors="coerce")

    if len(positive.dropna()):
        args.set_vmax = float(positive.max())
    if len(negative.dropna()):
        args.reset_vmin = float(negative.min())


def label_butterfly_branches(sim):
    sim = sim.sort_values("time_s").copy()
    sim["branch"] = np.where(sim["voltage_V"] >= 0, "SET", "RESET")
    sim["butterfly_sequence_index"] = np.arange(1, len(sim) + 1)
    return sim


def estimate_set_compliance_current(exp_fit):
    exp = exp_fit.copy()
    exp["voltage_V"] = pd.to_numeric(exp["voltage_V"], errors="coerce")
    exp["median_abs_current_A"] = pd.to_numeric(
        exp["median_abs_current_A"], errors="coerce"
    )

    set_exp = exp[
        exp["branch"].astype(str).eq("SET")
        & np.isfinite(exp["voltage_V"])
        & np.isfinite(exp["median_abs_current_A"])
        & (exp["voltage_V"] > 0)
        & (exp["median_abs_current_A"] > 0)
    ]
    if set_exp.empty:
        return np.nan

    vmax = set_exp["voltage_V"].max()
    tail = set_exp[set_exp["voltage_V"] >= 0.8 * vmax]
    if tail.empty:
        tail = set_exp.nlargest(max(3, len(set_exp) // 10), "voltage_V")

    return float(tail["median_abs_current_A"].median())


def apply_set_compliance(sim, compliance_current):
    if compliance_current is None or not np.isfinite(compliance_current):
        return sim
    if compliance_current <= 0:
        return sim

    sim = sim.copy()
    if "unclamped_current_A" not in sim.columns:
        sim["unclamped_current_A"] = sim["current_A"]
        sim["unclamped_abs_current_A"] = sim["abs_current_A"]

    mask = (sim["voltage_V"] >= 0) & (sim["abs_current_A"] > compliance_current)
    signs = np.sign(sim.loc[mask, "current_A"].to_numpy(float))
    signs[signs == 0] = 1.0

    sim["set_compliance_current_A"] = compliance_current
    sim["set_compliance_applied"] = False
    sim.loc[mask, "current_A"] = signs * compliance_current
    sim.loc[mask, "abs_current_A"] = compliance_current
    sim.loc[mask, "set_compliance_applied"] = True
    return sim


def resolve_set_compliance_current(args, exp_fit):
    if args.set_compliance_current is not None:
        return args.set_compliance_current
    if args.auto_set_compliance_current:
        return estimate_set_compliance_current(exp_fit)
    return None


def interpolate_sim_to_exp(sim, exp_branch):
    sim = sim.copy()
    exp_branch = exp_branch.copy()

    sim = sim[np.isfinite(sim["voltage_V"]) & np.isfinite(sim["abs_current_A"])]
    sim = sim[sim["abs_current_A"] > 0]

    if len(sim) < 5:
        exp_branch["sim_abs_current_A"] = np.nan
        exp_branch["sim_log10_abs_current"] = np.nan
        exp_branch["log_error"] = np.nan
        return exp_branch

    sim = sim.sort_values("voltage_V")
    v = sim["voltage_V"].to_numpy(float)
    logi = np.log10(sim["abs_current_A"].to_numpy(float))

    unique_v, inv = np.unique(v, return_inverse=True)
    unique_logi = np.zeros_like(unique_v)

    for k in range(len(unique_v)):
        unique_logi[k] = np.median(logi[inv == k])

    exp_v = exp_branch["voltage_V"].to_numpy(float)
    sim_log = np.interp(exp_v, unique_v, unique_logi, left=np.nan, right=np.nan)

    exp_branch["sim_log10_abs_current"] = sim_log
    exp_branch["sim_abs_current_A"] = 10 ** sim_log
    exp_branch["log_error"] = (
        exp_branch["median_log10_abs_current"] - exp_branch["sim_log10_abs_current"]
    )

    return exp_branch


def interpolate_butterfly_sim_to_exp(sim, exp_fit):
    sim = sim.sort_values("time_s").copy()
    exp = exp_fit.sort_values("butterfly_sequence_index").copy()

    sim = sim[np.isfinite(sim["abs_current_A"])]
    sim = sim[sim["abs_current_A"] > 0]

    if len(sim) < 5 or len(exp) < 5:
        exp["sim_abs_current_A"] = np.nan
        exp["sim_log10_abs_current"] = np.nan
        exp["log_error"] = np.nan
        return exp

    sim_x = np.linspace(0.0, 1.0, len(sim))
    exp_x = np.linspace(0.0, 1.0, len(exp))
    sim_log = np.log10(sim["abs_current_A"].to_numpy(float))

    exp["sim_log10_abs_current"] = np.interp(exp_x, sim_x, sim_log)
    exp["sim_abs_current_A"] = 10 ** exp["sim_log10_abs_current"]
    exp["log_error"] = (
        exp["median_log10_abs_current"] - exp["sim_log10_abs_current"]
    )
    return exp


def split_butterfly_sweeps(df):
    df = df.copy()
    if "butterfly_sequence_index" in df.columns:
        df = df.sort_values("butterfly_sequence_index")
    elif "time_s" in df.columns:
        df = df.sort_values("time_s")
    df = df.reset_index(drop=True)
    if len(df) < 5:
        return {}

    vmax_idx = int(df["voltage_V"].idxmax())
    vmin_idx = int(df["voltage_V"].idxmin())
    if vmax_idx >= vmin_idx:
        return {}

    after_max = df.iloc[vmax_idx:vmin_idx + 1]
    zero_candidates = after_max.index[after_max["voltage_V"] <= 0]
    if len(zero_candidates) == 0:
        zero_after_set_idx = vmin_idx
    else:
        zero_after_set_idx = int(zero_candidates[0])

    return {
        "SET_HRS_PRE": df.iloc[:vmax_idx + 1].copy(),
        "SET_LRS_POST": df.iloc[vmax_idx:zero_after_set_idx + 1].copy(),
        "RESET_LRS_PRE": df.iloc[zero_after_set_idx:vmin_idx + 1].copy(),
        "RESET_HRS_POST": df.iloc[vmin_idx:].copy(),
    }


def interpolate_abs_current(segment, voltage):
    if len(segment) < 2:
        return np.nan

    v = pd.to_numeric(segment["voltage_V"], errors="coerce").to_numpy(float)
    i = pd.to_numeric(segment["abs_current_A"], errors="coerce").to_numpy(float)
    keep = np.isfinite(v) & np.isfinite(i) & (i > 0)
    v = v[keep]
    i = i[keep]
    if len(v) < 2:
        return np.nan

    order = np.argsort(v)
    v = v[order]
    i = i[order]
    unique_v, inv = np.unique(v, return_inverse=True)
    unique_i = np.zeros_like(unique_v)
    for idx in range(len(unique_v)):
        unique_i[idx] = np.median(i[inv == idx])

    if voltage < unique_v.min() or voltage > unique_v.max():
        return np.nan

    return float(10 ** np.interp(voltage, unique_v, np.log10(unique_i)))


def butterfly_read_currents(df, source, read_voltage):
    sweeps = split_butterfly_sweeps(df)
    targets = {
        "SET_HRS_PRE": abs(read_voltage),
        "SET_LRS_POST": abs(read_voltage),
        "RESET_LRS_PRE": -abs(read_voltage),
        "RESET_HRS_POST": -abs(read_voltage),
    }

    rows = []
    for state, voltage in targets.items():
        current = interpolate_abs_current(sweeps.get(state, pd.DataFrame()), voltage)
        rows.append(
            {
                "source": source,
                "state": state,
                "read_voltage_V": voltage,
                "abs_current_A": current,
            }
        )

    lookup = {row["state"]: row["abs_current_A"] for row in rows}
    ratio_specs = [
        ("SET_LRS_to_HRS", "SET_LRS_POST", "SET_HRS_PRE"),
        ("RESET_LRS_to_HRS", "RESET_LRS_PRE", "RESET_HRS_POST"),
    ]
    for ratio_name, numerator_state, denominator_state in ratio_specs:
        numerator = lookup.get(numerator_state, np.nan)
        denominator = lookup.get(denominator_state, np.nan)
        ratio = numerator / denominator if denominator and np.isfinite(denominator) else np.nan
        rows.append(
            {
                "source": source,
                "state": ratio_name,
                "read_voltage_V": abs(read_voltage),
                "abs_current_A": ratio,
            }
        )

    return rows


def experiment_butterfly_for_metrics(exp_fit):
    exp = exp_fit.sort_values("butterfly_sequence_index").copy()
    exp["current_A"] = signed_experiment_current(exp)
    exp["abs_current_A"] = np.abs(exp["current_A"])
    return exp


def fit_metric_rows(comparison):
    valid = comparison["log_error"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) == 0:
        return pd.DataFrame(
            [{"metric": "valid_log_error_points", "value": 0}]
        )

    rows = [
        ("valid_log_error_points", len(valid)),
        ("log10_mae_decades", float(np.mean(np.abs(valid)))),
        ("log10_rmse_decades", float(np.sqrt(np.mean(valid**2)))),
        ("log10_median_error_decades", float(np.median(valid))),
        ("log10_mean_error_decades", float(np.mean(valid))),
        ("log10_p90_abs_error_decades", float(np.percentile(np.abs(valid), 90))),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def save_and_print_fit_report(args, output_dir, comparison, exp_fit, sim_all):
    params = model_parameter_rows(args)
    params_path = output_dir / "03_fit_parameters.csv"
    params.to_csv(params_path, index=False)

    metrics = fit_metric_rows(comparison)
    metrics_path = output_dir / "03_fit_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    ratio_rows = []
    if "butterfly_sequence_index" in exp_fit.columns:
        exp_butterfly = experiment_butterfly_for_metrics(exp_fit)
        ratio_rows.extend(butterfly_read_currents(exp_butterfly, "experiment", args.read_voltage))
        ratio_rows.extend(butterfly_read_currents(sim_all, "simulation", args.read_voltage))

    ratio_df = pd.DataFrame(ratio_rows)
    ratio_path = output_dir / "03_read_ratio_summary.csv"
    if len(ratio_df):
        ratio_df.to_csv(ratio_path, index=False)

    print("\nFit/model parameters used:")
    for _, row in params.iterrows():
        print(f"  {row['parameter']} = {row['value']}")

    print("\nFit metrics:")
    for _, row in metrics.iterrows():
        print(f"  {row['metric']} = {row['value']}")

    if len(ratio_df):
        print(f"\nRead-current summary at |Vread|={args.read_voltage:g} V:")
        for _, row in ratio_df.iterrows():
            value = row["abs_current_A"]
            if pd.isna(value):
                value_str = "nan"
            else:
                value_str = f"{value:.6e}"
            print(f"  {row['source']} {row['state']} = {value_str}")
        print_ratio_tuning_hint(ratio_df)
        print(f"Saved: {ratio_path}")

    print(f"Saved: {params_path}")
    print(f"Saved: {metrics_path}")


def print_ratio_tuning_hint(ratio_df):
    ratios = ratio_df[ratio_df["state"].isin(["SET_LRS_to_HRS", "RESET_LRS_to_HRS"])]
    if ratios.empty:
        return

    pivot = ratios.pivot_table(
        index="state",
        columns="source",
        values="abs_current_A",
        aggfunc="first",
    )
    if not {"experiment", "simulation"}.issubset(pivot.columns):
        return

    mismatch = pivot["simulation"] / pivot["experiment"]
    mismatch = mismatch.replace([np.inf, -np.inf], np.nan).dropna()
    if mismatch.empty:
        return

    typical_factor = float(np.nanmedian(mismatch))
    if typical_factor <= 1.5:
        return

    print(
        "\nRatio hint: simulated LRS/HRS is about "
        f"{typical_factor:.2g}x higher than experiment. "
        "To reduce that while keeping SET/RESET voltage roughly fixed, first try "
        "increasing --g0 or narrowing --gap-max minus --gap-min. Lower --gap-max "
        "if HRS current is too low; raise --gap-min if LRS current is too high. "
        "--I0 mainly shifts both states together, so it usually will not fix ratio by itself."
    )


def plot_overlay(exp_fit, sim_all, output_dir):
    if "butterfly_sequence_index" in exp_fit.columns:
        plot_butterfly_overlay(exp_fit, sim_all, output_dir)
        return

    fig, ax = plt.subplots(figsize=(7.2, 5.2))

    for branch, g in exp_fit.groupby("branch"):
        ax.plot(
            g["voltage_V"],
            g["median_abs_current_A"],
            linewidth=2.8,
            label=f"{branch} experiment",
        )

    for branch, g in sim_all.groupby("branch"):
        ax.plot(
            g["voltage_V"],
            g["abs_current_A"],
            linewidth=2.0,
            linestyle="--",
            label=f"{branch} Stanford baseline",
        )

    ax.set_yscale("log")
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("|Current| (A)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()

    path = output_dir / "03_baseline_overlay.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {path}")


def signed_experiment_current(exp_fit):
    if "median_current_A" in exp_fit.columns:
        return pd.to_numeric(exp_fit["median_current_A"], errors="coerce").to_numpy(float)

    sign = np.where(exp_fit["branch"].astype(str).eq("RESET"), -1.0, 1.0)
    return sign * pd.to_numeric(exp_fit["median_abs_current_A"], errors="coerce").to_numpy(float)


def plot_butterfly_overlay(exp_fit, sim_all, output_dir):
    exp = exp_fit.sort_values("butterfly_sequence_index").copy()
    sim = sim_all.sort_values("time_s").copy()

    exp_current = signed_experiment_current(exp)

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.semilogy(
        exp["voltage_V"],
        np.abs(exp_current),
        linewidth=2.8,
        label="Measured representative",
    )
    ax.semilogy(
        sim["voltage_V"],
        sim["abs_current_A"],
        linewidth=2.0,
        linestyle="--",
        label="Stanford baseline",
    )
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("|Current| (A)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()

    path = output_dir / "03_baseline_overlay.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.plot(
        exp["voltage_V"],
        exp_current,
        linewidth=2.8,
        label="Measured representative butterfly",
    )
    ax.plot(
        sim["voltage_V"],
        sim["current_A"],
        linewidth=2.0,
        linestyle="--",
        label="Stanford baseline butterfly",
    )
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()

    linear_path = output_dir / "03_baseline_overlay_linear.png"
    fig.savefig(linear_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {linear_path}")


def main():
    p = argparse.ArgumentParser()

    p.add_argument("--rep-csv", type=Path, required=True)
    p.add_argument("--va", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("step03_baseline"))

    p.add_argument("--hspice-cmd", default="hspice")
    p.add_argument("--no-run", action="store_true")
    p.add_argument(
        "--deck-mode",
        choices=["butterfly", "separate"],
        default="butterfly",
        help="butterfly runs one bipolar PWL deck; separate runs legacy SET and RESET pulse decks.",
    )
    p.add_argument(
        "--no-auto-sweep-limits",
        action="store_true",
        help="Do not set SET/RESET sweep limits from the representative CSV voltage range.",
    )

    p.add_argument("--set-vmin", type=float, default=0.0)
    p.add_argument("--set-vmax", type=float, default=1.1)
    p.add_argument("--reset-vmin", type=float, default=-2.0)
    p.add_argument("--reset-vmax", type=float, default=0.0)
    p.add_argument(
        "--read-voltage",
        type=float,
        default=0.1,
        help="Read voltage magnitude used for HRS/LRS ratio diagnostics.",
    )
    p.add_argument(
        "--set-compliance-current",
        type=float,
        default=None,
        help="Clamp positive-voltage simulated SET current magnitude to this compliance current.",
    )
    p.add_argument(
        "--auto-set-compliance-current",
        action="store_true",
        help="Estimate SET compliance from the measured high-voltage SET plateau and clamp simulated SET current.",
    )

    p.add_argument("--gap-min", type=float, default=5e-10)#2e-10
    p.add_argument("--gap-max", type=float, default=15e-10)#18e-10
    p.add_argument("--g0", type=float, default=0.35e-9)#0.25e-9
    p.add_argument("--V0", type=float, default=0.35)#0.25
    p.add_argument("--Vel0", type=float, default=10.0)
    p.add_argument("--I0", type=float, default=1e-3)
    p.add_argument("--beta", type=float, default=0.8)
    p.add_argument("--gamma0", type=float, default=16.0)
    p.add_argument("--Rth", type=float, default=2.1e3)
    p.add_argument("--tox", type=float, default=7e-9)
    p.add_argument("--deltaGap0", "--delta-gap0", dest="deltaGap0", type=float, default=1e-4)

    p.add_argument("--ramp-time", default="4m")
    p.add_argument("--hold-time", default="1m")
    p.add_argument("--period", default="10m")
    p.add_argument("--tstep", default="1u")
    p.add_argument("--tstop", default="5.2m")
    p.add_argument("--butterfly-set-time", default="1m")
    p.add_argument("--butterfly-zero-after-set-time", default="2m")
    p.add_argument("--butterfly-reset-time", default="3m")
    p.add_argument("--butterfly-final-time", default="4m")
    p.add_argument("--butterfly-tstop", default="4m")

    args = p.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rep = pd.read_csv(args.rep_csv)
    if args.deck_mode == "butterfly" and not args.no_auto_sweep_limits:
        apply_rep_voltage_limits(rep, args)

    exp_fit = filter_rep(rep, args)
    if "butterfly_sequence_index" in exp_fit.columns:
        exp_fit = exp_fit.sort_values("butterfly_sequence_index")
    exp_fit.to_csv(output_dir / "03_experiment_fit_window.csv", index=False)
    set_compliance_current = resolve_set_compliance_current(args, exp_fit)

    va_path = args.va.expanduser().resolve()

    if args.deck_mode == "butterfly":
        decks = [("BUTTERFLY", make_butterfly_deck(va_path, output_dir, args))]
    else:
        decks = [
            ("SET", make_deck("SET", va_path, output_dir, args)),
            ("RESET", make_deck("RESET", va_path, output_dir, args)),
        ]

    for _, deck in decks:
        print(f"Saved: {deck}")

    if args.no_run:
        print("Decks generated only.")
        return

    remove_stale_outputs(output_dir)

    sim_rows = []

    for label, deck in decks:
        code, runlog = run_hspice(deck, args.hspice_cmd)
        require_hspice_success(label, code, runlog)

        lis_path = deck.with_suffix(".lis")
        if lis_path.exists():
            sim = parse_hspice_lis(lis_path)
        else:
            sim = fallback_parse_stdout(runlog)

        sim = require_sim_points(label, sim, lis_path, runlog)
        if args.deck_mode == "butterfly":
            sim = label_butterfly_branches(sim)
            sim = apply_set_compliance(sim, set_compliance_current)
            sim_path = output_dir / "03_butterfly_sim.csv"
        else:
            sim["branch"] = label
            if label == "SET":
                sim = apply_set_compliance(sim, set_compliance_current)
            sim_path = output_dir / f"03_{label.lower()}_sim.csv"
        sim.to_csv(sim_path, index=False)

        print(f"{label}: return_code={code}")
        print(f"Saved: {sim_path}")

        sim_rows.append(sim)

    sim_all = pd.concat(sim_rows, ignore_index=True)
    sim_all.to_csv(output_dir / "03_all_sim.csv", index=False)

    if args.deck_mode == "butterfly" and "butterfly_sequence_index" in exp_fit.columns:
        comparison = interpolate_butterfly_sim_to_exp(sim_all, exp_fit)
    else:
        comp_rows = []

        for branch, exp_branch in exp_fit.groupby("branch"):
            sim_branch = sim_all[sim_all["branch"] == branch]
            comp_rows.append(interpolate_sim_to_exp(sim_branch, exp_branch))

        comparison = pd.concat(comp_rows, ignore_index=True)
    comparison.to_csv(output_dir / "03_exp_vs_baseline_comparison.csv", index=False)

    valid = comparison["log_error"].replace([np.inf, -np.inf], np.nan).dropna()

    if len(valid):
        mae = float(np.mean(np.abs(valid)))
        rmse = float(np.sqrt(np.mean(valid**2)))
        print(f"log10 MAE = {mae:.4f} decades")
        print(f"log10 RMSE = {rmse:.4f} decades")
    else:
        print("No valid comparison points parsed.")

    save_and_print_fit_report(args, output_dir, comparison, exp_fit, sim_all)
    plot_overlay(exp_fit, sim_all, output_dir)


if __name__ == "__main__":
    main()
