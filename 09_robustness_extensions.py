#!/usr/bin/env python3
"""
09_robustness_extensions.py
===========================
Robustness hardening and novelty extensions for the TaO_x / Stanford-model
manuscripts.  Everything here is **pure post-processing of already-archived
artifacts** (the per-condition .mat / .csv files produced by the HSPICE-in-the-
loop pipeline); no new HSPICE simulation is required.

Inputs (all pre-existing):
  results/variability/<cond>/{validation,refined}.mat   bootstrap draws (theta_bs),
                                                         refined optimum, prior box
  results/<cond>_taofit/fisher_matrix.csv               log-coord Fisher matrix
  results/<cond>_taofit/refined.mat                      names / active set
  results/<cond>_taofit/profile_summary.csv             (S1-S4) profile verdicts
  results/paper_alt/heldout_validation.csv              held-out RMSE per condition

Outputs (results/robustness/):
  A1  ci_consistency.csv          refined optimum vs bootstrap percentile CI
  A2  bound_railing.csv           fraction of bootstrap draws pinned to box edges
  A3  generalization_gap.csv      per-condition in-sample vs held-out RMSE gap
  A4  profile_likelihood_summary.csv   aggregated profile-likelihood verdicts
  B1/B2 sloppy_spectrum.csv + sloppy_spectrum.{pdf,png}
                                   Fisher eigenvalue spectra (sloppiness) and the
                                   stiff/sloppy eigenvector composition
  B3  doe_response_surface.csv     formal DOE significance + lack-of-fit test on
                                   the identifiable parameters
  B4  variance_components.csv + variance_components.{pdf,png}
                                   cycle-to-cycle vs device-to-device variance
                                   from the replicated center points (S9-S12)

Usage:
  python3 09_robustness_extensions.py
"""

import os
import glob
import numpy as np
import pandas as pd
import scipy.io as sio
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
VAR = os.path.join(ROOT, "results", "variability")
OUT = os.path.join(ROOT, "results", "robustness")
os.makedirs(OUT, exist_ok=True)

CONDS = [f"S{i}" for i in range(1, 13)]
CENTER = ["S9", "S10", "S11", "S12"]   # replicated center-point devices

DOE = {
    "S1": (20.0, 75.0),   "S2": (20.0, 250.0),
    "S3": (35.0, 75.0),   "S4": (35.0, 250.0),
    "S5": (20.0, 162.5),  "S6": (35.0, 162.5),
    "S7": (27.5, 75.0),   "S8": (27.5, 250.0),
    "S9": (27.5, 162.5),  "S10": (27.5, 162.5),
    "S11": (27.5, 162.5), "S12": (27.5, 162.5),
}
# coded factor levels for the face-centered design
O2_CODE = {20.0: -1.0, 27.5: 0.0, 35.0: 1.0}
PW_CODE = {75.0: -1.0, 162.5: 0.0, 250.0: 1.0}

plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "figure.dpi": 150, "savefig.bbox": "tight", "axes.grid": True,
    "grid.alpha": 0.3,
})


