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
import pandas as pd
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
MECH_ORDER = ["ohmic", "poole_frenkel", "schottky", "fowler_nordheim",
              "unclassified"]


def build_regime_map(rep_csv: str, ensemble_csv: str) -> str:
    """Run 02c (regime map + per-cycle mechanism stability); return map path."""
    rep = Path(rep_csv)
    prefix = rep.stem.replace("_representative_curve_FIXED", "")
    cmd = [sys.executable, str(ROOT / "02c_classify_conduction_regimes.py"),
           "--rep-csv", str(rep), "--output-dir", str(rep.parent)]
    if Path(ensemble_csv).is_file():
        cmd += ["--ensemble-csv", str(ensemble_csv)]
    if subprocess.call(cmd) != 0:
        raise RuntimeError(f"regime classification failed for {rep}")
    return str(rep.parent / f"{prefix}_regime_map.csv")


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
    ap.add_argument("--reanalyze", action="store_true",
                    help="skip ensemble build + HSPICE fitting; regenerate the "
                         "CSV/figures from existing per-condition .mat files only")
    ap.add_argument("--bound-tol", type=float, default=0.01,
                    help="a bootstrap draw is counted as bound-pinned when it "
                         "lies within this fraction of the (lb,ub) box edge")
    args = ap.parse_args()
    conds = args.conditions or [f"S{i}" for i in range(1, 13)]
    base = Path(args.base_config)
    outroot = Path(args.outroot); outroot.mkdir(parents=True, exist_ok=True)

    overrides = {
        "run_fisher": 0,
        "run_slice": 0,
        "run_bootstrap": 1,
        "run_loco": 1 if args.with_loco else 0,
        "bootstrap_n": args.bootstrap_n,
        "bootstrap_bo_n_init": 8, "bootstrap_bo_n_iter": 24,
        "loco_bo_n_init": 8, "loco_bo_n_iter": 24,
    }

    collected = {}
    names = None
    for c in conds:
        outdir = outroot / c
        if not args.reanalyze:
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
            print(f"[{c}] classifying conduction regimes ...")
            try:
                regime_map = build_regime_map(rep[0], str(ens))
            except RuntimeError as e:
                print(f"[{c}] {e}; fitting without regime map")
                regime_map = ""
            cond_overrides = dict(overrides)
            if regime_map:
                cond_overrides["regime_map_csv"] = regime_map
            cfg = write_cfg(base, cond_overrides)
            print(f"[{c}] bootstrap fit (n={args.bootstrap_n}) ...")
            subprocess.call([
                sys.executable, str(ROOT / "stanford_fit/python/03_run_stanford_fit.py"),
                "--input", rep[0], "--ensemble", str(ens), "--config", cfg,
                "--outdir", str(outdir), "--matlab-bin", args.matlab_bin])
            os.unlink(cfg)
        if not (outdir / "validation.mat").is_file():
            print(f"[{c}] no validation.mat in {outdir}; skipping"); continue
        try:
            val = sio.loadmat(outdir / "validation.mat", squeeze_me=True, struct_as_record=False)["val"]
            ref = sio.loadmat(outdir / "refined.mat", squeeze_me=True, struct_as_record=False)["refined"]
            names = [str(x) for x in np.ravel(ref.priors.names)]
            active = set(str(x) for x in np.ravel(ref.active_names))
            theta = np.asarray(ref.theta, dtype=float).ravel()
            ci = np.asarray(val.ci95, dtype=float)            # 2 x nP
            tbs = np.asarray(val.theta_bs, dtype=float)        # nB x nP
            lb = np.asarray(ref.priors.lb, dtype=float).ravel()
            ub = np.asarray(ref.priors.ub, dtype=float).ravel()
            collected[c] = dict(theta=theta, ci=ci, tbs=tbs, active=active,
                                lb=lb, ub=ub)
            nfin = int(np.all(np.isfinite(tbs), axis=1).sum()) if tbs.ndim == 2 else 0
            print(f"[{c}] bootstrap draws used: {nfin}; ci95 finite: {np.isfinite(ci).all()}")
        except Exception as e:
            print(f"[{c}] collect failed: {e}")

    if not collected:
        print("No conditions collected."); return 1

    active = [n for n in names if n in next(iter(collected.values()))["active"]]
    idx = {n: i for i, n in enumerate(names)}
    cl = sorted(collected, key=lambda s: int(s[1:]))

    # CSV: per condition per active param.
    # Robustness fix (A1): the reported point and the 95% interval are now both
    # read from the SAME bootstrap distribution -- theta is the bootstrap median
    # and (ci_lo,ci_hi) are its 2.5/97.5 percentiles -- so the interval brackets
    # the plotted estimate by construction.  The full-budget refined optimum is
    # retained as theta_point for reference, and the percentile interval may not
    # contain it when the reduced-budget bootstrap optimum is biased.
    # Robustness fix (A2): frac_at_bound is the fraction of bootstrap draws
    # pinned within --bound-tol of the (lb,ub) prior box edge; a large value
    # means the interval width is set by the box rather than by the data.
    tol = args.bound_tol
    n_outside = 0
    lines = ["condition,parameter,theta,theta_point,ci_lo,ci_hi,cv,frac_at_bound"]
    cv_mat = np.full((len(active), len(cl)), np.nan)
    for j, c in enumerate(cl):
        d = collected[c]
        for i, n in enumerate(active):
            p = idx[n]
            col = d["tbs"][:, p]; col = col[np.isfinite(col)]
            if col.size:
                med = float(np.median(col))
                lo, hi = (float(np.percentile(col, 2.5)),
                          float(np.percentile(col, 97.5)))
                cv = (np.std(col) / abs(np.mean(col))) if np.mean(col) != 0 else np.nan
                span = d["ub"][p] - d["lb"][p]
                if span > 0:
                    frac = float(np.mean(((col - d["lb"][p]) / span < tol) |
                                         ((d["ub"][p] - col) / span < tol)))
                else:
                    frac = np.nan
            else:
                med, lo, hi, cv, frac = (np.nan,) * 5
            cv_mat[i, j] = cv
            if np.isfinite(lo) and not (lo <= d["theta"][p] <= hi):
                n_outside += 1
            lines.append(f"{c},{n},{med:.6g},{d['theta'][p]:.6g},"
                         f"{lo:.6g},{hi:.6g},{cv:.4g},{frac:.3g}")
    (outroot / "parameter_cis.csv").write_text("\n".join(lines) + "\n")
    n_total = len(active) * len(cl)
    print(f"[A1] full-budget refined optimum lies outside the bootstrap "
          f"percentile CI for {n_outside}/{n_total} parameter-conditions "
          f"(reported theta is now the bootstrap median, always inside the CI).")

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

    summarize_regimes(cl, outroot)
    return 0


