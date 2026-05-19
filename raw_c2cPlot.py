#!/usr/bin/env python3
"""Plot raw SET-RESET RRAM I-V cycles grouped by device.

This is a Python equivalent of raw_c2cPlot.m for Keysight/B1500-style CSVs.
Each CSV is treated as one SET-RESET cycle. Files are grouped by device ID
parsed from names like:

    [A8-04-4um-01,SET-RESET,2,8_30_2024 2_15_03 PM].csv

Outputs are written once per processed folder:
    <folder_name>_IV.png
    <folder_name>_summary.csv
"""

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


MPLCONFIGDIR = Path(os.environ.get("MPLCONFIGDIR", "/tmp/matplotlib"))
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


TITLE_RE = re.compile(r"^AnalysisSetup,\s*Analysis\.Setup\.Title,\s*(.*)$")
DATA_RE = re.compile(
    r"^DataValue,\s*([^,]+)\s*,\s*([^,]+)\s*$", re.IGNORECASE
)
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


def parse_filename_metadata(path: Path) -> tuple[str, str, str, Optional[datetime]]:
    """Return device_id, test_name, measurement_id, timestamp parsed from filename."""
    stem = path.stem.strip()
    if stem.startswith("[") and stem.endswith("]"):
        stem = stem[1:-1]

    parts = [part.strip() for part in stem.split(",")]
    device_id = parts[0] if len(parts) >= 1 and parts[0] else path.stem
    test_name = parts[1] if len(parts) >= 2 else ""
    measurement_id = parts[2] if len(parts) >= 3 else ""
    timestamp = parse_datetime(parts[3]) if len(parts) >= 4 else None
    return device_id, test_name, measurement_id, timestamp


