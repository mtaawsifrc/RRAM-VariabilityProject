#!/usr/bin/env python3
"""Orchestrate the MATLAB TaO-Fit pipeline from Python."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def matlab_quote(path: Path) -> str:
    return str(path).replace("'", "''")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--matlab-bin", default="matlab")
    args = parser.parse_args()

    input_csv = Path(args.input).expanduser().resolve()
    config = Path(args.config).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    matlab_dir = Path(__file__).resolve().parent.parent / "matlab"
    outdir.mkdir(parents=True, exist_ok=True)

    script = (
        f"cd('{matlab_quote(matlab_dir)}');"
        f"main_fit_stanford('{matlab_quote(input_csv)}',"
        f"'{matlab_quote(config)}','{matlab_quote(outdir)}');"
    )
    command = [args.matlab_bin, "-batch", script]
    print("[taofit] launching:", " ".join(command))
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main())

