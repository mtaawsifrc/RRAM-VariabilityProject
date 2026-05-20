#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def as_bool(series):
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def pick_best_device(device_summary, min_good_cycles):
    eligible = device_summary[device_summary["good_cycles"] >= min_good_cycles].copy()
    if len(eligible) == 0:
        eligible = device_summary.copy()

    eligible = eligible.sort_values(
        by=["good_cycles", "mean_quality_score", "good_fraction"],
        ascending=[False, False, False],
    )

    return eligible.iloc[0]


def split_voltage_segments(g, min_segment_points=20):
    g = g.sort_values("point_index").copy()
    v = g["voltage_V"].to_numpy(float)

    if len(v) < min_segment_points:
        return []

    dv = np.diff(v)
    direction = np.sign(dv)

    for k in range(1, len(direction)):
        if direction[k] == 0:
            direction[k] = direction[k - 1]

    cut_indices = [0]

    for k in range(1, len(direction)):
        if direction[k] != 0 and direction[k - 1] != 0 and direction[k] != direction[k - 1]:
            cut_indices.append(k + 1)

    cut_indices.append(len(g))

    segments = []
    for start, end in zip(cut_indices[:-1], cut_indices[1:]):
        seg = g.iloc[start:end].copy()
        if len(seg) >= min_segment_points:
            segments.append(seg)

    return segments


def choose_programming_segment(cycle_branch_df, branch, min_segment_points, min_segment_vspan):
    candidates = []

    for (_, block_id), g in cycle_branch_df.groupby(["cycle_id", "block_id"]):
        segments = split_voltage_segments(g, min_segment_points=min_segment_points)

        for seg in segments:
            v = seg["voltage_V"].to_numpy(float)

            if len(v) < min_segment_points:
                continue

            vspan = np.nanmax(v) - np.nanmin(v)
            if vspan < min_segment_vspan:
                continue

            if branch == "SET":
                polarity_fraction = np.mean(v >= 0)
                direction_score = v[-1] - v[0]
                useful_span = np.nanmax(v) - max(np.nanmin(v), 0)
                score = 5 * polarity_fraction + 2 * direction_score + useful_span

            elif branch == "RESET":
                polarity_fraction = np.mean(v <= 0)
                direction_score = v[0] - v[-1]
                useful_span = min(np.nanmax(v), 0) - np.nanmin(v)
                score = 5 * polarity_fraction + 2 * direction_score + useful_span

            else:
                continue

            candidates.append((score, seg))

    if not candidates:
        return pd.DataFrame()

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1].copy()


def build_programming_segments(selected_points, args):
    rows = []

    for (cycle_id, branch), g in selected_points.groupby(["cycle_id", "branch"]):
        if branch not in ["SET", "RESET"]:
            continue

        seg = choose_programming_segment(
            g,
            branch=branch,
            min_segment_points=args.min_segment_points,
            min_segment_vspan=args.min_segment_vspan,
        )

        if len(seg) == 0:
            continue

        seg = seg.copy()
        seg["fit_segment"] = f"{branch}_PROGRAM"
        rows.append(seg)

    if not rows:
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def make_voltage_grid(branch_df, branch, n_grid):
    if branch == "SET":
        vmin = max(0.0, branch_df["voltage_V"].quantile(0.01))
        vmax = branch_df["voltage_V"].quantile(0.99)
    else:
        vmin = branch_df["voltage_V"].quantile(0.01)
        vmax = min(0.0, branch_df["voltage_V"].quantile(0.99))

    return np.linspace(vmin, vmax, n_grid)


