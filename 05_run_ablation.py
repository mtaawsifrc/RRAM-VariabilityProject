#!/usr/bin/env python3
"""Ablation harness: quantify the value of physics-guided Bayesian optimization.

For each condition it fits the representative curve three ways and tabulates the
fit error, isolating the contribution of (i) the physics priors and (ii) the
Bayesian optimization:

  physics_bo    physics priors + BO            (the full proposed method)
  plain_bo      uninformative priors + BO      (same model/data/budget, no physics)
  physics_nobo  physics priors, NO BO          (the un-tuned initial guess)

Outputs:
  results/ablation/<cond>/<variant>/...        per-run TaO-Fit outputs
  results/ablation/ablation_summary.csv
  results/ablation/ablation_rmse.{png,pdf}

Usage:
  python3 05_run_ablation.py                 # all 12 conditions
  python3 05_run_ablation.py S1 S2           # a subset
"""
import argparse, subprocess, sys, tempfile, os, glob
from pathlib import Path
import numpy as np
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
VARIANTS = {
    "physics_bo":   {},                       # full method (defaults)
    "plain_bo":     {"prior_mode": "plain"},   # no physics priors
    "physics_nobo": {"defaults_only": 1},      # physics priors, no optimization
}
# Fisher not needed for the ablation comparison -> force it off for speed.
COMMON = {"run_fisher": 0, "run_loco": 0, "run_bootstrap": 0}


def write_cfg(base: Path, overrides: dict) -> str:
    txt = base.read_text()
    extra = "".join(f"\n{k}: {v}" for k, v in {**COMMON, **overrides}.items())
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix="ablation_")
    os.write(fd, (txt + extra + "\n").encode())
    os.close(fd)
    return path


def sc(x):
    a = np.ravel(np.asarray(x))
    return float(a[0]) if a.size and a.dtype.kind in "fiu" else np.nan


def collect(outdir: Path):
    try:
        val = sio.loadmat(outdir / "validation.mat", squeeze_me=True, struct_as_record=False)["val"]
        ref = sio.loadmat(outdir / "refined.mat", squeeze_me=True, struct_as_record=False)["refined"]
        return sc(val.rmse_set), sc(val.rmse_res), sc(ref.fval)
    except Exception as e:
        print("  [warn] collect failed:", e)
        return np.nan, np.nan, np.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions", nargs="*", default=None)
    ap.add_argument("--base-config", default=str(ROOT / "stanford_fit/config/default_config.yaml"))
    ap.add_argument("--matlab-bin", default="matlab")
    ap.add_argument("--outroot", default=str(ROOT / "results/ablation"))
    args = ap.parse_args()
    conds = args.conditions or [f"S{i}" for i in range(1, 13)]
    base = Path(args.base_config)
    outroot = Path(args.outroot); outroot.mkdir(parents=True, exist_ok=True)

    rows = [("condition", "variant", "rmse_set_dec", "rmse_res_dec", "fval")]
    for c in conds:
        rep = glob.glob(str(ROOT / f"step02_{c}/*_representative_curve_FIXED.csv"))
        if not rep:
            print(f"[{c}] no representative curve, skipping"); continue
        for vname, ov in VARIANTS.items():
            outdir = outroot / c / vname
            cfg = write_cfg(base, ov)
            print(f"[{c}/{vname}] fitting ...")
            rc = subprocess.call([
                sys.executable, str(ROOT / "stanford_fit/python/03_run_stanford_fit.py"),
                "--input", rep[0], "--config", cfg,
                "--outdir", str(outdir), "--matlab-bin", args.matlab_bin])
            os.unlink(cfg)
            rs, rr, fv = collect(outdir)
            rows.append((c, vname, f"{rs:.4f}", f"{rr:.4f}", f"{fv:.4f}"))
            print(f"  rc={rc} rmse_set={rs:.3f} rmse_res={rr:.3f}")

    summ = outroot / "ablation_summary.csv"
    summ.write_text("\n".join(",".join(map(str, r)) for r in rows) + "\n")

    # grouped bar of mean RMSE (set+res averaged) per variant per condition
    data = {v: {} for v in VARIANTS}
    for c, v, rs, rr, _ in rows[1:]:
        vals = [float(rs), float(rr)]
        data[v][c] = np.nanmean(vals)
    plotted = [c for c in conds if c in data["physics_bo"]]
    x = np.arange(len(plotted)); w = 0.26
    fig, ax = plt.subplots(figsize=(max(8, len(plotted)), 4.5))
    for i, v in enumerate(VARIANTS):
        ax.bar(x + (i - 1) * w, [data[v].get(c, np.nan) for c in plotted], w, label=v)
    ax.set_xticks(x); ax.set_xticklabels(plotted, rotation=45, ha="right")
    ax.set_ylabel("mean RMSE (decades)"); ax.legend(); ax.grid(axis="y", alpha=.3)
    ax.set_title("Ablation: fit error by method")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outroot / f"ablation_rmse.{ext}", dpi=300)
    print("Wrote", summ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
