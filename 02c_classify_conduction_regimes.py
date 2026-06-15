#!/usr/bin/env python3
"""Classify the dominant conduction mechanism per voltage window and state.

Automates the conduction-mechanism analysis of Chowdhury et al., MWSCAS 2025
(Literature/01.pdf): for each butterfly state segment (SET_HRS_PRE,
SET_LRS_POST, RESET_LRS_PRE, RESET_HRS_POST) it tests the four standard
linearizations on sliding voltage windows and selects the winner by BIC:

  ohmic           ln I       vs ln V      slope ~ 1
  poole_frenkel   ln(I/V)    vs sqrt(V)   slope > 0, plausible eps_r
  schottky        ln I       vs sqrt(V)   slope > 0, plausible eps_r
  fowler_nordheim ln(I/V^2)  vs 1/V       slope < 0

PF and Schottky linearizations are nearly collinear, so both must also pass a
physical check: the dynamic permittivity implied by the fitted slope
(eps_r = q^3/(pi*eps0*tox*(s*kT)^2), /4 for Schottky) must be plausible.

Outputs (in --output-dir):
  <prefix>_regime_map.csv            merged regimes: branch,state,v_lo,v_hi,
                                     mechanism,slope,intercept,r2,bic,
                                     eps_r_dyn,n_points
  <prefix>_regime_overview.png       log|I|-V per state colored by mechanism
  <prefix>_regime_linearizations.png winning linearization per regime (R^2)
  <prefix>_regime_stability.csv      (with --ensemble-csv) dominant mechanism
                                     per cycle per state + stability fraction

Usage:
  python3 02c_classify_conduction_regimes.py \
      --rep-csv step02_S1/S1_A8-04-4um-02_representative_curve_FIXED.csv \
      --output-dir step02_S1 \
      [--ensemble-csv step02_S1/S1_cycle_ensemble.csv]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

KB = 1.380649e-23
Q = 1.602176634e-19
EPS0 = 8.8541878128e-12

MECHANISMS = ("ohmic", "poole_frenkel", "schottky", "fowler_nordheim")
MECH_COLORS = {
    "ohmic": "tab:blue",
    "poole_frenkel": "tab:red",
    "schottky": "tab:orange",
    "fowler_nordheim": "tab:green",
    "unclassified": "0.6",
}
# Stanford model current law is bulk hopping/tunneling: it can represent
# ohmic and PF-like windows but not interface-limited (Schottky) or FN windows.
BULK_MECHS = {"ohmic", "poole_frenkel"}


def linearize(mech, v, i):
    """Return (x, y) for the mechanism's linearization."""
    if mech == "ohmic":
        return np.log(v), np.log(i)
    if mech == "poole_frenkel":
        return np.sqrt(v), np.log(i / v)
    if mech == "schottky":
        return np.sqrt(v), np.log(i)
    if mech == "fowler_nordheim":
        return 1.0 / v, np.log(i / v**2)
    raise ValueError(mech)


def eps_r_from_slope(slope, tox, T, schottky=False):
    """Dynamic permittivity implied by a PF/Schottky sqrt(V) slope."""
    if slope <= 0:
        return np.nan
    kT = KB * T
    eps_r = Q**3 / (np.pi * EPS0 * tox * (slope * kT) ** 2)
    return eps_r / 4.0 if schottky else eps_r