def read_csv_text(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def extract_record_time(lines: Iterable[str]) -> Optional[datetime]:
    for line in lines:
        match = RECORD_TIME_RE.match(line.strip())
        if match:
            parsed = parse_datetime(match.group(1))
            if parsed is not None:
                return parsed
    return None


def extract_target(lines: Iterable[str]) -> Optional[str]:
    for line in lines:
        match = TARGET_RE.match(line.strip())
        if match:
            target = match.group(1).strip()
            if target:
                return target
    return None


def extract_data_pairs(lines: Iterable[str]) -> tuple[np.ndarray, np.ndarray]:
    voltage: list[float] = []
    current: list[float] = []

    for line in lines:
        match = DATA_RE.match(line.strip())
        if not match:
            continue
        try:
            v = float(match.group(1))
            i = float(match.group(2))
        except ValueError:
            continue
        if math.isfinite(v) and math.isfinite(i):
            voltage.append(v)
            current.append(i)

    return np.asarray(voltage, dtype=float), np.asarray(current, dtype=float)


def parse_b1500_set_reset_csv(path: Path) -> CycleRecord:
    lines = read_csv_text(path)
    filename_device, test_name, measurement_id, filename_time = parse_filename_metadata(path)
    metadata_device = extract_target(lines)
    record_time = extract_record_time(lines) or filename_time
    if record_time is None:
        record_time = datetime.fromtimestamp(path.stat().st_mtime)

    title_indices: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = TITLE_RE.match(line.strip())
        if match:
            title_indices.append((index, match.group(1).strip()))

    blocks: list[IVBlock] = []
    if title_indices:
        for block_index, (start, title) in enumerate(title_indices):
            end = (
                title_indices[block_index + 1][0]
                if block_index + 1 < len(title_indices)
                else len(lines)
            )
            voltage, current = extract_data_pairs(lines[start:end])
            if len(voltage):
                blocks.append(IVBlock(title=title or "Untitled", voltage=voltage, current=current))
    else:
        voltage, current = extract_data_pairs(lines)
        if len(voltage):
            blocks.append(IVBlock(title="All", voltage=voltage, current=current))

    return CycleRecord(
        path=path,
        device_id=metadata_device or filename_device,
        test_name=test_name,
        measurement_id=measurement_id,
        record_time=record_time,
        blocks=blocks,
    )


def lighten_rgb(rgb: tuple[float, float, float], amount: float) -> tuple[float, float, float]:
    """Blend rgb toward white. amount=0 keeps rgb; amount=1 returns white."""
    return tuple((1.0 - amount) * channel + amount for channel in rgb)


def safe_filename_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe.strip("._") or "selected_device"


def collect_cycles(folder: Path) -> list[CycleRecord]:
    cycles = []
    for path in sorted(folder.glob("*.csv")):
        try:
            cycle = parse_b1500_set_reset_csv(path)
        except OSError as exc:
            print(f"Skipping {path}: {exc}")
            continue
        if cycle.blocks:
            cycles.append(cycle)

    cycles.sort(key=lambda item: (item.device_id, item.record_time, item.path.name))

    grouped: dict[str, list[CycleRecord]] = {}
    for cycle in cycles:
        grouped.setdefault(cycle.device_id, []).append(cycle)

    for device_cycles in grouped.values():
        device_cycles.sort(key=lambda item: (item.record_time, item.path.name))
        for index, cycle in enumerate(device_cycles, start=1):
            cycle.cycle_number = index

    return cycles


def plot_folder_iv(
    folder: Path,
    cycles: list[CycleRecord],
    output_path: Path,
    yscale: str,
    use_abs_current: bool = False,
    use_abs_voltage: bool = False,
    current_floor: Optional[float] = None,
    symlog_linthresh: float = 1e-12,
    xlim: Optional[tuple[float, float]] = (-5.0, 5.0),
    dpi: int = 300,
) -> None:
    grouped: dict[str, list[CycleRecord]] = {}
    for cycle in cycles:
        grouped.setdefault(cycle.device_id, []).append(cycle)

    device_ids = sorted(grouped)
    color_map = plt.get_cmap("tab20", max(len(device_ids), 1))

    fig, ax = plt.subplots(figsize=(9.0, 6.5), facecolor="white")
    legend_handles: list[Line2D] = []

    for device_index, device_id in enumerate(device_ids):
        device_cycles = sorted(
            grouped[device_id], key=lambda item: (item.record_time, item.path.name)
        )
        base_color = color_map(device_index)[:3]

        for cycle_index, cycle in enumerate(device_cycles):
            if len(device_cycles) == 1:
                shade = 0.0
            else:
                shade = 0.58 * (1.0 - cycle_index / (len(device_cycles) - 1))
            color = lighten_rgb(base_color, shade)
            alpha = 0.40 if cycle_index < len(device_cycles) - 1 else 0.92
            linewidth = 0.75 if cycle_index < len(device_cycles) - 1 else 1.45

            for block in cycle.blocks:
                voltage = np.abs(block.voltage) if use_abs_voltage else block.voltage.copy()
                current = np.abs(block.current) if use_abs_current else block.current.copy()

                if yscale == "log":
                    bad = ~np.isfinite(current) | (current <= 0)
                    current = current.astype(float, copy=True)
                    if current_floor is None:
                        current[bad] = np.nan
                    else:
                        current[bad] = current_floor
                else:
                    good = np.isfinite(voltage) & np.isfinite(current)
                    voltage = voltage[good]
                    current = current[good]

                ax.plot(voltage, current, color=color, alpha=alpha, linewidth=linewidth)

        legend_handles.append(
            Line2D([0], [0], color=base_color, lw=2.0, label=f"{device_id} (n={len(device_cycles)})")
        )

    ax.set_xlabel("|Voltage| (V)" if use_abs_voltage else "Voltage (V)")
    ax.set_ylabel("|Current| (A)" if use_abs_current else "Current (A)")
    scale_label = "signed log" if yscale == "symlog" else yscale
    ax.set_title(
        f"Set-Reset I-V ({scale_label}): {folder.name} "
        f"({len(device_ids)} devices, {len(cycles)} cycles)"
    )
    if yscale == "symlog":
        ax.set_yscale("symlog", linthresh=symlog_linthresh)
    else:
        ax.set_yscale(yscale)
    ax.grid(True, which="both", alpha=0.25)
    ax.minorticks_on()
    if xlim is not None:
        ax.set_xlim(*xlim)

    if len(legend_handles) <= 16:
        ax.legend(handles=legend_handles, loc="best", fontsize=8, frameon=False)
    else:
        ax.legend(
            handles=legend_handles,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=7,
            frameon=False,
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def write_summary_csv(folder: Path, cycles: list[CycleRecord], output_path: Path) -> None:
    grouped: dict[str, list[CycleRecord]] = {}
    for cycle in cycles:
        grouped.setdefault(cycle.device_id, []).append(cycle)

    total_devices = len(grouped)
    total_cycles = len(cycles)
    rows = []

    for device_id in sorted(grouped):
        device_cycles = sorted(
            grouped[device_id], key=lambda item: (item.record_time, item.path.name)
        )
        set_blocks = sum(
            1 for cycle in device_cycles for block in cycle.blocks if is_block_title(block.title, "set")
        )
        reset_blocks = sum(
            1 for cycle in device_cycles for block in cycle.blocks if is_block_title(block.title, "reset")
        )
        total_blocks = sum(len(cycle.blocks) for cycle in device_cycles)
        rows.append(
            {
                "folder": str(folder),
                "device_id": device_id,
                "cycle_count": len(device_cycles),
                "cycle_delta_from_20": len(device_cycles) - 20,
                "total_blocks": total_blocks,
                "set_blocks": set_blocks,
                "reset_blocks": reset_blocks,
                "first_record_time": device_cycles[0].record_time.isoformat(sep=" "),
                "last_record_time": device_cycles[-1].record_time.isoformat(sep=" "),
                "first_file": device_cycles[0].path.name,
                "last_file": device_cycles[-1].path.name,
                "measurement_ids": ";".join(
                    sorted({cycle.measurement_id for cycle in device_cycles if cycle.measurement_id})
                ),
                "total_devices_in_folder": total_devices,
                "total_cycles_in_folder": total_cycles,
            }
        )

    total_row = {
        "folder": str(folder),
        "device_id": "ALL_DEVICES",
        "cycle_count": total_cycles,
        "cycle_delta_from_20": "",
        "total_blocks": sum(len(cycle.blocks) for cycle in cycles),
        "set_blocks": sum(1 for cycle in cycles for block in cycle.blocks if is_block_title(block.title, "set")),
        "reset_blocks": sum(
            1 for cycle in cycles for block in cycle.blocks if is_block_title(block.title, "reset")
        ),
        "first_record_time": min((cycle.record_time for cycle in cycles), default=""),
        "last_record_time": max((cycle.record_time for cycle in cycles), default=""),
        "first_file": "",
        "last_file": "",
        "measurement_ids": "",
        "total_devices_in_folder": total_devices,
        "total_cycles_in_folder": total_cycles,
    }
    if isinstance(total_row["first_record_time"], datetime):
        total_row["first_record_time"] = total_row["first_record_time"].isoformat(sep=" ")
    if isinstance(total_row["last_record_time"], datetime):
        total_row["last_record_time"] = total_row["last_record_time"].isoformat(sep=" ")
    rows.append(total_row)

    fieldnames = [
        "folder",
        "device_id",
        "cycle_count",
        "cycle_delta_from_20",
        "total_blocks",
        "set_blocks",
        "reset_blocks",
        "first_record_time",
        "last_record_time",
        "first_file",
        "last_file",
        "measurement_ids",
        "total_devices_in_folder",
        "total_cycles_in_folder",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_block_title(title: str, target: str) -> bool:
    return re.search(rf"\b{re.escape(target.lower())}\b", title.lower()) is not None


def folders_with_csv(root: Path) -> list[Path]:
    folders = {path.parent for path in root.rglob("*.csv")}
    return sorted(folders)


def parse_xlim(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("xlim must look like -5,5")
    try:
        left, right = float(parts[0]), float(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("xlim values must be numeric") from exc
    if left >= right:
        raise argparse.ArgumentTypeError("xlim left must be smaller than right")
    return left, right


def process_folder(folder: Path, args: argparse.Namespace) -> None:
    cycles = collect_cycles(folder)
    if not cycles:
        print(f"No plottable B1500 CSV files found in {folder}")
        return

    if args.device_id:
        requested_devices = set(args.device_id)
        available_devices = sorted({cycle.device_id for cycle in cycles})
        cycles = [cycle for cycle in cycles if cycle.device_id in requested_devices]
        missing_devices = sorted(requested_devices - set(available_devices))
        for device_id in missing_devices:
            print(f"{folder}: device ID not found: {device_id}")
        if not cycles:
            print(f"{folder}: no cycles matched requested device ID(s)")
            return

    output_dir = Path(args.output_dir) if args.output_dir else folder
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = folder.name or "iv_plot"
    if args.device_id:
        selected_name = "_".join(safe_filename_part(device_id) for device_id in sorted({cycle.device_id for cycle in cycles}))
        output_stem = f"{safe_name}_{selected_name}_IV"
    else:
        output_stem = f"{safe_name}_IV"
    log_plot_path = output_dir / f"{output_stem}_log_signed.png"
    linear_plot_path = output_dir / f"{output_stem}_linear_signed.png"
    summary_path = output_dir / f"{safe_name}_summary.csv"

    current_floor = args.current_floor if args.floor_current else None
    log_yscale = "log" if args.abs_current else "symlog"
    plot_folder_iv(
        folder=folder,
        cycles=cycles,
        output_path=log_plot_path,
        yscale=log_yscale,
        use_abs_current=args.abs_current,
        use_abs_voltage=args.abs_voltage,
        current_floor=current_floor,
        symlog_linthresh=args.symlog_linthresh,
        xlim=args.xlim,
        dpi=args.dpi,
    )
    plot_folder_iv(
        folder=folder,
        cycles=cycles,
        output_path=linear_plot_path,
        yscale="linear",
        use_abs_current=args.abs_current,
        use_abs_voltage=args.abs_voltage,
        xlim=args.xlim,
        dpi=args.dpi,
    )
    if not args.device_id:
        write_summary_csv(folder, cycles, summary_path)

    device_count = len({cycle.device_id for cycle in cycles})
    print(f"{folder}: {device_count} devices, {len(cycles)} cycles")
    print(f"  saved {log_plot_path}")
    print(f"  saved {linear_plot_path}")
    if not args.device_id:
        print(f"  saved {summary_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot SET-RESET RRAM I-V CSV files grouped by device ID."
    )
    parser.add_argument(
        "folders",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help="Folder(s) containing SET-RESET CSV files. Defaults to current folder.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Treat each supplied path as a root and process every subfolder containing CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional common output directory. By default outputs are saved inside each input folder.",
    )
    parser.add_argument(
        "--device-id",
        action="append",
        default=[],
        help=(
            "Only plot the requested device ID. Can be used multiple times. "
            "When set, no summary CSV is saved."
        ),
    )
    parser.add_argument(
        "--abs-current",
        action="store_true",
        help="Plot |current| instead of signed current.",
    )
    parser.add_argument(
        "--abs-voltage",
        action="store_true",
        help="Plot |voltage| instead of signed voltage.",
    )
    parser.add_argument(
        "--floor-current",
        action="store_true",
        help="Clamp nonpositive current to --current-floor instead of dropping those points.",
    )
    parser.add_argument(
        "--current-floor",
        type=float,
        default=1e-12,
        help="Current floor used with --floor-current. Default: 1e-12 A.",
    )
    parser.add_argument(
        "--symlog-linthresh",
        type=float,
        default=1e-12,
        help="Linear threshold around zero for signed log plots. Default: 1e-12 A.",
    )
    parser.add_argument(
        "--xlim",
        type=parse_xlim,
        default=(-5.0, 5.0),
        help="Voltage axis limits as left,right. Default: -5,5.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Saved plot DPI. Default: 300.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    folders: list[Path] = []
    for folder in args.folders:
        folder = folder.expanduser().resolve()
        if args.recursive:
            folders.extend(folders_with_csv(folder))
        else:
            folders.append(folder)

    seen: set[Path] = set()
    for folder in folders:
        if folder in seen:
            continue
        seen.add(folder)
        if not folder.is_dir():
            print(f"Skipping missing folder: {folder}")
            continue
        process_folder(folder, args)


if __name__ == "__main__":
    main()
