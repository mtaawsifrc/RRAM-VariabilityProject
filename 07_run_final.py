#!/usr/bin/env python3
"""Final (publication) fits for all conditions.

For each condition this:
  1. builds the per-cycle ensemble (02b),
  2. classifies conduction regimes incl. cycle stability (02c),
  3. runs the full TaO-Fit with final_config.yaml: regime-conditioned priors,
     mechanism-aware loss weighting, Fisher CRLB at the optimum, and Stage-4b
     profile likelihood -> identifiability_report.csv per condition.

Outputs land in results/<cond>_taofit/ -- the layout 04_publication_summary.py
aggregates. Cross-cycle bootstrap CIs are produced separately by
06_run_variability.py (orders of magnitude more HSPICE calls).

Usage:
  python3 07_run_final.py            # all 12 conditions
  python3 07_run_final.py S1 S2      # a subset
"""
import argparse, subprocess, sys, tempfile, os, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_cfg(base: Path, overrides: dict) -> str:
    txt = base.read_text()
    extra = "".join(f"\n{k}: {v}" for k, v in overrides.items())
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix="final_")
    os.write(fd, (txt + extra + "\n").encode())
    os.close(fd)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions", nargs="*", default=None)
    ap.add_argument("--base-config",
                    default=str(ROOT / "stanford_fit/config/final_config.yaml"))
    ap.add_argument("--matlab-bin", default="matlab")
    ap.add_argument("--skip-profile", action="store_true",
                    help="disable Stage-4b profile likelihood (faster)")
    args = ap.parse_args()
    conds = args.conditions or [f"S{i}" for i in range(1, 13)]
    base = Path(args.base_config)

    failures = []
    for c in conds:
        rep = glob.glob(str(ROOT / f"step02_{c}/*_representative_curve_FIXED.csv"))
        st1 = ROOT / f"step01_{c}"
        if not rep or not st1.is_dir():
            print(f"[{c}] missing rep curve or step01 dir, skipping")
            failures.append(c)
            continue
        rep_csv = Path(rep[0])
        prefix = rep_csv.stem.replace("_representative_curve_FIXED", "")

        ens = ROOT / f"step02_{c}/{c}_cycle_ensemble.csv"
        print(f"[{c}] building ensemble ...")
        ens_arg = []
        if subprocess.call([sys.executable, str(ROOT / "02b_build_cycle_ensemble.py"),
                            "--step01-dir", str(st1), "--rep-csv", str(rep_csv),
                            "--output", str(ens)]) == 0:
            ens_arg = ["--ensemble", str(ens)]
        else:
            print(f"[{c}] ensemble build failed; continuing without it")

        print(f"[{c}] classifying conduction regimes ...")
        cmd = [sys.executable, str(ROOT / "02c_classify_conduction_regimes.py"),
               "--rep-csv", str(rep_csv), "--output-dir", str(rep_csv.parent)]
        if ens_arg:
            cmd += ["--ensemble-csv", str(ens)]
        regime_map = rep_csv.parent / f"{prefix}_regime_map.csv"
        overrides = {}
        if subprocess.call(cmd) == 0 and regime_map.is_file():
            overrides["regime_map_csv"] = str(regime_map)
        else:
            print(f"[{c}] regime classification failed; legacy prior windows")
        if args.skip_profile:
            overrides["run_slice"] = 0

        outdir = ROOT / "results" / f"{c}_taofit"
        cfg = write_cfg(base, overrides)
        print(f"[{c}] final TaO-Fit -> {outdir}")
        rc = subprocess.call([
            sys.executable, str(ROOT / "stanford_fit/python/03_run_stanford_fit.py"),
            "--input", str(rep_csv), "--config", cfg,
            "--outdir", str(outdir), "--matlab-bin", args.matlab_bin] + ens_arg)
        os.unlink(cfg)
        if rc != 0:
            print(f"[{c}] FIT FAILED (rc={rc})")
            failures.append(c)

    if failures:
        print("Failed/skipped conditions:", ", ".join(failures))
        return 1
    print("All conditions fitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