def savefig(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote results/robustness/{name}.pdf (+png)")


# ---------------------------------------------------------------------------
# Shared loaders
# ---------------------------------------------------------------------------
def load_variability(cond):
    """theta_bs (nB x nP), refined theta, names, active set, prior box."""
    vp = os.path.join(VAR, cond, "validation.mat")
    rp = os.path.join(VAR, cond, "refined.mat")
    if not (os.path.exists(vp) and os.path.exists(rp)):
        return None
    val = sio.loadmat(vp, squeeze_me=True, struct_as_record=False)["val"]
    ref = sio.loadmat(rp, squeeze_me=True, struct_as_record=False)["refined"]
    names = [str(x) for x in np.ravel(ref.priors.names)]
    active = [str(x) for x in np.ravel(ref.active_names)]
    return dict(
        names=names, active=active,
        theta=np.asarray(ref.theta, float).ravel(),
        tbs=np.asarray(val.theta_bs, float),
        lb=np.asarray(ref.priors.lb, float).ravel(),
        ub=np.asarray(ref.priors.ub, float).ravel(),
    )


def bs_median(cond_data, name):
    """Bootstrap median of one parameter (NaN-safe)."""
    p = cond_data["names"].index(name)
    col = cond_data["tbs"][:, p]
    col = col[np.isfinite(col)]
    return float(np.median(col)) if col.size else np.nan


# ---------------------------------------------------------------------------
# A1 + A2 : interval consistency and bound railing
# ---------------------------------------------------------------------------
def a1_a2_interval_diagnostics():
    print("[A1/A2] interval consistency and bound railing")
    rows, brows = [], []
    data = {c: load_variability(c) for c in CONDS}
    data = {c: d for c, d in data.items() if d}
    n_out = n_tot = 0
    for c, d in data.items():
        for name in d["active"]:
            p = d["names"].index(name)
            col = d["tbs"][:, p]; col = col[np.isfinite(col)]
            if col.size == 0:
                continue
            med = float(np.median(col))
            lo, hi = float(np.percentile(col, 2.5)), float(np.percentile(col, 97.5))
            theta = float(d["theta"][p])
            inside = bool(lo <= theta <= hi)
            n_tot += 1; n_out += (0 if inside else 1)
            span = d["ub"][p] - d["lb"][p]
            frac = (float(np.mean(((col - d["lb"][p]) / span < 0.01) |
                                  ((d["ub"][p] - col) / span < 0.01)))
                    if span > 0 else np.nan)
            rows.append(dict(condition=c, parameter=name, theta_point=theta,
                             bs_median=med, ci_lo=lo, ci_hi=hi,
                             refined_inside_ci=inside))
            brows.append(dict(condition=c, parameter=name, frac_at_bound=frac))
    ci = pd.DataFrame(rows); ci.to_csv(os.path.join(OUT, "ci_consistency.csv"), index=False)
    bd = pd.DataFrame(brows); bd.to_csv(os.path.join(OUT, "bound_railing.csv"), index=False)
    print(f"  refined optimum outside its OWN (legacy) interval would be common; "
          f"with bootstrap-percentile CIs the reported median is inside by "
          f"construction.  refined-vs-percentile mismatches: {n_out}/{n_tot}")
    # which parameters rail most
    railed = (bd.groupby("parameter").frac_at_bound.mean()
              .sort_values(ascending=False))
    print("  mean fraction of bootstrap draws pinned to a box edge (top 6):")
    for k, v in railed.head(6).items():
        print(f"    {k:14s} {v:.2f}")
    return ci, bd


# ---------------------------------------------------------------------------
# A3 : generalization gap per condition (highlights the S1 RESET outlier)
# ---------------------------------------------------------------------------
def a3_generalization_gap():
    print("[A3] per-condition generalization gap")
    hp = os.path.join(ROOT, "results", "paper_alt", "heldout_validation.csv")
    if not os.path.exists(hp):
        print("  heldout_validation.csv missing (run 08 first); skipped"); return None
    h = pd.read_csv(hp)
    h["gap"] = h["rmse_heldout_median"] - h["rmse_insample"]
    h["gap_rel"] = h["gap"] / h["rmse_insample"]
    h.to_csv(os.path.join(OUT, "generalization_gap.csv"), index=False)
    for br in ("SET", "RESET"):
        s = h[h.branch == br]
        worst = s.loc[s.gap.abs().idxmax()]
        print(f"  {br}: mean gap {s.gap.mean():+.3f} dec, median gap "
              f"{s.gap.median():+.3f} dec, worst {worst.condition} "
              f"({worst.gap:+.3f} dec, {100*worst.gap_rel:+.0f}% of in-sample)")
    return h


# ---------------------------------------------------------------------------
# A4 : aggregate profile-likelihood verdicts over available conditions
# ---------------------------------------------------------------------------
def a4_profile_summary():
    print("[A4] profile-likelihood verdict aggregation")
    rows = []
    for c in CONDS:
        f = os.path.join(ROOT, "results", f"{c}_taofit", "profile_summary.csv")
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f)
        vc = d["verdict"].value_counts().to_dict()
        rows.append(dict(condition=c, n=len(d),
                         flat=vc.get("flat_non_identifiable", 0),
                         weak=vc.get("weakly_identifiable", 0),
                         identifiable=vc.get("identifiable", 0)))
    if not rows:
        print("  no profile_summary.csv found; skipped"); return None
    df = pd.DataFrame(rows)
    tot = df[["n", "flat", "weak", "identifiable"]].sum()
    df.to_csv(os.path.join(OUT, "profile_likelihood_summary.csv"), index=False)
    print(f"  conditions with profile scans: {list(df.condition)}")
    print(f"  pooled: {tot['flat']}/{tot['n']} flat/non-identifiable "
          f"({100*tot['flat']/tot['n']:.0f}%), {tot['weak']} weak, "
          f"{tot['identifiable']} identifiable")
    return df


