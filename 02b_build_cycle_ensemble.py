#!/usr/bin/env python3
"""Build a per-cycle ensemble CSV for the representative device.

Stages 1-4 of TaO-Fit fit a single representative (medoid) curve. To attach
cross-cycle uncertainty (Stage-5 LOCO + bootstrap), we need every good cycle of
that *same* device as separate curves. This reshapes step01's extracted points
into the long format main_fit_stanford expects, tagging each row with its
`representative_cycle_id` so Stage 5 can resample cycles.

Usage:
  python3 02b_build_cycle_ensemble.py --step01-dir step01_S1 \
      --rep-csv step02_S1/S1_..._representative_curve_FIXED.csv \
      --output  step02_S1/S1_cycle_ensemble.csv
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step01-dir", required=True)
    ap.add_argument("--rep-csv", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-cycles", type=int, default=3)
    args = ap.parse_args()

    pts = pd.read_csv(Path(args.step01_dir) / "01_extracted_points.csv")
    rep = pd.read_csv(args.rep_csv)
    device = str(rep["device_id"].iloc[0])

    df = pts[(pts["device_id"].astype(str) == device)].copy()
    if "is_good_cycle" in df.columns:
        df = df[df["is_good_cycle"] == 1]
    df["branch"] = df["branch"].astype(str).str.upper()
    df = df[df["branch"].isin(["SET", "RESET"])]
    df = df.dropna(subset=["voltage_V", "current_A"])

    cycles = sorted(df["cycle_id"].unique())
    if len(cycles) < args.min_cycles:
        raise SystemExit(
            f"Only {len(cycles)} good cycles for {device}; need >= {args.min_cycles} "
            f"for LOCO/bootstrap. Lower --min-cycles or pick another device."
        )

    abs_i = df["abs_current_A"] if "abs_current_A" in df else df["current_A"].abs()
    log_i = (df["log10_abs_current"] if "log10_abs_current" in df
             else np.log10(np.clip(abs_i, 1e-14, None)))
    out = pd.DataFrame({
        "condition": df.get("condition", device),
        "device_id": device,
        "representative_cycle_id": df["cycle_id"].astype(int),
        "branch": df["branch"],
        "voltage_V": df["voltage_V"].astype(float),
        "median_current_A": df["current_A"].astype(float),
        "median_abs_current_A": np.asarray(abs_i, dtype=float),
        "median_log10_abs_current": np.asarray(log_i, dtype=float),
        # point_index = position within the sweep; Stage 5 aggregates cycles by
        # (branch, point_index) so the butterfly/hysteresis shape is preserved
        # (grouping by voltage alone would merge the forward and return sweeps).
        "point_index": df["point_index"].astype(int),
        "butterfly_sequence_index": df["point_index"].astype(int),
    })
    # q25==q75==median -> eval_loss falls back to its default log-sigma
    out["q25_current_A"] = out["median_current_A"]
    out["q75_current_A"] = out["median_current_A"]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"[ensemble] {device}: {len(cycles)} cycles, {len(out)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