def representative_branch_curve(branch_df, branch, grid, min_overlap_cycles):
    interp_rows = []

    for cycle_id, g in branch_df.groupby("cycle_id"):
        g = g.sort_values("point_index")

        v = g["voltage_V"].to_numpy(float)
        y = g["log10_abs_current"].to_numpy(float)

        keep = np.isfinite(v) & np.isfinite(y)
        v = v[keep]
        y = y[keep]

        if len(v) < 5:
            continue

        order = np.argsort(v)
        v = v[order]
        y = y[order]

        unique_v, inv = np.unique(v, return_inverse=True)
        unique_y = np.zeros_like(unique_v)

        for idx in range(len(unique_v)):
            unique_y[idx] = np.median(y[inv == idx])

        if len(unique_v) < 5:
            continue

        valid_grid = grid[(grid >= unique_v.min()) & (grid <= unique_v.max())]

        if len(valid_grid) == 0:
            continue

        interp_y = np.interp(valid_grid, unique_v, unique_y)

        for vv, yy in zip(valid_grid, interp_y):
            interp_rows.append(
                {
                    "cycle_id": cycle_id,
                    "branch": branch,
                    "voltage_V": vv,
                    "log10_abs_current": yy,
                }
            )

    interp_df = pd.DataFrame(interp_rows)

    if len(interp_df) == 0:
        return pd.DataFrame()

    rep = (
        interp_df
        .groupby("voltage_V")["log10_abs_current"]
        .agg(
            median_log10_abs_current="median",
            q25_log10_abs_current=lambda x: np.percentile(x, 25),
            q75_log10_abs_current=lambda x: np.percentile(x, 75),
            n_cycles="count",
        )
        .reset_index()
    )

    rep = rep[rep["n_cycles"] >= min_overlap_cycles].copy()

    if len(rep) == 0:
        return pd.DataFrame()

    rep["median_abs_current_A"] = 10 ** rep["median_log10_abs_current"]
    rep["q25_abs_current_A"] = 10 ** rep["q25_log10_abs_current"]
    rep["q75_abs_current_A"] = 10 ** rep["q75_log10_abs_current"]

    return rep


def interpolate_cycles_to_grid(branch_df, grid):
    interp_rows = []

    for cycle_id, g in branch_df.groupby("cycle_id"):
        g = g.sort_values("point_index")

        v = g["voltage_V"].to_numpy(float)
        y = g["log10_abs_current"].to_numpy(float)

        keep = np.isfinite(v) & np.isfinite(y)
        v = v[keep]
        y = y[keep]

        if len(v) < 5:
            continue

        order = np.argsort(v)
        v = v[order]
        y = y[order]

        unique_v, inv = np.unique(v, return_inverse=True)
        unique_y = np.zeros_like(unique_v)

        for idx in range(len(unique_v)):
            unique_y[idx] = np.median(y[inv == idx])

        if len(unique_v) < 5:
            continue

        valid_grid = grid[(grid >= unique_v.min()) & (grid <= unique_v.max())]

        if len(valid_grid) == 0:
            continue

        interp_y = np.interp(valid_grid, unique_v, unique_y)

        for vv, yy in zip(valid_grid, interp_y):
            interp_rows.append(
                {
                    "cycle_id": cycle_id,
                    "voltage_V": vv,
                    "log10_abs_current": yy,
                }
            )

    return pd.DataFrame(interp_rows)


def score_branch_cycles_against_typical(branch_df, branch, args):
    grid = make_voltage_grid(branch_df, branch, args.n_grid)
    interp_df = interpolate_cycles_to_grid(branch_df, grid)

    if len(interp_df) == 0:
        return pd.DataFrame()

    overlap = interp_df.groupby("voltage_V")["cycle_id"].transform("count")
    interp_df = interp_df[overlap >= args.min_overlap_cycles].copy()

    if len(interp_df) == 0:
        return pd.DataFrame()

    interp_df["typical_log10_abs_current"] = (
        interp_df.groupby("voltage_V")["log10_abs_current"].transform("median")
    )
    interp_df["abs_log_error"] = (
        interp_df["log10_abs_current"] - interp_df["typical_log10_abs_current"]
    ).abs()

    scores = (
        interp_df
        .groupby("cycle_id")
        .agg(
            representative_score=("abs_log_error", "median"),
            mean_abs_log_error=("abs_log_error", "mean"),
            p90_abs_log_error=("abs_log_error", lambda x: np.percentile(x, 90)),
            overlap_points=("abs_log_error", "count"),
        )
        .reset_index()
    )

    scores = scores[scores["overlap_points"] >= args.min_medoid_grid_points].copy()
    if len(scores) == 0:
        return pd.DataFrame()

    scores["branch"] = branch
    scores["branch_cycle_count"] = branch_df["cycle_id"].nunique()
    return scores