# ---------------------------------------------------------------------------
# B1 + B2 : Fisher eigenvalue spectrum (sloppiness) and stiff/sloppy directions
# ---------------------------------------------------------------------------
def b1_b2_sloppy_spectrum():
    print("[B1/B2] Fisher eigenspectrum and identifiable directions")
    # use the taofit Fisher matrices (the variability runs disabled Fisher)
    specs, stiff_part, sloppy_part, active_ref = {}, [], [], None
    conds_used = []
    for c in CONDS:
        fp = os.path.join(ROOT, "results", f"{c}_taofit", "fisher_matrix.csv")
        rp = os.path.join(ROOT, "results", f"{c}_taofit", "refined.mat")
        if not (os.path.exists(fp) and os.path.exists(rp)):
            continue
        F = np.loadtxt(fp, delimiter=",")
        F = np.nan_to_num(0.5 * (F + F.T), nan=0.0, posinf=0.0, neginf=0.0)
        ref = sio.loadmat(rp, squeeze_me=True, struct_as_record=False)["refined"]
        names = [str(x) for x in np.ravel(ref.priors.names)]
        active = [str(x) for x in np.ravel(ref.active_names)]
        idx = [names.index(a) for a in active]
        Fa = F[np.ix_(idx, idx)]
        if not np.any(Fa):
            continue
        w, V = np.linalg.eigh(Fa)
        w = np.clip(w, 0, None)
        order = np.argsort(w)[::-1]
        w = w[order]; V = V[:, order]
        specs[c] = w
        stiff_part.append(V[:, 0] ** 2)              # participation in stiffest mode
        sloppy_part.append(V[:, -1] ** 2)            # participation in sloppiest mode
        active_ref = active
        conds_used.append(c)
    if not specs:
        print("  no populated Fisher matrices found; skipped"); return None

    # spectra table (normalized eigenvalues per condition)
    rows = []
    for c in conds_used:
        w = specs[c]
        wmax = w.max()
        wpos = w[w > 0]
        cond_number = (wmax / wpos.min()) if wpos.size else np.inf
        for k, val in enumerate(w):
            rows.append(dict(condition=c, mode=k + 1, eigenvalue=val,
                             eigenvalue_norm=val / wmax if wmax > 0 else np.nan))
        print(f"  {c}: {len(active_ref)} active dirs, log10 dynamic range "
              f"{np.log10(cond_number):.1f}")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "sloppy_spectrum.csv"), index=False)

    stiff_mean = np.mean(stiff_part, axis=0)
    sloppy_mean = np.mean(sloppy_part, axis=0)
    comp = pd.DataFrame(dict(parameter=active_ref,
                             stiff_participation=stiff_mean,
                             sloppy_participation=sloppy_mean))
    comp.to_csv(os.path.join(OUT, "sloppy_directions.csv"), index=False)
    top = comp.sort_values("stiff_participation", ascending=False)
    print("  stiffest (most identifiable) direction dominated by: "
          + ", ".join(f"{r.parameter}({r.stiff_participation:.2f})"
                      for r in top.head(4).itertuples()))

    # ---- figure: spectra fan + stiff-mode composition ----
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2))
    for c in conds_used:
        w = specs[c]
        wn = w / w.max()
        wn = np.clip(wn, 1e-30, None)
        ax1.plot(range(1, len(wn) + 1), wn, "-o", ms=2.5, lw=0.8, alpha=0.6)
    ax1.set_yscale("log")
    ax1.set_xlabel("eigen-direction (stiff $\\rightarrow$ sloppy)")
    ax1.set_ylabel("normalized Fisher eigenvalue")
    ax1.set_title("Sloppy spectrum (all conditions)")

    o = np.argsort(stiff_mean)[::-1]
    ax2.barh(np.arange(len(active_ref)), stiff_mean[o], color="#1f77b4")
    ax2.set_yticks(np.arange(len(active_ref)))
    ax2.set_yticklabels([active_ref[i] for i in o], fontsize=6.5)
    ax2.invert_yaxis()
    ax2.set_xlabel("participation in stiffest mode")
    ax2.set_title("Identifiable direction composition")
    fig.tight_layout()
    savefig(fig, "sloppy_spectrum")
    return comp


