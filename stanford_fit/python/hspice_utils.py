"""Shared HSPICE parsing helpers for Python users."""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd


HSPICE_NUM_RE = re.compile(
    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?[fpnumkKMG]?"
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


def hspice_float(value: str) -> float:
    value = value.strip().replace("D", "E").replace("d", "e")
    suffix = value[-1] if value else ""
    if suffix in HSPICE_SUFFIX_SCALE:
        return float(value[:-1]) * HSPICE_SUFFIX_SCALE[suffix]
    return float(value)


def parse_lis_currents(lis_path: Path) -> pd.DataFrame:
    rows = []
    for line in Path(lis_path).read_text(errors="replace").splitlines():
        values = HSPICE_NUM_RE.findall(line)
        if len(values) < 3:
            continue
        try:
            rows.append(tuple(hspice_float(value) for value in values[:3]))
        except ValueError:
            continue
    return pd.DataFrame(rows, columns=["time_s", "voltage_V", "current_A"])


def interp_to_grid(df: pd.DataFrame, voltage_grid: np.ndarray) -> np.ndarray:
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    df = df.sort_values("voltage_V")
    return np.interp(
        voltage_grid,
        df["voltage_V"].to_numpy(float),
        df["current_A"].to_numpy(float),
        left=np.nan,
        right=np.nan,
    )