def measured_curve_from_cycle(selected_points, program_segments, branch, cycle_id, score_row, args):
    program_seg = program_segments[
        (program_segments["branch"] == branch)
        & (program_segments["cycle_id"] == cycle_id)
    ].copy()

    if len(program_seg) == 0:
        return pd.DataFrame()

    block_id = program_seg["block_id"].mode().iloc[0]
    seg = selected_points[
        (selected_points["branch"] == branch)
        & (selected_points["cycle_id"] == cycle_id)
        & (selected_points["block_id"] == block_id)
    ].copy()

    if len(seg) == 0:
        return pd.DataFrame()

    seg = seg.sort_values("point_index").copy()
    out = pd.DataFrame(
        {
            "branch": branch,
            "block_id": seg["block_id"].to_numpy(int),
            "block_title": seg["block_title"].astype(str).to_numpy(),
            "voltage_V": seg["voltage_V"].to_numpy(float),
            "median_current_A": seg["current_A"].to_numpy(float),
            "q25_current_A": seg["current_A"].to_numpy(float),
            "q75_current_A": seg["current_A"].to_numpy(float),
            "median_log10_abs_current": seg["log10_abs_current"].to_numpy(float),
            "q25_log10_abs_current": seg["log10_abs_current"].to_numpy(float),
            "q75_log10_abs_current": seg["log10_abs_current"].to_numpy(float),
            "median_abs_current_A": seg["abs_current_A"].to_numpy(float),
            "q25_abs_current_A": seg["abs_current_A"].to_numpy(float),
            "q75_abs_current_A": seg["abs_current_A"].to_numpy(float),
            "n_cycles": int(score_row["branch_cycle_count"]),
            "representative_mode": args.representative_mode,
            "representative_cycle_id": int(cycle_id),
            "representative_score": float(score_row["representative_score"]),
            "representative_point_index": seg["point_index"].to_numpy(int),
            "representative_source_file": seg["source_file"].astype(str).to_numpy(),
        }
    )
    return out


def representative_measured_curve(selected_points, program_segments, args):
    score_rows = []

    for branch, g in program_segments.groupby("branch"):
        if branch not in ["SET", "RESET"]:
            continue

        scores = score_branch_cycles_against_typical(g, branch, args)
        if len(scores):
            score_rows.append(scores)

    if not score_rows:
        return pd.DataFrame(), pd.DataFrame()

    scores = pd.concat(score_rows, ignore_index=True)
    scores["branch_rank"] = scores.groupby("branch")["representative_score"].rank(method="min")
    branch_counts = scores.groupby("branch")["cycle_id"].transform("count")
    scores["branch_rank_fraction"] = np.where(
        branch_counts > 1,
        (scores["branch_rank"] - 1) / (branch_counts - 1),
        0.0,
    )
    selected_by_branch = {}

    if args.representative_mode == "medoid-cycle":
        pivot = scores.pivot_table(
            index="cycle_id",
            columns="branch",
            values="branch_rank_fraction",
            aggfunc="min",
        )

        required = [branch for branch in ["SET", "RESET"] if branch in scores["branch"].unique()]
        if required:
            complete = pivot.dropna(subset=required).copy()
        else:
            complete = pd.DataFrame()

        if len(complete):
            complete["combined_representative_score"] = complete[required].mean(axis=1)
            cycle_id = complete["combined_representative_score"].idxmin()
            for branch in required:
                selected_by_branch[branch] = cycle_id
        else:
            for branch, g in scores.groupby("branch"):
                selected_by_branch[branch] = g.sort_values("representative_score").iloc[0]["cycle_id"]
    else:
        for branch, g in scores.groupby("branch"):
            selected_by_branch[branch] = g.sort_values("representative_score").iloc[0]["cycle_id"]

    rep_rows = []
    for branch in ["SET", "RESET"]:
        if branch not in selected_by_branch:
            continue

        cycle_id = selected_by_branch[branch]
        score_row = scores[
            (scores["branch"] == branch)
            & (scores["cycle_id"] == cycle_id)
        ].sort_values("representative_score").iloc[0]

        rep = measured_curve_from_cycle(selected_points, program_segments, branch, cycle_id, score_row, args)
        if len(rep):
            rep_rows.append(rep)

    if not rep_rows:
        return pd.DataFrame(), scores

    return pd.concat(rep_rows, ignore_index=True), scores