# ---------------------------------------------------------------------------
# B3 : formal DOE response surface + lack-of-fit on identifiable parameters
# ---------------------------------------------------------------------------
def _ols_doe(y, X):
    """Return beta, se, t, p, ss_resid, resid for an OLS fit."""
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, p = X.shape
    dof = n - p
    ss_resid = float(resid @ resid)
    sigma2 = ss_resid / dof if dof > 0 else np.nan
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.clip(np.diag(sigma2 * xtx_inv), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = beta / se
    pvals = 2 * stats.t.sf(np.abs(t), dof) if dof > 0 else np.full_like(beta, np.nan)
    return beta, se, t, pvals, ss_resid, resid


def b3_doe_response_surface():
    print("[B3] DOE response-surface significance + lack-of-fit")
    data = {c: load_variability(c) for c in CONDS}
    data = {c: d for c, d in data.items() if d}
    terms = ["intercept", "O2", "Power", "O2:Power", "O2^2", "Power^2"]
    x1 = np.array([O2_CODE[DOE[c][0]] for c in data])
    x2 = np.array([PW_CODE[DOE[c][1]] for c in data])
    X = np.column_stack([np.ones_like(x1), x1, x2, x1 * x2, x1**2, x2**2])
    center = np.array([c in CENTER for c in data])

    out = []
    targets = [("V0_set", False), ("V0_res", False), ("Rs", True)]
    for name, uselog in targets:
        y = np.array([bs_median(data[c], name) for c in data])
        if uselog:
            y = np.log10(np.clip(y, 1e-30, None))
        beta, se, t, pv, ss_resid, _ = _ols_doe(y, X)
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ss_resid / ss_tot if ss_tot > 0 else np.nan
        # lack-of-fit using center-point pure error
        yc = y[center]
        ss_pe = float(np.sum((yc - yc.mean()) ** 2)); df_pe = yc.size - 1
        df_resid = len(y) - X.shape[1]
        ss_lof = ss_resid - ss_pe; df_lof = df_resid - df_pe
        if df_lof > 0 and df_pe > 0 and ss_pe > 0:
            F_lof = (ss_lof / df_lof) / (ss_pe / df_pe)
            p_lof = float(stats.f.sf(F_lof, df_lof, df_pe))
        else:
            F_lof = p_lof = np.nan
        label = f"log10({name})" if uselog else name
        for term, b, s, p in zip(terms, beta, se, pv):
            out.append(dict(response=label, term=term, coef=b, se=s, p_value=p,
                            model_R2=r2, lack_of_fit_F=F_lof, lack_of_fit_p=p_lof))
        sig = [terms[k] for k in range(1, len(terms)) if pv[k] < 0.05]
        print(f"  {label:12s} R2={r2:.2f}  significant terms (p<.05): "
              f"{sig if sig else 'none'}  lack-of-fit p="
              f"{p_lof:.2f}" if np.isfinite(p_lof) else
              f"  {label}: R2={r2:.2f}")
    pd.DataFrame(out).to_csv(os.path.join(OUT, "doe_response_surface.csv"),
                             index=False)
    print("  wrote results/robustness/doe_response_surface.csv")
    return out


# ---------------------------------------------------------------------------
# B4 : cycle-to-cycle vs device-to-device variance from the center replicates
# ---------------------------------------------------------------------------
def b4_variance_components():
    print("[B4] variance components from replicated center points (S9-S12)")
    data = {c: load_variability(c) for c in CENTER}
    data = {c: d for c, d in data.items() if d}
    if len(data) < 2:
        print("  insufficient center-point runs; skipped"); return None
    any_d = next(iter(data.values()))
    rows = []
    for name in any_d["active"]:
        meds, within = [], []
        for c, d in data.items():
            p = d["names"].index(name)
            col = d["tbs"][:, p]; col = col[np.isfinite(col)]
            if col.size == 0:
                continue
            meds.append(np.median(col))
            within.append(np.var(col, ddof=1))
        meds = np.array(meds)
        if meds.size < 2:
            continue
        grand = np.mean(np.abs(meds)) or np.nan
        between_var = float(np.var(meds, ddof=1))           # device-to-device
        within_var = float(np.mean(within))                 # cycle-to-cycle
        icc = between_var / (between_var + within_var) if (between_var + within_var) > 0 else np.nan
        rows.append(dict(parameter=name,
                         device_to_device_cv=np.sqrt(between_var) / grand,
                         cycle_to_cycle_cv=np.sqrt(within_var) / grand,
                         var_ratio_dev_over_cycle=(between_var / within_var
                                                   if within_var > 0 else np.inf),
                         icc_device_fraction=icc))
    vc = pd.DataFrame(rows)
    vc.to_csv(os.path.join(OUT, "variance_components.csv"), index=False)
    print("  parameter        dev-to-dev CV   cycle CV   ICC(device frac)")
    for r in vc.itertuples():
        print(f"  {r.parameter:14s} {r.device_to_device_cv:9.2f} "
              f"{r.cycle_to_cycle_cv:10.2f} {r.icc_device_fraction:12.2f}")

    # figure: a few representative parameters
    show = [p for p in ["V0_set", "V0_res", "Rs", "I0", "Ea_set", "Vel0_set"]
            if p in set(vc.parameter)]
    sub = vc.set_index("parameter").loc[show]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    xx = np.arange(len(show)); w = 0.38
    ax.bar(xx - w / 2, sub.cycle_to_cycle_cv, w, label="cycle-to-cycle",
           color="#1f77b4")
    ax.bar(xx + w / 2, sub.device_to_device_cv, w, label="device-to-device",
           color="#d62728")
    ax.set_xticks(xx); ax.set_xticklabels(show, rotation=30, ha="right")
    ax.set_ylabel("coefficient of variation")
    ax.set_title("Cycle-to-cycle vs device-to-device spread (center points)")
    ax.legend(frameon=False)
    fig.tight_layout()
    savefig(fig, "variance_components")
    return vc


if __name__ == "__main__":
    print("Robustness + novelty post-processing -> results/robustness/\n")
    a1_a2_interval_diagnostics()
    a3_generalization_gap()
    a4_profile_summary()
    b1_b2_sloppy_spectrum()
    b3_doe_response_surface()
    b4_variance_components()
    print("\nDone.")
