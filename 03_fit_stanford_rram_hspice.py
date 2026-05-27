#!/usr/bin/env python3
"""
03_fit_stanford_rram_hspice.py

Stage-wise nominal parameter extraction for the uploaded Stanford RRAM
Verilog-A / HSPICE model (rram_v_1_0_0_hspice.va or .txt).

This script is designed to work AFTER your existing scripts:

  01_extract_clean_cycles.py
  02_select_device_representative_curve.py

It can either:
  (A) consume an existing representative curve CSV from step 02, or
  (B) call your existing step 01 and step 02 scripts verbatim if raw data is provided.

The fitting strategy follows the reviewer-hardened approach discussed earlier:
  1. Use a real medoid-cycle representative curve, not a pointwise average.
  2. Fit only nominal deterministic parameters; model_switch is fixed to 0.
  3. Use log-current residuals and robust losses across SET/RESET branches.
  4. Use stage-wise optimization: amplitude -> SET dynamics -> RESET dynamics -> joint refinement.
  5. Run an exact-code sensitivity audit around the initial seed.
  6. Save all decks, logs, progress, final parameter card, and diagnostic plots.

Important assumptions:
  - The Stanford Verilog-A model module name is rram_v_1_0_0.
  - HSPICE supports .hdl for the Verilog-A file.
  - HSPICE ASCII .lis output from `.print tran V(te) I(VDRV)` is parseable.
  - If HSPICE output format differs on your system, edit parse_hspice_lis().

Author: ChatGPT, customized for Md Tawsif Rahman Chowdhury's RRAM workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# -----------------------------------------------------------------------------
# Configuration data structures
# -----------------------------------------------------------------------------


@dataclass
class ParameterSpec:
    name: str
    default: float
    lo: float
    hi: float
    log_space: bool = True
    fit: bool = True
    description: str = ""

    def to_internal(self, value: float) -> float:
        value = float(value)
        if self.log_space:
            value = max(value, self.lo)
            return math.log10(value)
        return value

    def from_internal(self, x: float) -> float:
        if self.log_space:
            return float(10 ** x)
        return float(x)

    @property
    def internal_bounds(self) -> tuple[float, float]:
        if self.log_space:
            return (math.log10(self.lo), math.log10(self.hi))
        return (self.lo, self.hi)


@dataclass
class TargetBranch:
    branch: str
    voltage: np.ndarray
    current: np.ndarray
    abs_current: np.ndarray
    log_abs_current: np.ndarray
    weights: np.ndarray
    source_df: pd.DataFrame
    vread: float
    threshold_current: float
    vth_current: float = np.nan
    vth_derivative: float = np.nan
    width_20_80: float = np.nan
    iread_abs: float = np.nan


@dataclass
class SimulationResult:
    ok: bool
    branch: str
    time: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    voltage: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    current: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    abs_current: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    log_abs_current: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    features: dict[str, float] = field(default_factory=dict)
    deck_path: str = ""
    lis_path: str = ""
    error: str = ""


@dataclass
class EvalResult:
    ok: bool
    loss: float
    params: dict[str, float]
    stage: str
    sim: dict[str, SimulationResult] = field(default_factory=dict)
    terms: dict[str, float] = field(default_factory=dict)
    error: str = ""
    eval_id: str = ""


# -----------------------------------------------------------------------------
# Defaults for the exact uploaded Stanford model.
# These are intentionally conservative. They can be overridden in JSON.
# -----------------------------------------------------------------------------


def default_parameter_specs(include_fmin: bool = False) -> dict[str, ParameterSpec]:
    specs = {
        "I0": ParameterSpec(
            "I0", 1000e-6, 1e-12, 1e-2, True, True,
            "current prefactor in I0*exp(-gap/g0)*sinh(V/V0)",
        ),
        "g0": ParameterSpec(
            "g0", 0.25e-9, 0.03e-9, 2.0e-9, True, True,
            "gap exponential scale; controls memory-window amplification",
        ),
        "V0": ParameterSpec(
            "V0", 0.25, 0.03, 3.0, True, True,
            "voltage scale in sinh(V/V0); controls branch curvature",
        ),
        "Vel0": ParameterSpec(
            "Vel0", 10.0, 1e-10, 20.0, True, True,
            "kinetic prefactor for gap evolution; sweep-protocol dependent",
        ),
        "beta": ParameterSpec(
            "beta", 0.8, 1e-6, 8.0, True, True,
            "field enhancement gap-dependence coefficient",
        ),
        "gamma0": ParameterSpec(
            "gamma0", 16.0, 0.1, 40.0, True, True,
            "positive-branch field enhancement coefficient in uploaded code",
        ),
        # Usually fixed. Keep available for model card and for optional experiments.
        "Ea": ParameterSpec("Ea", 0.6, 0.2, 1.0, False, False, "activation energy; weakly identifiable from nominal DC"),
        "Rth": ParameterSpec("Rth", 2.1e3, 1e2, 1e6, True, False, "thermal resistance; usually fixed"),
        "tox": ParameterSpec("tox", 7.5e-9, 1e-9, 30e-9, True, False, "oxide thickness; should be measured/fixed"),
        "a0": ParameterSpec("a0", 0.25e-9, 0.05e-9, 1e-9, True, False, "atomic spacing; fixed"),
        "gap_min": ParameterSpec("gap_min", 2e-10, 0.05e-10, 10e-10, True, False, "minimum gap; fixed initially"),
        "gap_max": ParameterSpec("gap_max", 17e-10, 2e-10, 40e-10, True, False, "maximum gap; fixed initially"),
        "T_ini": ParameterSpec("T_ini", 298.0, 250.0, 400.0, False, False, "ambient temperature; fixed"),
        "F_min": ParameterSpec("F_min", 1.4e9, 0.2e9, 3.0e9, True, include_fmin, "threshold field gate; optional"),
        "time_step": ParameterSpec("time_step", 1e-9, 1e-13, 1e-6, True, False, "HSPICE bound step; solver control"),
    }
    return specs


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def finite_float(x: Any, default: float = np.nan) -> float:
    try:
        y = float(x)
        return y if math.isfinite(y) else default
    except Exception:
        return default


def safe_log10_abs(i: np.ndarray, floor: float = 1e-13) -> np.ndarray:
    return np.log10(np.maximum(np.abs(i), floor))


def huber(x: np.ndarray, delta: float = 1.0) -> np.ndarray:
    ax = np.abs(x)
    return np.where(ax <= delta, 0.5 * x * x, delta * (ax - 0.5 * delta))


def robust_mean(values: np.ndarray, default: float = np.inf) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return default
    return float(np.mean(values))


def interpolate_unique(x: np.ndarray, y: np.ndarray, xnew: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xnew = np.asarray(xnew, dtype=float)
    keep = np.isfinite(x) & np.isfinite(y)
    x = x[keep]
    y = y[keep]
    if len(x) < 2:
        return np.full_like(xnew, np.nan, dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    ux, inv = np.unique(x, return_inverse=True)
    uy = np.zeros_like(ux, dtype=float)
    for k in range(len(ux)):
        uy[k] = np.median(y[inv == k])
    if len(ux) < 2:
        return np.full_like(xnew, np.nan, dtype=float)
    out = np.full_like(xnew, np.nan, dtype=float)
    mask = (xnew >= ux.min()) & (xnew <= ux.max())
    out[mask] = np.interp(xnew[mask], ux, uy)
    return out


def find_nearest_value(x: np.ndarray, y: np.ndarray, x0: float) -> float:
    out = interpolate_unique(x, y, np.array([x0], dtype=float))[0]
    return float(out) if math.isfinite(out) else np.nan


def estimate_threshold_current(v: np.ndarray, iabs: np.ndarray, branch: str, threshold: float) -> float:
    v = np.asarray(v, dtype=float)
    iabs = np.asarray(iabs, dtype=float)
    keep = np.isfinite(v) & np.isfinite(iabs)
    v = v[keep]
    iabs = iabs[keep]
    if len(v) < 5:
        return np.nan

    # Use path order, not sorted order. For SET, crossing upward; for RESET, often crossing downward.
    if branch.upper() == "SET":
        mask = iabs >= threshold
        if np.any(mask):
            return float(v[np.argmax(mask)])
    elif branch.upper() == "RESET":
        # RESET branch may start LRS/high current and drop. Use first point below threshold after being high.
        high_seen = False
        for vv, ii in zip(v, iabs):
            if ii >= threshold:
                high_seen = True
            if high_seen and ii < threshold:
                return float(vv)
        # fallback: max derivative threshold below.
    else:
        mask = iabs >= threshold
        if np.any(mask):
            return float(v[np.argmax(mask)])
    return np.nan


def estimate_threshold_derivative(v: np.ndarray, logi: np.ndarray, branch: str) -> float:
    v = np.asarray(v, dtype=float)
    logi = np.asarray(logi, dtype=float)
    keep = np.isfinite(v) & np.isfinite(logi)
    v = v[keep]
    logi = logi[keep]
    if len(v) < 7:
        return np.nan
    # Smooth slightly with moving median/mean to reduce digitization noise.
    n = len(logi)
    win = max(3, min(11, (n // 20) * 2 + 1))
    if win >= 3:
        pad = win // 2
        padded = np.pad(logi, (pad, pad), mode="edge")
        sm = np.array([np.median(padded[k:k + win]) for k in range(n)])
    else:
        sm = logi
    dv = np.gradient(v)
    dy = np.gradient(sm)
    deriv = np.divide(dy, dv, out=np.zeros_like(dy), where=np.abs(dv) > 1e-15)
    if branch.upper() == "SET":
        idx = int(np.nanargmax(deriv))
    elif branch.upper() == "RESET":
        # Depending on path and sign, reset transition is often the strongest magnitude derivative.
        idx = int(np.nanargmax(np.abs(deriv)))
    else:
        idx = int(np.nanargmax(np.abs(deriv)))
    return float(v[idx])


def estimate_width_20_80(v: np.ndarray, logi: np.ndarray, branch: str) -> float:
    v = np.asarray(v, dtype=float)
    logi = np.asarray(logi, dtype=float)
    keep = np.isfinite(v) & np.isfinite(logi)
    v = v[keep]
    logi = logi[keep]
    if len(v) < 7:
        return np.nan
    lo = np.nanpercentile(logi, 20)
    hi = np.nanpercentile(logi, 80)
    if not np.isfinite(lo) or not np.isfinite(hi) or abs(hi - lo) < 1e-6:
        return np.nan
    if branch.upper() == "SET":
        m20 = np.where(logi >= lo)[0]
        m80 = np.where(logi >= hi)[0]
    else:
        # RESET may decrease; use magnitude transition region between 80 and 20 percentiles.
        m20 = np.where(logi <= hi)[0]
        m80 = np.where(logi <= lo)[0]
    if len(m20) == 0 or len(m80) == 0:
        return np.nan
    return float(abs(v[m80[0]] - v[m20[0]]))


def parameter_hash(params: dict[str, float], stage: str) -> str:
    items = sorted((k, float(v)) for k, v in params.items())
    payload = json.dumps({"stage": stage, "params": items}, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def write_json(path: Path, obj: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


# -----------------------------------------------------------------------------
# Optional use of user's step 01 and step 02 scripts verbatim
# -----------------------------------------------------------------------------


def run_existing_preprocessing(args) -> Path:
    """Call the user's uploaded scripts exactly through subprocess."""
    raw_dir = Path(args.raw_data_dir).expanduser().resolve()
    step01_script = Path(args.step01_script).expanduser().resolve()
    step02_script = Path(args.step02_script).expanduser().resolve()
    out = Path(args.output_dir).expanduser().resolve()
    step01_dir = out / "step01_from_raw"
    step02_dir = out / "step02_from_raw"

    if not raw_dir.exists():
        raise FileNotFoundError(f"raw data folder not found: {raw_dir}")
    if not step01_script.exists():
        raise FileNotFoundError(f"step01 script not found: {step01_script}")
    if not step02_script.exists():
        raise FileNotFoundError(f"step02 script not found: {step02_script}")

    mkdir(out)
    print("\n[preprocess] Running your existing step 01 script verbatim...")
    cmd1 = [sys.executable, str(step01_script), str(raw_dir), "--output-dir", str(step01_dir)]
    if args.recursive:
        cmd1.append("--recursive")
    print(" ".join(map(str, cmd1)))
    subprocess.run(cmd1, check=True)

    print("\n[preprocess] Running your existing step 02 script verbatim...")
    cmd2 = [
        sys.executable, str(step02_script),
        "--step01-dir", str(step01_dir),
        "--output-dir", str(step02_dir),
        "--representative-mode", args.representative_mode,
        "--min-overlap-cycles", str(args.min_overlap_cycles),
        "--vread", str(args.vread),
        "--switch-current-threshold", str(args.switch_current_threshold),
    ]
    if args.condition:
        cmd2.extend(["--condition", args.condition])
    if args.device_id:
        cmd2.extend(["--device-id", args.device_id])
    print(" ".join(map(str, cmd2)))
    subprocess.run(cmd2, check=True)

    rep_files = sorted(step02_dir.glob("*_representative_curve_FIXED.csv"))
    if not rep_files:
        raise RuntimeError(f"No representative curve CSV found in {step02_dir}")
    # If multiple files, choose latest modified.
    rep_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return rep_files[0]