def estimate_threshold(program_segments, branch, current_threshold):
    rows = []

    for cycle_id, g in program_segments[program_segments["branch"] == branch].groupby("cycle_id"):
        g = g.sort_values("point_index")

        v = g["voltage_V"].to_numpy(float)
        iabs = g["abs_current_A"].to_numpy(float)

        keep = np.isfinite(v) & np.isfinite(iabs)
        v = v[keep]
        iabs = iabs[keep]

        if len(v) < 5:
            continue

        mask = iabs >= current_threshold

        if np.any(mask):
            idx = np.argmax(mask)
            vth = v[idx]
        else:
            vth = np.nan

        rows.append(
            {
                "cycle_id": cycle_id,
                "branch": branch,
                "threshold_current_A": current_threshold,
                "estimated_switch_voltage_V": vth,
                "max_abs_current_A": np.nanmax(iabs),
                "min_abs_current_A": np.nanmin(iabs),
            }
        )

    return rows


def current_at_vread(program_segments, vread):
    rows = []

    for (cycle_id, branch), g in program_segments.groupby(["cycle_id", "branch"]):
        g = g.sort_values("voltage_V")

        v = g["voltage_V"].to_numpy(float)
        y = g["log10_abs_current"].to_numpy(float)

        keep = np.isfinite(v) & np.isfinite(y)
        v = v[keep]
        y = y[keep]

        if len(v) < 5:
            continue

        unique_v, inv = np.unique(v, return_inverse=True)
        unique_y = np.zeros_like(unique_v)

        for idx in range(len(unique_v)):
            unique_y[idx] = np.median(y[inv == idx])

        if vread < unique_v.min() or vread > unique_v.max():
            iread = np.nan
        else:
            iread = 10 ** np.interp(vread, unique_v, unique_y)

        rows.append(
            {
                "cycle_id": cycle_id,
                "branch": branch,
                "vread_V": vread,
                "abs_current_at_vread_A": iread,
            }
        )

    return rows


def plot_selected_device(selected_points, program_segments, rep_df, output_dir, stem):
    fig, ax = plt.subplots(figsize=(7.5, 5.5))

    for (_, _, branch), g in selected_points.groupby(["cycle_id", "block_id", "branch"]):
        if branch not in ["SET", "RESET"]:
            continue
        g = g.sort_values("point_index")
        ax.plot(
            g["voltage_V"],
            g["abs_current_A"],
            linewidth=0.5,
            alpha=0.15,
        )

    for (_, branch), g in program_segments.groupby(["cycle_id", "branch"]):
        g = g.sort_values("point_index")
        ax.plot(
            g["voltage_V"],
            g["abs_current_A"],
            linewidth=0.8,
            alpha=0.35,
        )

    for branch, g in rep_df.groupby("branch"):
        if "representative_point_index" in g.columns and g["representative_point_index"].notna().any():
            g = g.sort_values("representative_point_index")
            cycle_ids = sorted(g["representative_cycle_id"].dropna().unique())
            cycle_label = f" cycle {int(cycle_ids[0])}" if len(cycle_ids) == 1 else ""
            label = f"{branch} measured medoid{cycle_label}"
        else:
            g = g.sort_values("voltage_V")
            label = f"{branch} median fit-segment"

        ax.plot(
            g["voltage_V"],
            g["median_abs_current_A"],
            linewidth=2.8,
            label=label,
        )

    ax.set_yscale("log")
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("|Current| (A)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()

    path = output_dir / f"{stem}_representative_curve_FIXED.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {path}")