def fit_window(mech, v, i, tox, T, eps_r_range):
    """Fit one mechanism on one window. Returns dict or None if disqualified."""
    x, y = linearize(mech, v, i)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4:
        return None
    x, y = x[ok], y[ok]
    if np.ptp(x) <= 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    n = len(y)
    rss = float(np.sum(resid**2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0
    bic = n * np.log(max(rss / n, 1e-30)) + 2 * np.log(n)

    eps_r = np.nan
    if mech == "ohmic":
        if not (0.8 <= slope <= 1.2):
            return None
    elif mech in ("poole_frenkel", "schottky"):
        if slope <= 0:
            return None
        eps_r = eps_r_from_slope(slope, tox, T, schottky=(mech == "schottky"))
        if not (eps_r_range[0] <= eps_r <= eps_r_range[1]):
            return None
    elif mech == "fowler_nordheim":
        if slope >= 0:
            return None
    return dict(mechanism=mech, slope=float(slope), intercept=float(intercept),
                r2=float(r2), bic=float(bic), eps_r_dyn=float(eps_r), n_points=n)


def classify_window(v, i, tox, T, eps_r_range):
    fits = [f for m in MECHANISMS if (f := fit_window(m, v, i, tox, T, eps_r_range))]
    if not fits:
        return None
    return min(fits, key=lambda f: f["bic"])


def split_states(branch_df, branch):
    """Split one branch (sorted by sequence) into forward/return state segments."""
    df = branch_df.reset_index(drop=True)
    if len(df) < 5:
        return {}
    if branch == "SET":
        pivot = int(df["voltage_V"].idxmax())
        return {"SET_HRS_PRE": df.iloc[: pivot + 1],
                "SET_LRS_POST": df.iloc[pivot:]}
    pivot = int(df["voltage_V"].idxmin())
    return {"RESET_LRS_PRE": df.iloc[: pivot + 1],
            "RESET_HRS_POST": df.iloc[pivot:]}


def clean_segment(seg, v_floor, i_floor, compliance_guard):
    """abs(V), abs(I); drop sub-floor points and the compliance plateau."""
    v = np.abs(pd.to_numeric(seg["voltage_V"], errors="coerce").to_numpy(float))
    i = pd.to_numeric(seg["abs_current_A"], errors="coerce").to_numpy(float)
    keep = np.isfinite(v) & np.isfinite(i) & (v >= v_floor) & (i >= i_floor)
    if keep.sum() >= 4:
        imax = i[keep].max()
        keep &= i < compliance_guard * imax
    v, i = v[keep], i[keep]
    order = np.argsort(v)
    return v[order], i[order]


def classify_segment(v, i, args):
    """Sliding-window classification + merge of same-mechanism neighbors."""
    n = len(v)
    if n < args.min_window_points:
        return []
    win = max(args.min_window_points, int(np.ceil(n / 3)))
    step = max(1, win // 4)
    starts = list(range(0, max(n - win, 0) + 1, step))
    if not starts:
        starts = [0]
    labels = []
    for s in starts:
        sl = slice(s, min(s + win, n))
        best = classify_window(v[sl], i[sl], args.tox, args.temperature,
                               (args.eps_r_min, args.eps_r_max))
        labels.append((s, sl.stop, best["mechanism"] if best else "unclassified"))

    # merge consecutive windows with the same winner into regimes
    regimes = []
    cur_mech, cur_lo, cur_hi = None, None, None
    for s, e, mech in labels:
        if mech == cur_mech:
            cur_hi = e
        else:
            if cur_mech is not None:
                regimes.append((cur_lo, cur_hi, cur_mech))
            cur_mech, cur_lo, cur_hi = mech, s, e
    if cur_mech is not None:
        regimes.append((cur_lo, cur_hi, cur_mech))

    # refit each merged regime over its full span for the reported numbers
    out = []
    for lo, hi, mech in regimes:
        if mech == "unclassified":
            out.append(dict(mechanism="unclassified", slope=np.nan,
                            intercept=np.nan, r2=np.nan, bic=np.nan,
                            eps_r_dyn=np.nan, n_points=hi - lo,
                            v_lo=float(v[lo]), v_hi=float(v[hi - 1])))
            continue
        fit = fit_window(mech, v[lo:hi], i[lo:hi], args.tox, args.temperature,
                         (args.eps_r_min, args.eps_r_max))
        if fit is None:  # merged span fails the physical check -> re-classify
            fit = classify_window(v[lo:hi], i[lo:hi], args.tox, args.temperature,
                                  (args.eps_r_min, args.eps_r_max))
        if fit is None:
            fit = dict(mechanism="unclassified", slope=np.nan, intercept=np.nan,
                       r2=np.nan, bic=np.nan, eps_r_dyn=np.nan, n_points=hi - lo)
        fit["v_lo"] = float(v[lo])
        fit["v_hi"] = float(v[hi - 1])
        out.append(fit)
    return out


def classify_curve(df, args):
    """Full classification of one butterfly curve -> regime rows."""
    rows = []
    df = df.copy()
    if "butterfly_sequence_index" in df.columns:
        df = df.sort_values("butterfly_sequence_index")
    if "abs_current_A" not in df.columns:
        src = ("median_abs_current_A" if "median_abs_current_A" in df.columns
               else "median_current_A")
        df["abs_current_A"] = df[src].abs()
    for branch in ("SET", "RESET"):
        bdf = df[df["branch"].astype(str).str.upper() == branch]
        for state, seg in split_states(bdf, branch).items():
            v, i = clean_segment(seg, args.v_floor, args.i_floor,
                                 args.compliance_guard)
            for reg in classify_segment(v, i, args):
                reg.update(branch=branch, state=state)
                rows.append(reg)
    return rows


def plot_overview(df, regimes, path):
    states = ["SET_HRS_PRE", "SET_LRS_POST", "RESET_LRS_PRE", "RESET_HRS_POST"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    df = df.sort_values("butterfly_sequence_index")
    if "abs_current_A" not in df.columns:
        df = df.assign(abs_current_A=df["median_abs_current_A"].abs())
    segs = {}
    for branch in ("SET", "RESET"):
        bdf = df[df["branch"].astype(str).str.upper() == branch]
        segs.update(split_states(bdf, branch))
    for ax, state in zip(axes.ravel(), states):
        seg = segs.get(state)
        if seg is None or seg.empty:
            ax.set_visible(False)
            continue
        v = np.abs(seg["voltage_V"].to_numpy(float))
        i = seg["abs_current_A"].to_numpy(float)
        ax.semilogy(v, np.clip(i, 1e-14, None), ".", color="0.75", ms=4,
                    label="data")
        for r in [r for r in regimes if r["state"] == state]:
            m = (v >= r["v_lo"]) & (v <= r["v_hi"])
            ax.semilogy(v[m], np.clip(i[m], 1e-14, None), ".",
                        color=MECH_COLORS.get(r["mechanism"], "k"), ms=6,
                        label=f"{r['mechanism']} "
                              f"[{r['v_lo']:.2f},{r['v_hi']:.2f}]V "
                              f"R2={r['r2']:.2f}" if np.isfinite(r["r2"])
                              else r["mechanism"])
        ax.set_title(state)
        ax.set_xlabel("|V| (V)")
        ax.set_ylabel("|I| (A)")
        ax.legend(fontsize=7)
    fig.suptitle("Conduction regime classification")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def plot_linearizations(df, regimes, path, args):
    """One panel per classified regime: the winning linearization (MWSCAS-style)."""
    cls = [r for r in regimes if r["mechanism"] != "unclassified"]
    if not cls:
        return
    ncol = min(4, len(cls))
    nrow = int(np.ceil(len(cls) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 3.2 * nrow),
                             squeeze=False)
    df = df.sort_values("butterfly_sequence_index")
    if "abs_current_A" not in df.columns:
        df = df.assign(abs_current_A=df["median_abs_current_A"].abs())
    segs = {}
    for branch in ("SET", "RESET"):
        bdf = df[df["branch"].astype(str).str.upper() == branch]
        segs.update(split_states(bdf, branch))
    xlabels = {"ohmic": "ln V", "poole_frenkel": r"$\sqrt{V}$",
               "schottky": r"$\sqrt{V}$", "fowler_nordheim": "1/V"}
    ylabels = {"ohmic": "ln I", "poole_frenkel": "ln(I/V)",
               "schottky": "ln I", "fowler_nordheim": r"ln(I/V$^2$)"}
    for ax, r in zip(axes.ravel(), cls):
        seg = segs[r["state"]]
        v, i = clean_segment(seg, args.v_floor, args.i_floor,
                             args.compliance_guard)
        m = (v >= r["v_lo"]) & (v <= r["v_hi"])
        x, y = linearize(r["mechanism"], v[m], i[m])
        ax.plot(x, y, "o", ms=4, color=MECH_COLORS[r["mechanism"]])
        xs = np.linspace(x.min(), x.max(), 50)
        ax.plot(xs, r["slope"] * xs + r["intercept"], "--", color="k", lw=1)
        ax.set_xlabel(xlabels[r["mechanism"]])
        ax.set_ylabel(ylabels[r["mechanism"]])
        ax.set_title(f"{r['state']}\n{r['mechanism']}  $R^2$={r['r2']:.3f}",
                     fontsize=9)
    for ax in axes.ravel()[len(cls):]:
        ax.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def cycle_stability(ensemble, args):
    """Dominant mechanism per cycle per state -> stability fractions."""
    rows = []
    for cyc, cdf in ensemble.groupby("representative_cycle_id"):
        cdf = cdf.sort_values("butterfly_sequence_index")
        if "abs_current_A" not in cdf.columns:
            cdf = cdf.assign(abs_current_A=cdf["median_abs_current_A"].abs())
        for branch in ("SET", "RESET"):
            bdf = cdf[cdf["branch"].astype(str).str.upper() == branch]
            for state, seg in split_states(bdf, branch).items():
                v, i = clean_segment(seg, args.v_floor, args.i_floor,
                                     args.compliance_guard)
                if len(v) < args.min_window_points:
                    continue
                best = classify_window(v, i, args.tox, args.temperature,
                                       (args.eps_r_min, args.eps_r_max))
                rows.append(dict(cycle_id=int(cyc), state=state,
                                 mechanism=best["mechanism"] if best
                                 else "unclassified",
                                 r2=best["r2"] if best else np.nan))
    per_cycle = pd.DataFrame(rows)
    if per_cycle.empty:
        return per_cycle, pd.DataFrame()
    stab = (per_cycle.groupby(["state", "mechanism"]).size()
            .rename("n_cycles").reset_index())
    totals = per_cycle.groupby("state").size().rename("total")
    stab = stab.merge(totals, on="state")
    stab["fraction"] = stab["n_cycles"] / stab["total"]
    return per_cycle, stab.sort_values(["state", "fraction"],
                                       ascending=[True, False])


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rep-csv", required=True,
                    help="representative curve CSV from step 02")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--prefix", default=None,
                    help="output filename prefix (default: rep CSV stem)")
    ap.add_argument("--ensemble-csv", default=None,
                    help="per-cycle ensemble CSV (02b) for mechanism stability")
    ap.add_argument("--tox", type=float, default=7e-9, help="oxide thickness (m)")
    ap.add_argument("--temperature", type=float, default=300.0, help="T (K)")
    ap.add_argument("--eps-r-min", type=float, default=1.0,
                    help="min plausible dynamic eps_r for PF/Schottky")
    ap.add_argument("--eps-r-max", type=float, default=60.0,
                    help="max plausible dynamic eps_r for PF/Schottky")
    ap.add_argument("--v-floor", type=float, default=0.05,
                    help="ignore |V| below this (V)")
    ap.add_argument("--i-floor", type=float, default=1e-13,
                    help="ignore |I| below this (A)")
    ap.add_argument("--compliance-guard", type=float, default=0.95,
                    help="drop points with I >= guard*Imax (compliance plateau)")
    ap.add_argument("--min-window-points", type=int, default=8)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or Path(args.rep_csv).stem.replace(
        "_representative_curve_FIXED", "")

    rep = pd.read_csv(args.rep_csv)
    regimes = classify_curve(rep, args)
    if not regimes:
        raise SystemExit("No regimes classified; check the input CSV.")
    cols = ["branch", "state", "v_lo", "v_hi", "mechanism", "slope",
            "intercept", "r2", "bic", "eps_r_dyn", "n_points"]
    reg_df = pd.DataFrame(regimes)[cols]
    reg_df["stanford_valid"] = reg_df["mechanism"].isin(BULK_MECHS).astype(int)
    map_path = outdir / f"{prefix}_regime_map.csv"
    reg_df.to_csv(map_path, index=False)
    print(f"[regimes] wrote {map_path}")
    print(reg_df.to_string(index=False))

    plot_overview(rep, regimes, outdir / f"{prefix}_regime_overview.png")
    plot_linearizations(rep, regimes,
                        outdir / f"{prefix}_regime_linearizations.png", args)

    if args.ensemble_csv and Path(args.ensemble_csv).is_file():
        ens = pd.read_csv(args.ensemble_csv)
        per_cycle, stab = cycle_stability(ens, args)
        if not stab.empty:
            stab_path = outdir / f"{prefix}_regime_stability.csv"
            stab.to_csv(stab_path, index=False)
            per_cycle.to_csv(outdir / f"{prefix}_regime_per_cycle.csv",
                             index=False)
            print(f"[regimes] wrote {stab_path}")
            print(stab.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