def summarize_regimes(conds, outroot: Path):
    """Aggregate per-condition regime maps + cycle stability; plot the
    dominant-mechanism map (state x condition) -- the stoichiometry/variability
    link to the conduction-mechanism analysis (MWSCAS 2025)."""
    maps, stabs = [], []
    for c in conds:
        for p in glob.glob(str(ROOT / f"step02_{c}/*_regime_map.csv")):
            maps.append(pd.read_csv(p).assign(condition=c))
        for p in glob.glob(str(ROOT / f"step02_{c}/*_regime_stability.csv")):
            stabs.append(pd.read_csv(p).assign(condition=c))
    if not maps:
        return
    all_maps = pd.concat(maps, ignore_index=True)
    all_maps.to_csv(outroot / "regime_maps_all.csv", index=False)
    states = ["SET_HRS_PRE", "SET_LRS_POST", "RESET_LRS_PRE", "RESET_HRS_POST"]
    if stabs:
        all_stab = pd.concat(stabs, ignore_index=True)
        all_stab.to_csv(outroot / "mechanism_stability_all.csv", index=False)
        dom = (all_stab.sort_values("fraction", ascending=False)
               .groupby(["condition", "state"]).first().reset_index())
        src = {(r.condition, r.state): (r.mechanism, r.fraction)
               for r in dom.itertuples()}
    else:
        big = (all_maps.sort_values("n_points", ascending=False)
               .groupby(["condition", "state"]).first().reset_index())
        src = {(r.condition, r.state): (r.mechanism, np.nan)
               for r in big.itertuples()}

    grid = np.full((len(states), len(conds)), np.nan)
    for j, c in enumerate(conds):
        for i, s in enumerate(states):
            mech = src.get((c, s), ("unclassified", np.nan))[0]
            grid[i, j] = MECH_ORDER.index(mech) if mech in MECH_ORDER else 4
    fig, ax = plt.subplots(figsize=(max(7, len(conds)), 4))
    im = ax.imshow(grid, aspect="auto", cmap=plt.get_cmap("viridis", 5),
                   vmin=-0.5, vmax=4.5)
    ax.set_xticks(range(len(conds))); ax.set_xticklabels(conds, rotation=45,
                                                         ha="right")
    ax.set_yticks(range(len(states))); ax.set_yticklabels(states)
    for j, c in enumerate(conds):
        for i, s in enumerate(states):
            mech, frac = src.get((c, s), ("", np.nan))
            txt = mech.replace("_", "\n")
            if np.isfinite(frac):
                txt += f"\n{100 * frac:.0f}%"
            ax.text(j, i, txt, ha="center", va="center", fontsize=6,
                    color="w")
    cb = fig.colorbar(im, ax=ax, ticks=range(5))
    cb.ax.set_yticklabels(MECH_ORDER)
    ax.set_title("Dominant conduction mechanism per state "
                 "(% = cycle-to-cycle stability)")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outroot / f"mechanism_map.{ext}", dpi=300)
    print("Wrote", outroot / "regime_maps_all.csv")


if __name__ == "__main__":
    raise SystemExit(main())