def main():
    p = argparse.ArgumentParser()

    p.add_argument("--step01-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("step02_selected_device_FIXED"))

    p.add_argument("--condition", default="")
    p.add_argument("--device-id", default="")
    p.add_argument("--min-good-cycles", type=int, default=5)

    p.add_argument("--n-grid", type=int, default=300)
    p.add_argument("--vread", type=float, default=0.1)
    p.add_argument("--switch-current-threshold", type=float, default=1e-6)

    p.add_argument("--min-segment-points", type=int, default=20)
    p.add_argument("--min-segment-vspan", type=float, default=0.3)
    p.add_argument("--min-overlap-cycles", type=int, default=5)
    p.add_argument(
        "--representative-mode",
        choices=["medoid-cycle", "medoid-branch", "median-grid"],
        default="medoid-cycle",
        help=(
            "medoid-cycle selects one real SET/RESET cycle closest to typical behavior; "
            "medoid-branch selects one real cycle per branch; median-grid keeps the old "
            "pointwise median curve."
        ),
    )
    p.add_argument(
        "--min-medoid-grid-points",
        type=int,
        default=20,
        help="Minimum voltage-grid overlap points required when scoring medoid cycles.",
    )

    args = p.parse_args()

    step01_dir = args.step01_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    points = pd.read_csv(step01_dir / "01_extracted_points.csv")
    device_summary = pd.read_csv(step01_dir / "01_device_summary.csv")

    points["is_good_cycle"] = as_bool(points["is_good_cycle"])

    if args.condition:
        device_summary = device_summary[device_summary["condition"] == args.condition]
        points = points[points["condition"] == args.condition]

    if args.device_id:
        selected_condition = args.condition if args.condition else points[points["device_id"] == args.device_id]["condition"].iloc[0]
        selected_device = args.device_id
    else:
        selected = pick_best_device(device_summary, args.min_good_cycles)
        selected_condition = selected["condition"]
        selected_device = selected["device_id"]

    selected_points = points[
        (points["condition"] == selected_condition)
        & (points["device_id"] == selected_device)
        & (points["is_good_cycle"])
        & (points["branch"].isin(["SET", "RESET"]))
    ].copy()

    if len(selected_points) == 0:
        raise RuntimeError("No good SET/RESET points found.")

    stem = f"{selected_condition}_{selected_device}".replace("/", "_").replace(" ", "_")

    program_segments = build_programming_segments(selected_points, args)

    if len(program_segments) == 0:
        raise RuntimeError("No valid programming segments found.")

    score_df = pd.DataFrame()

    if args.representative_mode == "median-grid":
        rep_rows = []

        for branch, g in program_segments.groupby("branch"):
            grid = make_voltage_grid(g, branch, args.n_grid)

            rep = representative_branch_curve(
                g,
                branch=branch,
                grid=grid,
                min_overlap_cycles=args.min_overlap_cycles,
            )

            if len(rep):
                rep["branch"] = branch
                rep["representative_mode"] = args.representative_mode
                rep_rows.append(rep)

        if not rep_rows:
            raise RuntimeError("No representative curve generated. Lower --min-overlap-cycles.")

        rep_df = pd.concat(rep_rows, ignore_index=True)
    else:
        rep_df, score_df = representative_measured_curve(selected_points, program_segments, args)

        if len(rep_df) == 0:
            raise RuntimeError(
                "No measured medoid representative curve generated. "
                "Try --representative-mode median-grid or lower --min-medoid-grid-points."
            )

    rep_df.insert(0, "condition", selected_condition)
    rep_df.insert(1, "device_id", selected_device)

    core_columns = [
        "condition",
        "device_id",
        "branch",
        "voltage_V",
        "median_current_A",
        "q25_current_A",
        "q75_current_A",
        "median_log10_abs_current",
        "q25_log10_abs_current",
        "q75_log10_abs_current",
        "median_abs_current_A",
        "q25_abs_current_A",
        "q75_abs_current_A",
        "n_cycles",
    ]
    core_columns = [col for col in core_columns if col in rep_df.columns]
    extra_columns = [col for col in rep_df.columns if col not in core_columns]
    rep_df = rep_df[core_columns + extra_columns]

    if "representative_point_index" in rep_df.columns:
        branch_order = {"SET": 0, "RESET": 1}
        rep_df["_branch_order"] = rep_df["branch"].map(branch_order).fillna(99)
        rep_df = rep_df.sort_values(
            ["_branch_order", "representative_point_index"],
            kind="stable",
        ).drop(columns="_branch_order")
        rep_df["butterfly_sequence_index"] = np.arange(1, len(rep_df) + 1)

    selected_points_path = output_dir / f"{stem}_selected_points.csv"
    segment_path = output_dir / f"{stem}_programming_segments.csv"
    rep_path = output_dir / f"{stem}_representative_curve_FIXED.csv"
    score_path = output_dir / f"{stem}_representative_scores_FIXED.csv"
    targets_path = output_dir / f"{stem}_fit_targets_FIXED.csv"
    info_path = output_dir / f"{stem}_selection_info_FIXED.txt"

    selected_points.to_csv(selected_points_path, index=False)
    program_segments.to_csv(segment_path, index=False)
    rep_df.to_csv(rep_path, index=False)
    if len(score_df):
        score_df.insert(0, "condition", selected_condition)
        score_df.insert(1, "device_id", selected_device)
        score_df.to_csv(score_path, index=False)

    target_rows = []
    for branch in ["SET", "RESET"]:
        target_rows.extend(
            estimate_threshold(
                program_segments,
                branch,
                args.switch_current_threshold,
            )
        )

    target_rows.extend(current_at_vread(program_segments, args.vread))

    targets = pd.DataFrame(target_rows)
    targets.insert(0, "condition", selected_condition)
    targets.insert(1, "device_id", selected_device)
    targets.to_csv(targets_path, index=False)

    with info_path.open("w") as f:
        f.write(f"condition={selected_condition}\n")
        f.write(f"device_id={selected_device}\n")
        f.write(f"good_cycles={selected_points['cycle_id'].nunique()}\n")
        f.write(f"selected_points={len(selected_points)}\n")
        f.write(f"programming_segment_cycles={program_segments['cycle_id'].nunique()}\n")
        f.write(f"programming_segment_points={len(program_segments)}\n")
        f.write(f"representative_mode={args.representative_mode}\n")
        f.write(f"vread={args.vread}\n")
        f.write(f"switch_current_threshold={args.switch_current_threshold}\n")
        f.write(f"min_overlap_cycles={args.min_overlap_cycles}\n")
        f.write(f"min_medoid_grid_points={args.min_medoid_grid_points}\n")
        if "representative_cycle_id" in rep_df.columns:
            for branch, g in rep_df.groupby("branch"):
                cycle_ids = sorted(g["representative_cycle_id"].dropna().unique())
                if cycle_ids:
                    f.write(f"{branch.lower()}_representative_cycle_id={int(cycle_ids[0])}\n")

    plot_selected_device(selected_points, program_segments, rep_df, output_dir, stem)

    print(f"Selected: {selected_condition} | {selected_device}")
    print(f"Good cycles: {selected_points['cycle_id'].nunique()}")
    print(f"Programming segment cycles: {program_segments['cycle_id'].nunique()}")
    print(f"Saved: {selected_points_path}")
    print(f"Saved: {segment_path}")
    print(f"Saved: {rep_path}")
    if len(score_df):
        print(f"Saved: {score_path}")
    print(f"Saved: {targets_path}")
    print(f"Saved: {info_path}")


if __name__ == "__main__":
    main()