# -----------------------------------------------------------------------------
# Target loading
# -----------------------------------------------------------------------------


def load_targets(rep_csv: Path, args) -> dict[str, TargetBranch]:
    rep_csv = Path(rep_csv).expanduser().resolve()
    if not rep_csv.exists():
        raise FileNotFoundError(rep_csv)
    df = pd.read_csv(rep_csv)

    required = {"branch", "voltage_V"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Representative CSV missing required columns: {missing}")

    # Determine measured current column.
    if "median_current_A" in df.columns:
        current_col = "median_current_A"
    elif "current_A" in df.columns:
        current_col = "current_A"
    elif "median_abs_current_A" in df.columns:
        current_col = "median_abs_current_A"
    else:
        raise ValueError("Could not find current column: expected median_current_A/current_A/median_abs_current_A")

    # For medoid-cycle output, preserve path order using representative_point_index or butterfly_sequence_index.
    sort_cols = []
    if "branch" in df.columns:
        sort_cols.append("branch")
    if "representative_point_index" in df.columns:
        sort_cols.append("representative_point_index")
    elif "butterfly_sequence_index" in df.columns:
        sort_cols.append("butterfly_sequence_index")
    elif "voltage_V" in df.columns:
        sort_cols.append("voltage_V")

    targets: dict[str, TargetBranch] = {}
    for branch in ["SET", "RESET"]:
        g = df[df["branch"].astype(str).str.upper() == branch].copy()
        if len(g) == 0:
            continue
        if sort_cols:
            local_sort = [c for c in sort_cols if c in g.columns and c != "branch"]
            if local_sort:
                g = g.sort_values(local_sort, kind="stable")

        v = g["voltage_V"].to_numpy(float)
        cur = g[current_col].to_numpy(float)
        if current_col == "median_abs_current_A":
            # No sign available; sign is not needed for log-absolute objective.
            cur = np.abs(cur)
        abs_i = np.abs(cur)
        log_i = safe_log10_abs(abs_i, args.current_floor)

        # Measurement uncertainty weights from q25/q75 log current if available.
        if {"q25_log10_abs_current", "q75_log10_abs_current"}.issubset(g.columns):
            iqr = (g["q75_log10_abs_current"].to_numpy(float) - g["q25_log10_abs_current"].to_numpy(float))
            iqr = np.maximum(iqr, 0.05)
            weights = 1.0 / iqr
            weights = weights / np.nanmedian(weights[np.isfinite(weights)])
            weights = np.clip(weights, 0.2, 5.0)
        else:
            weights = np.ones_like(v, dtype=float)

        # Down-weight likely compliance plateaus if requested.
        if args.compliance_current > 0:
            comp = float(args.compliance_current)
            plateau = abs_i >= 0.98 * comp
            weights[plateau] *= args.compliance_weight

        vth_i = estimate_threshold_current(v, abs_i, branch, args.switch_current_threshold)
        vth_d = estimate_threshold_derivative(v, log_i, branch)
        width = estimate_width_20_80(v, log_i, branch)
        iread = find_nearest_value(v, abs_i, args.vread if branch == "SET" else -abs(args.vread))
        if not np.isfinite(iread):
            # fallback to +vread for either branch if negative not present
            iread = find_nearest_value(v, abs_i, args.vread)

        targets[branch] = TargetBranch(
            branch=branch,
            voltage=v,
            current=cur,
            abs_current=abs_i,
            log_abs_current=log_i,
            weights=weights,
            source_df=g,
            vread=args.vread,
            threshold_current=args.switch_current_threshold,
            vth_current=vth_i,
            vth_derivative=vth_d,
            width_20_80=width,
            iread_abs=iread,
        )

    if not targets:
        raise RuntimeError("No SET/RESET target branches found in representative CSV")
    return targets


# -----------------------------------------------------------------------------
# Initial seed estimation
# -----------------------------------------------------------------------------


def estimate_initial_seed(targets: dict[str, TargetBranch], specs: dict[str, ParameterSpec], args) -> dict[str, float]:
    seed = {name: spec.default for name, spec in specs.items()}

    gap_min = seed["gap_min"]
    gap_max = seed["gap_max"]

    # Estimate HRS from SET branch near +vread, LRS from RESET branch near -vread.
    hrs = np.nan
    lrs = np.nan
    if "SET" in targets:
        hrs = find_nearest_value(targets["SET"].voltage, targets["SET"].abs_current, abs(args.vread))
    if "RESET" in targets:
        lrs = find_nearest_value(targets["RESET"].voltage, targets["RESET"].abs_current, -abs(args.vread))
        if not np.isfinite(lrs):
            lrs = find_nearest_value(targets["RESET"].voltage, targets["RESET"].abs_current, abs(args.vread))

    if np.isfinite(hrs) and np.isfinite(lrs) and hrs > args.current_floor and lrs > args.current_floor:
        ratio = max(lrs / hrs, 1.5)
        g0_seed = (gap_max - gap_min) / max(math.log(ratio), 1e-6)
        seed["g0"] = float(np.clip(g0_seed, specs["g0"].lo, specs["g0"].hi))

    # Estimate V0 from normalized non-switching current shape. Use a grid search.
    candidate_v0 = np.logspace(math.log10(specs["V0"].lo), math.log10(specs["V0"].hi), 80)
    best_v0 = seed["V0"]
    best_score = np.inf
    for v0 in candidate_v0:
        scores = []
        for branch, tb in targets.items():
            v = tb.voltage
            logi = tb.log_abs_current
            # Use lower-voltage, non-switching-ish subset.
            if branch == "SET":
                mask = (v >= 0) & (v <= np.nanpercentile(v[v >= 0], 45) if np.any(v >= 0) else False)
                vr = abs(args.vread)
            else:
                mask = (v <= 0) & (v >= np.nanpercentile(v[v <= 0], 55) if np.any(v <= 0) else False)
                vr = -abs(args.vread)
            if not np.any(mask):
                continue
            ir = find_nearest_value(v, logi, vr)
            if not np.isfinite(ir):
                continue
            model_shape = np.log10(np.maximum(np.abs(np.sinh(v[mask] / v0)), 1e-300))
            model_ref = math.log10(max(abs(math.sinh(vr / v0)), 1e-300))
            pred = model_shape - model_ref
            meas = logi[mask] - ir
            res = meas - pred
            scores.append(robust_mean(huber(res, delta=1.0)))
        if scores:
            sc = float(np.mean(scores))
            if sc < best_score:
                best_score = sc
                best_v0 = float(v0)
    seed["V0"] = float(np.clip(best_v0, specs["V0"].lo, specs["V0"].hi))

    # Estimate I0 from LRS read if possible.
    if np.isfinite(lrs) and lrs > args.current_floor:
        vr = abs(args.vread)
        denom = math.exp(-gap_min / seed["g0"]) * abs(math.sinh(vr / seed["V0"]))
        if denom > 0:
            seed["I0"] = float(np.clip(lrs / denom, specs["I0"].lo, specs["I0"].hi))

    # Estimate gamma0 from SET threshold and F_min gate if available.
    if "SET" in targets and np.isfinite(targets["SET"].vth_current) and abs(targets["SET"].vth_current) > 1e-6:
        vset = abs(float(targets["SET"].vth_current))
        gamma_seed = seed["F_min"] * seed["tox"] / max(vset, 1e-6) + seed["beta"] * (gap_max / 1e-9) ** 3
        seed["gamma0"] = float(np.clip(gamma_seed, specs["gamma0"].lo, specs["gamma0"].hi))

    # User overrides from JSON or CLI.
    if args.initial_params_json:
        with open(args.initial_params_json, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        for k, v in overrides.items():
            if k in seed:
                seed[k] = float(v)

    return seed


# -----------------------------------------------------------------------------
# HSPICE deck generation and parsing
# -----------------------------------------------------------------------------


def make_time_voltage_pwl(tb: TargetBranch, args) -> tuple[np.ndarray, np.ndarray, float]:
    v = np.asarray(tb.voltage, dtype=float)
    n = len(v)
    if n < 2:
        raise ValueError(f"not enough points for branch {tb.branch}")

    # Artificial time base: preserve point order. Vel0 is therefore tied to this sweep protocol.
    dt = float(args.pwl_dt)
    t = np.arange(n, dtype=float) * dt
    # Make sure first point exactly starts at 0 s.
    t[0] = 0.0
    return t, v, float(t[-1])


def format_pwl(t: np.ndarray, v: np.ndarray, max_pairs_per_line: int = 4) -> str:
    pairs = [f"{ti:.12e} {vi:.12e}" for ti, vi in zip(t, v)]
    lines = []
    for k in range(0, len(pairs), max_pairs_per_line):
        chunk = " ".join(pairs[k:k + max_pairs_per_line])
        prefix = "" if k == 0 else "+ "
        lines.append(prefix + chunk)
    return "\n".join(lines)


def copy_va_if_needed(va_path: Path, work_dir: Path) -> Path:
    va_path = Path(va_path).expanduser().resolve()
    if not va_path.exists():
        raise FileNotFoundError(va_path)
    suffix = ".va"
    dest = work_dir / (va_path.stem + suffix)
    text = va_path.read_text(encoding="utf-8", errors="replace")
    # If uploaded as .txt, write a .va copy for HSPICE.
    dest.write_text(text, encoding="utf-8")
    return dest


def generate_hspice_deck(
    deck_path: Path,
    va_file: Path,
    tb: TargetBranch,
    params: dict[str, float],
    specs: dict[str, ParameterSpec],
    args,
) -> None:
    t, v, tstop = make_time_voltage_pwl(tb, args)
    pwl = format_pwl(t, v)

    # Branch-specific initial condition.
    branch = tb.branch.upper()
    gap_ini = params.get("gap_max", specs["gap_max"].default) if branch == "SET" else params.get("gap_min", specs["gap_min"].default)

    # HSPICE parameter string. Keep model_switch=0 for nominal deterministic fitting.
    p = dict(params)
    p["gap_ini"] = gap_ini
    p["model_switch"] = 0
    p["deltaGap0"] = 0.0
    p["rand_seed_ini"] = 0
    p["time_step"] = args.time_step if args.time_step > 0 else max(args.pwl_dt / 10.0, 1e-12)

    # Ensure fixed defaults are supplied too. This avoids silent differences if model defaults change.
    for name, spec in specs.items():
        p.setdefault(name, spec.default)

    instance_params = [
        "model_switch={model_switch}",
        "g0={g0:.12e}",
        "V0={V0:.12e}",
        "Vel0={Vel0:.12e}",
        "I0={I0:.12e}",
        "beta={beta:.12e}",
        "gamma0={gamma0:.12e}",
        "Ea={Ea:.12e}",
        "a0={a0:.12e}",
        "T_ini={T_ini:.12e}",
        "F_min={F_min:.12e}",
        "gap_ini={gap_ini:.12e}",
        "gap_min={gap_min:.12e}",
        "gap_max={gap_max:.12e}",
        "Rth={Rth:.12e}",
        "tox={tox:.12e}",
        "deltaGap0={deltaGap0:.12e}",
        "rand_seed_ini={rand_seed_ini}",
        "time_step={time_step:.12e}",
    ]
    inst = " ".join(s.format(**p) for s in instance_params)

    tran_step = max(args.pwl_dt / 5.0, 1e-12)
    tstop2 = tstop + 2 * args.pwl_dt

    text = f"""
* Auto-generated Stanford RRAM extraction deck
* Branch: {branch}
* Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

.option accurate method=gear reltol=1e-5 abstol=1e-14 vntol=1e-8 nomod measdgt=8 numdgt=8
.option post=0
.hdl "{va_file}"

VDRV te 0 PWL(
{pwl}
+ )

XRRAM te 0 rram_v_1_0_0 {inst}

.tran {tran_step:.12e} {tstop2:.12e}
.print tran V(te) I(VDRV)
.end
"""
    deck_path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def is_float_token(tok: str) -> bool:
    tok = tok.strip().replace("D", "E").replace("d", "e")
    try:
        float(tok)
        return True
    except Exception:
        return False


def parse_float_token(tok: str) -> float:
    return float(tok.strip().replace("D", "E").replace("d", "e"))


def parse_hspice_lis(lis_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse HSPICE .lis table created by `.print tran V(te) I(VDRV)`.

    HSPICE .lis formats vary by version. This parser looks for a header line
    containing time plus V(te) and I(VDRV), then reads numeric rows. If your
    local HSPICE prints a different table style, adjust this function only.
    """
    if not lis_path.exists():
        raise FileNotFoundError(lis_path)

    lines = lis_path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[tuple[float, float, float]] = []
    in_table = False
    header_seen = False

    for line in lines:
        low = line.lower()
        # Common header variants include: time v(te) i(vdrv)
        compact_low = low.replace(" ", "")
        if ("time" in low) and ((("v(te" in compact_low) or ("vte" in compact_low)) and ("i(vdrv" in compact_low)):
            in_table = True
            header_seen = True
            continue

        if not in_table:
            continue

        stripped = line.strip()
        if not stripped:
            # HSPICE may have page breaks; do not immediately stop.
            continue
        if any(s in low for s in ["****", "analysis", "y-axis", "x-axis", "hspice", "job"]):
            continue

        toks = stripped.split()
        floats = [parse_float_token(tok) for tok in toks if is_float_token(tok)]
        if len(floats) >= 3:
            # Most often: time, v(te), i(vdrv). Sometimes an index column appears first.
            if len(floats) >= 4 and floats[0].is_integer() and floats[1] >= 0:
                cand = (floats[1], floats[2], floats[3])
            else:
                cand = (floats[0], floats[1], floats[2])
            # Basic sanity: time should be non-negative.
            if cand[0] >= -1e-30 and all(math.isfinite(x) for x in cand):
                rows.append(cand)
        else:
            # If table ended after data has started, stop.
            if rows and header_seen:
                # Do not break too aggressively; there can be page headers.
                pass

    if len(rows) < 3:
        # Fallback: find all numeric lines after any "time" header, less strict.
        rows = []
        in_table = False
        for line in lines:
            low = line.lower()
            if "time" in low and ("v(" in low or "i(" in low):
                in_table = True
                continue
            if not in_table:
                continue
            floats = [parse_float_token(tok) for tok in line.strip().split() if is_float_token(tok)]
            if len(floats) >= 3:
                if len(floats) >= 4 and floats[0].is_integer():
                    cand = (floats[1], floats[2], floats[3])
                else:
                    cand = (floats[0], floats[1], floats[2])
                if cand[0] >= -1e-30 and all(math.isfinite(x) for x in cand):
                    rows.append(cand)

    if len(rows) < 3:
        raise RuntimeError(f"Could not parse transient print table from {lis_path}")

    arr = np.asarray(rows, dtype=float)
    # Remove duplicate/nonmonotonic time rows conservatively.
    order = np.argsort(arr[:, 0], kind="stable")
    arr = arr[order]
    _, unique_idx = np.unique(arr[:, 0], return_index=True)
    arr = arr[np.sort(unique_idx)]
    return arr[:, 0], arr[:, 1], arr[:, 2]


def run_hspice(deck_path: Path, args) -> Path:
    deck_path = Path(deck_path).resolve()
    prefix = deck_path.with_suffix("")
    cmd = [args.hspice_bin, "-i", str(deck_path), "-o", str(prefix)]
    if args.verbose:
        print("[hspice]", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(deck_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=args.hspice_timeout,
    )
    # HSPICE usually writes prefix.lis.
    lis_path = prefix.with_suffix(".lis")
    if proc.returncode != 0:
        # Save stdout/stderr for debugging.
        (deck_path.parent / (deck_path.stem + ".stdout.txt")).write_text(proc.stdout or "", encoding="utf-8")
        (deck_path.parent / (deck_path.stem + ".stderr.txt")).write_text(proc.stderr or "", encoding="utf-8")
        raise RuntimeError(f"HSPICE failed with return code {proc.returncode}; see {deck_path.parent}")
    if not lis_path.exists():
        # Some versions may use .lis appended to output prefix.
        candidates = list(deck_path.parent.glob(deck_path.stem + "*.lis"))
        if candidates:
            lis_path = candidates[0]
        else:
            raise RuntimeError(f"HSPICE finished but .lis not found for {deck_path}")
    return lis_path


def simulate_branch(
    tb: TargetBranch,
    params: dict[str, float],
    specs: dict[str, ParameterSpec],
    va_file: Path,
    eval_dir: Path,
    args,
) -> SimulationResult:
    branch = tb.branch.upper()
    deck_path = eval_dir / f"sim_{branch}.sp"
    try:
        generate_hspice_deck(deck_path, va_file, tb, params, specs, args)
        if args.dry_run:
            return SimulationResult(ok=False, branch=branch, deck_path=str(deck_path), error="dry_run")
        lis_path = run_hspice(deck_path, args)
        t, v, cur_src = parse_hspice_lis(lis_path)
        # Current through voltage source is often opposite device current. Objective uses absolute current.
        iabs = np.abs(cur_src)
        logi = safe_log10_abs(iabs, args.current_floor)
        features = {
            "vth_current": estimate_threshold_current(v, iabs, branch, args.switch_current_threshold),
            "vth_derivative": estimate_threshold_derivative(v, logi, branch),
            "width_20_80": estimate_width_20_80(v, logi, branch),
            "iread_abs_pos": find_nearest_value(v, iabs, abs(args.vread)),
            "iread_abs_neg": find_nearest_value(v, iabs, -abs(args.vread)),
            "max_abs_current": float(np.nanmax(iabs)) if len(iabs) else np.nan,
            "min_abs_current": float(np.nanmin(iabs)) if len(iabs) else np.nan,
        }
        return SimulationResult(
            ok=True,
            branch=branch,
            time=t,
            voltage=v,
            current=cur_src,
            abs_current=iabs,
            log_abs_current=logi,
            features=features,
            deck_path=str(deck_path),
            lis_path=str(lis_path),
        )
    except Exception as exc:
        return SimulationResult(ok=False, branch=branch, deck_path=str(deck_path), error=str(exc))


# -----------------------------------------------------------------------------
# Objective and optimization
# -----------------------------------------------------------------------------


class StanfordRRAMFitter:
    def __init__(self, args, rep_csv: Path):
        self.args = args
        self.out = mkdir(Path(args.output_dir).expanduser().resolve())
        self.work = mkdir(self.out / "hspice_runs")
        self.rep_csv = Path(rep_csv).expanduser().resolve()
        self.targets = load_targets(self.rep_csv, args)
        self.specs = default_parameter_specs(include_fmin=args.fit_fmin)
        self.seed = estimate_initial_seed(self.targets, self.specs, args)
        self.va_file = copy_va_if_needed(Path(args.va), self.out)
        self.cache: dict[str, EvalResult] = {}
        self.progress_path = self.out / "03_fit_progress.csv"
        self._progress_header_written = False

        write_json(self.out / "00_initial_seed.json", self.seed)
        write_json(self.out / "00_parameter_specs.json", {
            k: {
                "default": v.default,
                "lo": v.lo,
                "hi": v.hi,
                "log_space": v.log_space,
                "fit": v.fit,
                "description": v.description,
            } for k, v in self.specs.items()
        })
        self._write_target_summary()

    def _write_target_summary(self) -> None:
        rows = []
        for branch, tb in self.targets.items():
            rows.append({
                "branch": branch,
                "n_points": len(tb.voltage),
                "v_min": float(np.nanmin(tb.voltage)),
                "v_max": float(np.nanmax(tb.voltage)),
                "i_min_abs": float(np.nanmin(tb.abs_current)),
                "i_max_abs": float(np.nanmax(tb.abs_current)),
                "vth_current": tb.vth_current,
                "vth_derivative": tb.vth_derivative,
                "width_20_80": tb.width_20_80,
                "iread_abs": tb.iread_abs,
            })
        pd.DataFrame(rows).to_csv(self.out / "00_target_summary.csv", index=False)

    def active_specs(self, names: Optional[list[str]] = None) -> dict[str, ParameterSpec]:
        if names is None:
            return {k: v for k, v in self.specs.items() if v.fit}
        return {k: self.specs[k] for k in names}

    def params_to_x(self, params: dict[str, float], names: list[str]) -> np.ndarray:
        return np.asarray([self.specs[n].to_internal(params[n]) for n in names], dtype=float)

    def x_to_params(self, x: np.ndarray, names: list[str], base: dict[str, float]) -> dict[str, float]:
        p = dict(base)
        for val, name in zip(x, names):
            spec = self.specs[name]
            lo, hi = spec.internal_bounds
            val = float(np.clip(val, lo, hi))
            p[name] = spec.from_internal(val)
        return p

    def bounds_for(self, names: list[str]) -> tuple[np.ndarray, np.ndarray]:
        lo = []
        hi = []
        for n in names:
            a, b = self.specs[n].internal_bounds
            lo.append(a)
            hi.append(b)
        return np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)

    def eval(self, params: dict[str, float], stage: str, branches: Optional[list[str]] = None) -> EvalResult:
        # Fill missing defaults.
        full_params = dict(self.seed)
        full_params.update({k: float(v) for k, v in params.items()})
        eval_id = parameter_hash(full_params, stage)
        if eval_id in self.cache:
            return self.cache[eval_id]

        eval_dir = mkdir(self.work / f"{stage}_{eval_id}")
        write_json(eval_dir / "params.json", full_params)

        if branches is None:
            branches = list(self.targets.keys())

        sim: dict[str, SimulationResult] = {}
        errors = []
        for branch in branches:
            if branch not in self.targets:
                continue
            sr = simulate_branch(self.targets[branch], full_params, self.specs, self.va_file, eval_dir, self.args)
            sim[branch] = sr
            if not sr.ok:
                errors.append(f"{branch}: {sr.error}")

        if errors:
            er = EvalResult(False, float(self.args.failure_loss), full_params, stage, sim, {}, "; ".join(errors), eval_id)
            self.cache[eval_id] = er
            self._append_progress(er)
            return er

        terms = self.compute_loss_terms(sim, branches)
        loss = float(sum(terms.values()))
        er = EvalResult(True, loss, full_params, stage, sim, terms, "", eval_id)
        self.cache[eval_id] = er
        self._append_progress(er)
        return er

    def compute_loss_terms(self, sim: dict[str, SimulationResult], branches: list[str]) -> dict[str, float]:
        args = self.args
        current_losses = []
        threshold_current_losses = []
        threshold_derivative_losses = []
        width_losses = []
        read_losses = []
        max_current_penalties = []

        for branch in branches:
            tb = self.targets[branch]
            sr = sim[branch]
            pred_log = interpolate_unique(sr.voltage, sr.log_abs_current, tb.voltage)
            mask = np.isfinite(pred_log) & np.isfinite(tb.log_abs_current) & np.isfinite(tb.weights)
            if np.any(mask):
                residual = pred_log[mask] - tb.log_abs_current[mask]
                val = robust_mean(tb.weights[mask] * huber(residual / args.log_current_scale, delta=args.huber_delta))
                current_losses.append(val)
            else:
                current_losses.append(args.failure_loss)

            # Threshold-current loss.
            if np.isfinite(tb.vth_current) and np.isfinite(sr.features.get("vth_current", np.nan)):
                threshold_current_losses.append(huber(np.array([(sr.features["vth_current"] - tb.vth_current) / args.vth_scale]), args.huber_delta)[0])

            # Derivative threshold loss.
            if np.isfinite(tb.vth_derivative) and np.isfinite(sr.features.get("vth_derivative", np.nan)):
                threshold_derivative_losses.append(huber(np.array([(sr.features["vth_derivative"] - tb.vth_derivative) / args.vth_scale]), args.huber_delta)[0])

            # Width loss.
            if np.isfinite(tb.width_20_80) and np.isfinite(sr.features.get("width_20_80", np.nan)) and tb.width_20_80 > 0:
                width_losses.append(huber(np.array([(sr.features["width_20_80"] - tb.width_20_80) / max(args.width_scale, 0.5 * tb.width_20_80)]), args.huber_delta)[0])

            # Read current loss at appropriate polarity.
            sim_iread = sr.features.get("iread_abs_pos", np.nan)
            if branch == "RESET" and np.isfinite(sr.features.get("iread_abs_neg", np.nan)):
                sim_iread = sr.features.get("iread_abs_neg", np.nan)
            if np.isfinite(tb.iread_abs) and np.isfinite(sim_iread) and tb.iread_abs > args.current_floor and sim_iread > args.current_floor:
                read_losses.append(huber(np.array([(math.log10(sim_iread) - math.log10(tb.iread_abs)) / args.log_current_scale]), args.huber_delta)[0])

            # Penalize runaway current if no compliance model is included.
            if args.max_sim_current > 0 and np.isfinite(sr.features.get("max_abs_current", np.nan)):
                mx = sr.features["max_abs_current"]
                if mx > args.max_sim_current:
                    max_current_penalties.append((math.log10(mx / args.max_sim_current)) ** 2)

        terms = {
            "L_current": args.w_current * robust_mean(np.asarray(current_losses), default=args.failure_loss),
            "L_vth_current": args.w_vth_current * robust_mean(np.asarray(threshold_current_losses), default=0.0),
            "L_vth_derivative": args.w_vth_derivative * robust_mean(np.asarray(threshold_derivative_losses), default=0.0),
            "L_width": args.w_width * robust_mean(np.asarray(width_losses), default=0.0),
            "L_read": args.w_read * robust_mean(np.asarray(read_losses), default=0.0),
            "L_max_current": args.w_penalty * robust_mean(np.asarray(max_current_penalties), default=0.0),
        }
        return terms

    def _append_progress(self, er: EvalResult) -> None:
        fieldnames = [
            "time", "eval_id", "stage", "ok", "loss", "error",
            "L_current", "L_vth_current", "L_vth_derivative", "L_width", "L_read", "L_max_current",
            "I0", "g0", "V0", "Vel0", "beta", "gamma0", "F_min", "Ea", "Rth", "tox", "gap_min", "gap_max",
        ]
        row = {k: "" for k in fieldnames}
        row.update({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "eval_id": er.eval_id,
            "stage": er.stage,
            "ok": er.ok,
            "loss": er.loss,
            "error": er.error,
        })
        for k, v in er.terms.items():
            if k in row:
                row[k] = v
        for k in ["I0", "g0", "V0", "Vel0", "beta", "gamma0", "F_min", "Ea", "Rth", "tox", "gap_min", "gap_max"]:
            if k in er.params:
                row[k] = er.params[k]
        write_header = not self.progress_path.exists() or not self._progress_header_written
        with self.progress_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
                self._progress_header_written = True
            writer.writerow(row)

    def sensitivity_audit(self, params: dict[str, float], names: list[str]) -> pd.DataFrame:
        rows = []
        base = self.eval(params, stage="sensitivity_base")
        base_features = self.extract_eval_features(base)
        for name in names:
            for factor in [0.9, 1.1]:
                pp = dict(params)
                pp[name] = float(np.clip(pp[name] * factor, self.specs[name].lo, self.specs[name].hi))
                er = self.eval(pp, stage=f"sensitivity_{name}_{factor:.2f}")
                feat = self.extract_eval_features(er)
                row = {"param": name, "factor": factor, "ok": er.ok, "loss": er.loss}
                for fk, fv in feat.items():
                    bv = base_features.get(fk, np.nan)
                    if np.isfinite(fv) and np.isfinite(bv):
                        row[f"d_{fk}"] = (fv - bv) / math.log(factor)
                    else:
                        row[f"d_{fk}"] = np.nan
                rows.append(row)
        df = pd.DataFrame(rows)
        df.to_csv(self.out / "01_exact_code_sensitivity_audit.csv", index=False)
        return df

    def extract_eval_features(self, er: EvalResult) -> dict[str, float]:
        out: dict[str, float] = {"loss": er.loss}
        if not er.ok:
            return out
        for branch, sr in er.sim.items():
            for k, v in sr.features.items():
                out[f"{branch}_{k}"] = float(v) if np.isfinite(v) else np.nan
        return out

    def optimize_group(
        self,
        base_params: dict[str, float],
        names: list[str],
        stage: str,
        branches: Optional[list[str]],
        rounds: int,
        candidates: int,
        radius0: float,
    ) -> EvalResult:
        rng = np.random.default_rng(self.args.seed + abs(hash(stage)) % 100000)
        x_best = self.params_to_x(base_params, names)
        lo, hi = self.bounds_for(names)
        x_best = np.clip(x_best, lo, hi)
        p_best = self.x_to_params(x_best, names, base_params)
        er_best = self.eval(p_best, stage=stage, branches=branches)
        radius = np.full_like(x_best, radius0, dtype=float)
        radius = np.minimum(radius, 0.33 * np.maximum(hi - lo, 1e-9))

        print(f"\n[optimize] Stage={stage} names={names} branches={branches or list(self.targets.keys())}")
        print(f"[optimize] Initial loss={er_best.loss:.6g}")

        for r in range(rounds):
            cand_x = [x_best.copy()]
            # Coordinate candidates.
            for j in range(len(names)):
                for sgn in [-1.0, 1.0]:
                    x = x_best.copy()
                    x[j] += sgn * radius[j]
                    cand_x.append(np.clip(x, lo, hi))
            # Random candidates.
            while len(cand_x) < candidates:
                step = rng.normal(0.0, 1.0, size=len(names)) * radius
                # Occasional uniform exploration inside current trust region.
                if rng.random() < 0.25:
                    step = rng.uniform(-1.0, 1.0, size=len(names)) * radius
                x = np.clip(x_best + step, lo, hi)
                cand_x.append(x)

            round_best = er_best
            round_best_x = x_best
            for x in cand_x:
                pp = self.x_to_params(x, names, base_params)
                er = self.eval(pp, stage=stage, branches=branches)
                if er.loss < round_best.loss:
                    round_best = er
                    round_best_x = x

            improved = round_best.loss < er_best.loss - self.args.min_improvement
            if improved:
                er_best = round_best
                x_best = round_best_x
                # update base so inactive fitted groups keep latest best values
                base_params = dict(er_best.params)
                radius *= self.args.radius_expand
            else:
                radius *= self.args.radius_shrink

            radius = np.minimum(radius, 0.5 * np.maximum(hi - lo, 1e-12))
            radius = np.maximum(radius, self.args.min_radius)
            print(
                f"[optimize] {stage} round {r+1:02d}/{rounds}: "
                f"best_loss={er_best.loss:.6g}, improved={improved}, radius_med={np.median(radius):.3g}"
            )

        return er_best

    def run(self) -> EvalResult:
        active_names = ["I0", "g0", "V0", "Vel0", "beta", "gamma0"]
        if self.args.fit_fmin:
            active_names.append("F_min")

        # Stage 0: exact-code sensitivity audit.
        if not self.args.skip_sensitivity:
            self.sensitivity_audit(self.seed, active_names)

        best_params = dict(self.seed)

        # Stage 1: amplitude/non-switching current shape.
        er_amp = self.optimize_group(
            best_params,
            names=["I0", "g0", "V0"],
            stage="stage1_amplitude",
            branches=list(self.targets.keys()),
            rounds=self.args.stage1_rounds,
            candidates=self.args.stage1_candidates,
            radius0=self.args.stage1_radius,
        )
        best_params.update(er_amp.params)

        # Stage 2: SET dynamics. gamma0 is meaningful for positive branch in uploaded code.
        if "SET" in self.targets:
            er_set = self.optimize_group(
                best_params,
                names=["Vel0", "beta", "gamma0"],
                stage="stage2_set",
                branches=["SET"],
                rounds=self.args.stage2_rounds,
                candidates=self.args.stage2_candidates,
                radius0=self.args.stage2_radius,
            )
            best_params.update(er_set.params)

        # Stage 3: RESET dynamics. gamma0 is hard-coded to 16 for Vtb < 0 in uploaded file, so do not fit it here.
        if "RESET" in self.targets:
            reset_names = ["Vel0", "beta"]
            if self.args.fit_fmin:
                reset_names.append("F_min")
            er_reset = self.optimize_group(
                best_params,
                names=reset_names,
                stage="stage3_reset",
                branches=["RESET"],
                rounds=self.args.stage3_rounds,
                candidates=self.args.stage3_candidates,
                radius0=self.args.stage3_radius,
            )
            best_params.update(er_reset.params)

        # Stage 4: joint refinement.
        er_joint = self.optimize_group(
            best_params,
            names=active_names,
            stage="stage4_joint",
            branches=list(self.targets.keys()),
            rounds=self.args.joint_rounds,
            candidates=self.args.joint_candidates,
            radius0=self.args.joint_radius,
        )

        self.save_final(er_joint)
        return er_joint

    def save_final(self, er: EvalResult) -> None:
        final_dir = mkdir(self.out / "final")
        write_json(final_dir / "best_params.json", er.params)
        write_json(final_dir / "best_loss_terms.json", er.terms)

        # HSPICE .param / instance parameter card.
        with (final_dir / "best_params_hspice.inc").open("w", encoding="utf-8") as f:
            f.write("* Best-fit nominal Stanford RRAM parameters\n")
            f.write("* Include or copy these values into your HSPICE deck.\n")
            for k in ["I0", "g0", "V0", "Vel0", "beta", "gamma0", "Ea", "a0", "T_ini", "F_min", "gap_min", "gap_max", "Rth", "tox"]:
                if k in er.params:
                    f.write(f".param {k} = {er.params[k]:.12e}\n")
            f.write(".param model_switch = 0\n")
            f.write(".param deltaGap0 = 0\n")

        # Save simulated curves interpolated and raw.
        rows = []
        feat_rows = []
        for branch, sr in er.sim.items():
            tb = self.targets[branch]
            pred_log = interpolate_unique(sr.voltage, sr.log_abs_current, tb.voltage)
            pred_abs = np.power(10.0, pred_log)
            for vv, im, ip, lm, lp in zip(tb.voltage, tb.abs_current, pred_abs, tb.log_abs_current, pred_log):
                rows.append({
                    "branch": branch,
                    "voltage_V": vv,
                    "meas_abs_current_A": im,
                    "sim_abs_current_A": ip,
                    "meas_log10_abs_current": lm,
                    "sim_log10_abs_current": lp,
                    "log_error_dec": lp - lm if np.isfinite(lp) else np.nan,
                })
            feat = {"branch": branch}
            feat.update({f"sim_{k}": v for k, v in sr.features.items()})
            feat.update({
                "meas_vth_current": tb.vth_current,
                "meas_vth_derivative": tb.vth_derivative,
                "meas_width_20_80": tb.width_20_80,
                "meas_iread_abs": tb.iread_abs,
            })
            feat_rows.append(feat)

        fit_df = pd.DataFrame(rows)
        fit_df.to_csv(final_dir / "final_fit_curve.csv", index=False)
        pd.DataFrame(feat_rows).to_csv(final_dir / "final_features.csv", index=False)

        self.plot_final(fit_df, final_dir)
        self.identifiability_summary(er, final_dir)

        print("\n[done] Final results saved to:", final_dir)
        print("[done] Best loss:", er.loss)
        print("[done] Best parameters:")
        for k in ["I0", "g0", "V0", "Vel0", "beta", "gamma0", "F_min", "Ea", "Rth", "tox", "gap_min", "gap_max"]:
            if k in er.params:
                print(f"  {k:10s} = {er.params[k]:.6e}")

    def plot_final(self, fit_df: pd.DataFrame, final_dir: Path) -> None:
        # Overlay plot.
        fig, ax = plt.subplots(figsize=(7.5, 5.2))
        for branch, g in fit_df.groupby("branch"):
            g = g.sort_values("voltage_V")
            ax.plot(g["voltage_V"], g["meas_abs_current_A"], linewidth=2.0, label=f"{branch} measured")
            ax.plot(g["voltage_V"], g["sim_abs_current_A"], "--", linewidth=2.0, label=f"{branch} simulated")
        ax.set_yscale("log")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("|Current| (A)")
        ax.grid(True, which="both", alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(final_dir / "final_overlay.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        # Residual plot.
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        for branch, g in fit_df.groupby("branch"):
            g = g.sort_values("voltage_V")
            ax.plot(g["voltage_V"], g["log_error_dec"], linewidth=1.6, label=branch)
        ax.axhline(0, linewidth=1.0)
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("log10 current error (decades)")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(final_dir / "final_log_error.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    def identifiability_summary(self, er: EvalResult, final_dir: Path) -> None:
        # Lightweight local identifiability: use sensitivity audit if available and boundary checks.
        rows = []
        active_names = ["I0", "g0", "V0", "Vel0", "beta", "gamma0"] + (["F_min"] if self.args.fit_fmin else [])
        for name in active_names:
            spec = self.specs[name]
            val = er.params[name]
            near_lo = val <= spec.lo * 1.05
            near_hi = val >= spec.hi / 1.05
            rows.append({
                "param": name,
                "value": val,
                "lower_bound": spec.lo,
                "upper_bound": spec.hi,
                "near_lower_bound": near_lo,
                "near_upper_bound": near_hi,
                "warning": "BOUNDARY" if (near_lo or near_hi) else "",
            })
        pd.DataFrame(rows).to_csv(final_dir / "identifiability_boundary_check.csv", index=False)

        # Write a readable notes file.
        with (final_dir / "reviewer_notes.txt").open("w", encoding="utf-8") as f:
            f.write("Identifiability notes for this nominal extraction\n")
            f.write("================================================\n\n")
            f.write("1. This fit uses model_switch=0 and deltaGap0=0; stochastic variability is not extracted.\n")
            f.write("2. gamma0 is not used as a RESET fitting knob because the uploaded Verilog-A code sets gamma_ini=16 when Vtb<0.\n")
            f.write("3. Vel0 is tied to the artificial PWL time base used here. Report pwl_dt if publishing Vel0.\n")
            f.write("4. Ea, Rth, gap_min, gap_max, tox, a0 are fixed by default because nominal DC I-V alone weakly identifies them.\n")
            f.write("5. If a fitted active parameter is close to a bound, treat it as a model-mismatch or weak-identifiability flag.\n")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Stage-wise HSPICE parameter extraction for uploaded Stanford RRAM model.",
    )

    # Input modes.
    p.add_argument("--rep-csv", type=Path, default=None,
                   help="Representative curve CSV from 02_select_device_representative_curve.py")
    p.add_argument("--raw-data-dir", type=Path, default=None,
                   help="Optional raw B1500 CSV folder. If given, calls your step01/step02 scripts verbatim.")
    p.add_argument("--step01-script", type=Path, default=Path("01_extract_clean_cycles.py"),
                   help="Path to your existing 01_extract_clean_cycles.py")
    p.add_argument("--step02-script", type=Path, default=Path("02_select_device_representative_curve.py"),
                   help="Path to your existing 02_select_device_representative_curve.py")
    p.add_argument("--recursive", action="store_true", help="Pass --recursive to step01 when using --raw-data-dir")
    p.add_argument("--representative-mode", default="medoid-cycle", choices=["medoid-cycle", "medoid-branch", "median-grid"])
    p.add_argument("--min-overlap-cycles", type=int, default=5)
    p.add_argument("--condition", default="", help="Optional condition passed to step02")
    p.add_argument("--device-id", default="", help="Optional device ID passed to step02")

    # HSPICE/model.
    p.add_argument("--va", type=Path, required=True, help="Path to Stanford Verilog-A file (.va or uploaded .txt)")
    p.add_argument("--hspice-bin", default="hspice", help="HSPICE executable name/path")
    p.add_argument("--hspice-timeout", type=float, default=120.0, help="Timeout in seconds per HSPICE run")
    p.add_argument("--output-dir", type=Path, default=Path("step03_stanford_fit"))
    p.add_argument("--dry-run", action="store_true", help="Generate decks but do not call HSPICE")
    p.add_argument("--verbose", action="store_true")

    # Target/reference settings.
    p.add_argument("--current-floor", type=float, default=1e-13)
    p.add_argument("--vread", type=float, default=0.1)
    p.add_argument("--switch-current-threshold", type=float, default=1e-6)
    p.add_argument("--compliance-current", type=float, default=0.0,
                   help="Known compliance current. If >0, plateau points are down-weighted.")
    p.add_argument("--compliance-weight", type=float, default=0.15)
    p.add_argument("--max-sim-current", type=float, default=0.2,
                   help="Penalty if simulated current exceeds this value; set <=0 to disable")

    # Time base.
    p.add_argument("--pwl-dt", type=float, default=1e-6,
                   help="Artificial time spacing between experimental voltage points in PWL source")
    p.add_argument("--time-step", type=float, default=0.0,
                   help="Override model time_step. Default uses pwl_dt/10.")

    # Objective weights/scales.
    p.add_argument("--w-current", type=float, default=1.0)
    p.add_argument("--w-vth-current", type=float, default=0.20)
    p.add_argument("--w-vth-derivative", type=float, default=0.10)
    p.add_argument("--w-width", type=float, default=0.10)
    p.add_argument("--w-read", type=float, default=0.25)
    p.add_argument("--w-penalty", type=float, default=1.0)
    p.add_argument("--log-current-scale", type=float, default=0.20,
                   help="Scale for log10 current residual; 0.20 means 0.2 decades roughly unit residual")
    p.add_argument("--vth-scale", type=float, default=0.10,
                   help="Voltage threshold error scale in V")
    p.add_argument("--width-scale", type=float, default=0.15,
                   help="Switching width error scale in V")
    p.add_argument("--huber-delta", type=float, default=1.5)
    p.add_argument("--failure-loss", type=float, default=1e6)

    # Optimization controls.
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--initial-params-json", type=Path, default=None,
                   help="Optional JSON with initial parameter overrides")
    p.add_argument("--fit-fmin", action="store_true", help="Also fit F_min. Not recommended unless needed.")
    p.add_argument("--skip-sensitivity", action="store_true")
    p.add_argument("--min-improvement", type=float, default=1e-5)
    p.add_argument("--radius-shrink", type=float, default=0.55)
    p.add_argument("--radius-expand", type=float, default=1.10)
    p.add_argument("--min-radius", type=float, default=0.01)

    p.add_argument("--stage1-rounds", type=int, default=5)
    p.add_argument("--stage1-candidates", type=int, default=18)
    p.add_argument("--stage1-radius", type=float, default=0.35)
    p.add_argument("--stage2-rounds", type=int, default=5)
    p.add_argument("--stage2-candidates", type=int, default=18)
    p.add_argument("--stage2-radius", type=float, default=0.35)
    p.add_argument("--stage3-rounds", type=int, default=5)
    p.add_argument("--stage3-candidates", type=int, default=18)
    p.add_argument("--stage3-radius", type=float, default=0.35)
    p.add_argument("--joint-rounds", type=int, default=8)
    p.add_argument("--joint-candidates", type=int, default=28)
    p.add_argument("--joint-radius", type=float, default=0.20)

    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.rep_csv is None and args.raw_data_dir is None:
        raise SystemExit("Provide either --rep-csv or --raw-data-dir")

    mkdir(Path(args.output_dir).expanduser().resolve())

    if args.raw_data_dir is not None:
        rep_csv = run_existing_preprocessing(args)
        print(f"[preprocess] Using representative CSV: {rep_csv}")
    else:
        rep_csv = Path(args.rep_csv).expanduser().resolve()

    fitter = StanfordRRAMFitter(args, rep_csv)
    if args.dry_run:
        print("[dry-run] Running one evaluation to generate decks only.")
        er = fitter.eval(fitter.seed, stage="dry_run_decks")
        print("Generated decks in:", fitter.work)
        return
    fitter.run()


if __name__ == "__main__":
    main()
