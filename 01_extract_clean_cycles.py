#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import numpy as np


TITLE_RE = re.compile(r"^AnalysisSetup,\s*Analysis\.Setup\.Title,\s*(.*)$")
DATA_RE = re.compile(r"^DataValue,\s*([^,]+)\s*,\s*([^,]+)\s*$", re.IGNORECASE)
RECORD_TIME_RE = re.compile(r"^MetaData,\s*TestRecord\.RecordTime,\s*(.*)$")
TARGET_RE = re.compile(r"^MetaData,\s*TestRecord\.TestTarget,\s*(.*)$")


@dataclass
class IVBlock:
    title: str
    voltage: np.ndarray
    current: np.ndarray


@dataclass
class CycleRecord:
    path: Path
    condition: str
    device_id: str
    test_name: str
    measurement_id: str
    record_time: datetime
    blocks: list[IVBlock]
    cycle_number: int = 0


def parse_datetime(value: str) -> Optional[datetime]:
    value = value.strip()
    formats = (
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%m_%d_%Y %I_%M_%S %p",
        "%m_%d_%Y %H_%M_%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def parse_filename_metadata(path: Path):
    stem = path.stem.strip()
    if stem.startswith("[") and stem.endswith("]"):
        stem = stem[1:-1]

    parts = [p.strip() for p in stem.split(",")]
    device_id = parts[0] if len(parts) >= 1 and parts[0] else path.stem
    test_name = parts[1] if len(parts) >= 2 else ""
    measurement_id = parts[2] if len(parts) >= 3 else ""
    timestamp = parse_datetime(parts[3]) if len(parts) >= 4 else None
    return device_id, test_name, measurement_id, timestamp


def read_csv_text(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def extract_record_time(lines: Iterable[str]) -> Optional[datetime]:
    for line in lines:
        m = RECORD_TIME_RE.match(line.strip())
        if m:
            t = parse_datetime(m.group(1))
            if t is not None:
                return t
    return None


def extract_target(lines: Iterable[str]) -> Optional[str]:
    for line in lines:
        m = TARGET_RE.match(line.strip())
        if m:
            target = m.group(1).strip()
            if target:
                return target
    return None


def extract_data_pairs(lines: Iterable[str]):
    voltage = []
    current = []

    for line in lines:
        m = DATA_RE.match(line.strip())
        if not m:
            continue
        try:
            v = float(m.group(1))
            i = float(m.group(2))
        except ValueError:
            continue

        if math.isfinite(v) and math.isfinite(i):
            voltage.append(v)
            current.append(i)

    return np.asarray(voltage, dtype=float), np.asarray(current, dtype=float)


def parse_b1500_csv(path: Path, condition: str) -> CycleRecord:
    lines = read_csv_text(path)

    filename_device, test_name, measurement_id, filename_time = parse_filename_metadata(path)
    metadata_device = extract_target(lines)

    record_time = extract_record_time(lines) or filename_time
    if record_time is None:
        record_time = datetime.fromtimestamp(path.stat().st_mtime)

    title_indices = []
    for idx, line in enumerate(lines):
        m = TITLE_RE.match(line.strip())
        if m:
            title_indices.append((idx, m.group(1).strip()))

    blocks = []
    if title_indices:
        for block_idx, (start, title) in enumerate(title_indices):
            end = title_indices[block_idx + 1][0] if block_idx + 1 < len(title_indices) else len(lines)
            v, i = extract_data_pairs(lines[start:end])
            if len(v):
                blocks.append(IVBlock(title=title or "Untitled", voltage=v, current=i))
    else:
        v, i = extract_data_pairs(lines)
        if len(v):
            blocks.append(IVBlock(title="All", voltage=v, current=i))

    return CycleRecord(
        path=path,
        condition=condition,
        device_id=metadata_device or filename_device,
        test_name=test_name,
        measurement_id=measurement_id,
        record_time=record_time,
        blocks=blocks,
    )


def infer_branch(title: str, voltage: np.ndarray) -> str:
    t = title.lower()

    if "reset" in t:
        return "RESET"
    if "set" in t:
        return "SET"

    if len(voltage) == 0:
        return "UNKNOWN"

    vmax = np.nanmax(voltage)
    vmin = np.nanmin(voltage)

    if vmax > abs(vmin):
        return "SET"
    if abs(vmin) > vmax:
        return "RESET"

    return "MIXED"


def safe_log10_abs_current(i: np.ndarray, floor: float):
    return np.log10(np.maximum(np.abs(i), floor))


def calc_dynamic_decades(i: np.ndarray, floor: float) -> float:
    abs_i = np.abs(i[np.isfinite(i)])
    abs_i = abs_i[abs_i > floor]

    if len(abs_i) < 5:
        return 0.0

    p05 = np.percentile(abs_i, 5)
    p95 = np.percentile(abs_i, 95)

    if p05 <= 0 or p95 <= 0:
        return 0.0

    return float(np.log10(p95 / p05))


def cycle_quality(cycle: CycleRecord, args) -> dict:
    all_v = []
    all_i = []
    branches = []

    for block in cycle.blocks:
        all_v.append(block.voltage)
        all_i.append(block.current)
        branches.append(infer_branch(block.title, block.voltage))

    if not all_v:
        return {
            "is_good": False,
            "quality_score": 0.0,
            "reject_reason": "no_data",
            "branch_list": "",
        }

    v = np.concatenate(all_v)
    i = np.concatenate(all_i)

    finite = np.isfinite(v) & np.isfinite(i)
    v = v[finite]
    i = i[finite]

    if len(v) < args.min_points:
        return {
            "is_good": False,
            "quality_score": 0.0,
            "reject_reason": "too_few_points",
            "branch_list": ";".join(sorted(set(branches))),
        }

    vmax = float(np.max(v))
    vmin = float(np.min(v))
    vspan = vmax - vmin

    abs_i = np.abs(i)
    max_abs_i = float(np.max(abs_i))
    median_abs_i = float(np.median(abs_i))
    dyn_dec = calc_dynamic_decades(i, args.current_floor)

    has_set = "SET" in branches or vmax >= args.min_abs_vmax
    has_reset = "RESET" in branches or vmin <= -args.min_abs_vmax

    reject = []

    if vspan < args.min_vspan:
        reject.append("low_voltage_span")
    if max_abs_i < args.min_peak_current:
        reject.append("weak_signal")
    if max_abs_i > args.max_peak_current:
        reject.append("too_high_current")
    if median_abs_i < args.current_floor:
        reject.append("mostly_floor_current")
    if dyn_dec < args.min_dynamic_decades:
        reject.append("low_dynamic_range")
    if args.require_set_reset and not (has_set and has_reset):
        reject.append("missing_set_or_reset")

    score = 0.0
    score += min(len(v) / max(args.min_points, 1), 2.0)
    score += min(vspan / max(args.min_vspan, 1e-12), 2.0)
    score += min(dyn_dec / max(args.min_dynamic_decades, 1e-12), 3.0)
    score += 1.0 if has_set else 0.0
    score += 1.0 if has_reset else 0.0

    is_good = len(reject) == 0

    return {
        "is_good": is_good,
        "quality_score": round(score, 4),
        "reject_reason": "accepted" if is_good else ";".join(reject),
        "branch_list": ";".join(sorted(set(branches))),
        "n_points": len(v),
        "v_min": vmin,
        "v_max": vmax,
        "v_span": vspan,
        "i_abs_min": float(np.min(abs_i)),
        "i_abs_median": median_abs_i,
        "i_abs_max": max_abs_i,
        "dynamic_decades": dyn_dec,
    }


def collect_cycles(folder: Path, recursive: bool) -> list[CycleRecord]:
    paths = sorted(folder.rglob("*.csv") if recursive else folder.glob("*.csv"))
    cycles = []

    for path in paths:
        condition = path.parent.name
        try:
            cycle = parse_b1500_csv(path, condition)
        except Exception as exc:
            print(f"SKIP: {path} | {exc}")
            continue

        if cycle.blocks:
            cycles.append(cycle)

    cycles.sort(key=lambda x: (x.condition, x.device_id, x.record_time, x.path.name))

    grouped = {}
    for c in cycles:
        key = (c.condition, c.device_id)
        grouped.setdefault(key, []).append(c)

    for group_cycles in grouped.values():
        group_cycles.sort(key=lambda x: (x.record_time, x.path.name))
        for idx, c in enumerate(group_cycles, start=1):
            c.cycle_number = idx

    return cycles


def write_outputs(cycles: list[CycleRecord], output_dir: Path, args):
    output_dir.mkdir(parents=True, exist_ok=True)

    points_path = output_dir / "01_extracted_points.csv"
    summary_path = output_dir / "01_cycle_summary.csv"
    device_path = output_dir / "01_device_summary.csv"

    summary_rows = []
    point_rows = []

    for cycle in cycles:
        q = cycle_quality(cycle, args)

        summary_rows.append({
            "condition": cycle.condition,
            "device_id": cycle.device_id,
            "cycle_id": cycle.cycle_number,
            "file": cycle.path.name,
            "record_time": cycle.record_time.isoformat(sep=" "),
            "test_name": cycle.test_name,
            "measurement_id": cycle.measurement_id,
            "is_good": q["is_good"],
            "quality_score": q["quality_score"],
            "reject_reason": q["reject_reason"],
            "branch_list": q["branch_list"],
            "n_points": q.get("n_points", ""),
            "v_min": q.get("v_min", ""),
            "v_max": q.get("v_max", ""),
            "v_span": q.get("v_span", ""),
            "i_abs_min": q.get("i_abs_min", ""),
            "i_abs_median": q.get("i_abs_median", ""),
            "i_abs_max": q.get("i_abs_max", ""),
            "dynamic_decades": q.get("dynamic_decades", ""),
            "path": str(cycle.path),
        })

        for block_id, block in enumerate(cycle.blocks, start=1):
            branch = infer_branch(block.title, block.voltage)

            for point_idx, (v, i) in enumerate(zip(block.voltage, block.current), start=1):
                if not np.isfinite(v) or not np.isfinite(i):
                    continue

                point_rows.append({
                    "condition": cycle.condition,
                    "device_id": cycle.device_id,
                    "cycle_id": cycle.cycle_number,
                    "block_id": block_id,
                    "block_title": block.title,
                    "branch": branch,
                    "point_index": point_idx,
                    "voltage_V": v,
                    "current_A": i,
                    "abs_current_A": abs(i),
                    "log10_abs_current": math.log10(max(abs(i), args.current_floor)),
                    "is_good_cycle": q["is_good"],
                    "quality_score": q["quality_score"],
                    "source_file": cycle.path.name,
                })

    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()) if summary_rows else [])
        if summary_rows:
            writer.writeheader()
            writer.writerows(summary_rows)

    with points_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(point_rows[0].keys()) if point_rows else [])
        if point_rows:
            writer.writeheader()
            writer.writerows(point_rows)

    device_stats = {}
    for row in summary_rows:
        key = (row["condition"], row["device_id"])
        device_stats.setdefault(key, {
            "condition": row["condition"],
            "device_id": row["device_id"],
            "total_cycles": 0,
            "good_cycles": 0,
            "mean_quality_score": [],
        })

        device_stats[key]["total_cycles"] += 1
        device_stats[key]["good_cycles"] += int(row["is_good"])
        device_stats[key]["mean_quality_score"].append(float(row["quality_score"]))

    device_rows = []
    for item in device_stats.values():
        scores = item.pop("mean_quality_score")
        item["mean_quality_score"] = round(float(np.mean(scores)), 4) if scores else 0.0
        item["good_fraction"] = round(item["good_cycles"] / item["total_cycles"], 4) if item["total_cycles"] else 0.0
        device_rows.append(item)

    device_rows.sort(key=lambda x: (-x["good_cycles"], -x["mean_quality_score"], x["device_id"]))

    with device_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(device_rows[0].keys()) if device_rows else [])
        if device_rows:
            writer.writeheader()
            writer.writerows(device_rows)

    print(f"Saved: {points_path}")
    print(f"Saved: {summary_path}")
    print(f"Saved: {device_path}")

    if device_rows:
        best = device_rows[0]
        print(f"Best device: {best['condition']} | {best['device_id']} | good_cycles={best['good_cycles']}")


def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--output-dir", type=Path, default=Path("fit_step01_output"))

    p.add_argument("--current-floor", type=float, default=1e-13)
    p.add_argument("--min-points", type=int, default=40)
    p.add_argument("--min-vspan", type=float, default=1.0)
    p.add_argument("--min-abs-vmax", type=float, default=0.5)
    p.add_argument("--min-peak-current", type=float, default=1e-9)
    p.add_argument("--max-peak-current", type=float, default=1.0)
    p.add_argument("--min-dynamic-decades", type=float, default=0.5)
    p.add_argument("--no-require-set-reset", dest="require_set_reset", action="store_false")
    p.set_defaults(require_set_reset=True)

    return p


def main():
    args = build_parser().parse_args()

    folder = args.folder.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    cycles = collect_cycles(folder, args.recursive)

    if not cycles:
        print("No valid CSV cycles found.")
        return

    write_outputs(cycles, output_dir, args)


if __name__ == "__main__":
    main()