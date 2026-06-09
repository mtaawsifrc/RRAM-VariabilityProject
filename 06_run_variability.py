#!/usr/bin/env python3
"""Cross-cycle variability: attach bootstrap confidence intervals to the fit.

For each condition this (1) builds the per-cycle ensemble of the representative
device, (2) refits the representative curve while Stage 5 runs a cluster
bootstrap over cycles (resample whole cycles -> aggregate -> refit), and
(3) collects the 95% parameter CIs. The point estimate is unchanged; the
bootstrap quantifies how cycle-to-cycle variability propagates to the
extracted Stanford parameters -- the core "variability" result.

Outputs:
  step02_<cond>/<cond>_cycle_ensemble.csv      per-cycle ensemble
  results/variability/<cond>/...               per-run TaO-Fit outputs (incl. ci95)
  results/variability/parameter_cis.csv        theta, CI lo/hi, CV per param/condition
  results/variability/parameter_cv.{png,pdf}   coefficient of variation heatmap

Usage:
  python3 06_run_variability.py S1                 # one condition (recommended first)
  python3 06_run_variability.py --bootstrap-n 200  # all 12, 200 resamples
  python3 06_run_variability.py --with-loco S1      # also run leave-one-cycle-out

NOTE: the bootstrap re-runs HSPICE bootstrap_n x (bo_init+bo_iter) times per
condition -- this is the slow stage. Start with one condition / bootstrap_n~100.
"""
import argparse, subprocess, sys, tempfile, os, glob
from pathlib import Path
import numpy as np
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent


def write_cfg(base: Path, overrides: dict) -> str:
    txt = base.read_text()
    extra = "".join(f"\n{k}: {v}" for k, v in overrides.items())
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix="variability_")
    os.write(fd, (txt + extra + "\n").encode())
    os.close(fd)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions", nargs="*", default=None)
    ap.add_argument("--base-config", default=str(ROOT / "stanford_fit/config/default_config.yaml"))
    ap.add_argument("--matlab-bin", default="matlab")
    ap.add_argument("--outroot", default=str(ROOT / "results/variability"))
    ap.add_argument("--bootstrap-n", type=int, default=120)
    ap.add_argument("--with-loco", action="store_true")
    args = ap.parse_args()
    conds = args.conditions or [f"S{i}" for i in range(1, 13)]
    base = Path(args.base_config)
    outroot = Path(args.outroot); outroot.mkdir(parents=True, exist_ok=True)

    overrides = {
        "run_fisher": 0,
        "run_bootstrap": 1,
        "run_loco": 1 if args.with_loco else 0,
        "bootstrap_n": args.bootstrap_n,
        "bootstrap_bo_n_init": 8, "bootstrap_bo_n_iter": 24,
        "loco_bo_n_init": 8, "loco_bo_n_iter": 24,
    }

    collected = {}
    names = None
    for c in conds:
        rep = glob.glob(str(ROOT / f"step02_{c}/*_representative_curve_FIXED.csv"))
        st1 = ROOT / f"step01_{c}"
        if not rep or not st1.is_dir():
            print(f"[{c}] missing rep curve or step01 dir, skipping"); continue
        ens = ROOT / f"step02_{c}/{c}_cycle_ensemble.csv"
        print(f"[{c}] building ensemble ...")
        if subprocess.call([sys.executable, str(ROOT / "02b_build_cycle_ensemble.py"),
                            "--step01-dir", str(st1), "--rep-csv", rep[0],
                            "--output", str(ens)]) != 0:
            print(f"[{c}] ensemble build failed, skipping"); continue
        outdir = outroot / c
        cfg = write_cfg(base, overrides)
        print(f"[{c}] bootstrap fit (n={args.bootstrap_n}) ...")
        subprocess.call([
            sys.executable, str(ROOT / "stanford_fit/python/03_run_stanford_fit.py"),
            "--input", rep[0], "--ensemble", str(ens), "--config", cfg,
            "--outdir", str(outdir), "--matlab-bin", args.matlab_bin])
        os.unlink(cfg)
        try:
            val = sio.loadmat(outdir / "validation.mat", squeeze_me=True, struct_as_record=False)["val"]
            ref = sio.loadmat(outdir / "refined.mat", squeeze_me=True, struct_as_record=False)["refined"]
            names = [str(x) for x in np.ravel(ref.priors.names)]
            active = set(str(x) for x in np.ravel(ref.active_names))
            theta = np.asarray(ref.theta, dtype=float).ravel()
            ci = np.asarray(val.ci95, dtype=float)            # 2 x nP
            tbs = np.asarray(val.theta_bs, dtype=float)        # nB x nP
            collected[c] = dict(theta=theta, ci=ci, tbs=tbs, active=active)
            nfin = int(np.all(np.isfinite(tbs), axis=1).sum()) if tbs.ndim == 2 else 0
            print(f"[{c}] bootstrap draws used: {nfin}; ci95 finite: {np.isfinite(ci).all()}")
        except Exception as e:
            print(f"[{c}] collect failed: {e}")

    if not collected:
        print("No conditions collected."); return 1

    active = [n for n in names if n in next(iter(collected.values()))["active"]]
    idx = {n: i for i, n in enumerate(names)}
    cl = sorted(collected, key=lambda s: int(s[1:]))

    # CSV: per condition per active param
    lines = ["condition,parameter,theta,ci_lo,ci_hi,cv"]
    cv_mat = np.full((len(active), len(cl)), np.nan)
    for j, c in enumerate(cl):
        d = collected[c]
        for i, n in enumerate(active):
            p = idx[n]
            lo, hi = d["ci"][0, p], d["ci"][1, p]
            col = d["tbs"][:, p]; col = col[np.isfinite(col)]
            cv = (np.std(col) / abs(np.mean(col))) if col.size and np.mean(col) != 0 else np.nan
            cv_mat[i, j] = cv
            lines.append(f"{c},{n},{d['theta'][p]:.6g},{lo:.6g},{hi:.6g},{cv:.4g}")
    (outroot / "parameter_cis.csv").write_text("\n".join(lines) + "\n")

    # CV heatmap (cross-cycle parameter stability)
    fig, ax = plt.subplots(figsize=(max(7, len(cl)), 7))
    im = ax.imshow(np.log10(np.clip(cv_mat, 1e-3, 1e2)), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(cl))); ax.set_xticklabels(cl, rotation=45, ha="right")
    ax.set_yticks(range(len(active))); ax.set_yticklabels(active)
    cb = fig.colorbar(im, ax=ax); cb.set_label(r"$\log_{10}$ coefficient of variation (bootstrap)")
    ax.set_title("Cross-cycle parameter variability")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outroot / f"parameter_cv.{ext}", dpi=300)
    print("Wrote", outroot / "parameter_cis.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
