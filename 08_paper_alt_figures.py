#!/usr/bin/env python3
"""
08_paper_alt_figures.py
=======================
Post-processing for the *reframed* manuscript (Latex_main/main_alt.tex).

Generates, from EXISTING result files only (no new HSPICE simulation):

  (A) Deposition-condition trends of the bootstrap-identifiable parameter
      combinations (R_s, V0_set, V0_res) vs O2% and sputter power, with
      cycle-bootstrap 95% CI error bars.                 -> deposition_trends.{pdf,png}
  (B) HRS interface response: dynamic relative permittivity implied by the
      post-RESET Schottky window vs O2%.                 -> hrs_schottky_trend.{pdf,png}
  (C) Held-out (out-of-sample) generalization: the model fitted to the medoid
      cycle is scored against every OTHER measured cycle of the same device.
      Per-cycle RMSE distribution per condition + an S1 overlay against the
      measured cycle-to-cycle envelope.                  -> heldout_rmse.{pdf,png},
                                                            heldout_overlay_S1.{pdf,png}

Outputs land in results/paper_alt/ ; originals are never modified.

Reconstruction of the simulated curve (no re-simulation):
  validation.mat stores the validation residual r = log10|I_sim| - log10|I_meas,medoid|
  on the same 402(SET)/202(RESET) butterfly grid as the medoid fit target.
  Hence log10|I_sim| = log10|I_meas,medoid| + r  (verified: sqrt(mean r^2) == reported RMSE).
  Each non-medoid measured cycle in *_cycle_ensemble.csv lives on the same grid,
  so per-cycle held-out RMSE is a direct point-by-point comparison.
"""

import os
import glob
import numpy as np
import pandas as pd
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "results", "paper_alt")
os.makedirs(OUT, exist_ok=True)

CONDS = [f"S{i}" for i in range(1, 13)]

# Deposition design of experiments (Table I of the manuscript).
DOE = {
    "S1": (20.0, 75.0),   "S2": (20.0, 250.0),
    "S3": (35.0, 75.0),   "S4": (35.0, 250.0),
    "S5": (20.0, 162.5),  "S6": (35.0, 162.5),
    "S7": (27.5, 75.0),   "S8": (27.5, 250.0),
    "S9": (27.5, 162.5),  "S10": (27.5, 162.5),
    "S11": (27.5, 162.5), "S12": (27.5, 162.5),
}

plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "figure.dpi": 150, "savefig.bbox": "tight", "axes.grid": True,
    "grid.alpha": 0.3, "lines.linewidth": 1.3,
})


def savefig(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote results/paper_alt/{name}.pdf (+png)")


def find_one(pattern):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return hits[0] if hits else None


# ----------------------------------------------------------------------------
# (A) Deposition trends of bootstrap-identifiable parameter combinations
# ----------------------------------------------------------------------------
def deposition_trends():
    print("[A] Deposition trends of identifiable parameters")
    cis = pd.read_csv(os.path.join(ROOT, "results/variability/parameter_cis.csv"))
    # parameters featured as most reliably constrained (bootstrap CV + Fisher recurrence)
    params = ["Rs", "V0_set", "V0_res"]
    labels = {
        "Rs": r"$R_s$  ($\Omega$)",
        "V0_set": r"$V_{0,\mathrm{SET}}$  (V)",
        "V0_res": r"$V_{0,\mathrm{RESET}}$  (V)",
    }
    rows = []
    fig, axes = plt.subplots(len(params), 2, figsize=(7.0, 6.4), sharex="col")
    for i, p in enumerate(params):
        sub = cis[cis.parameter == p].set_index("condition")
        for c in CONDS:
            if c not in sub.index:
                continue
            o2, pw = DOE[c]
            r = sub.loc[c]
            rows.append(dict(condition=c, o2_pct=o2, power_W=pw, parameter=p,
                             theta=r.theta, ci_lo=r.ci_lo, ci_hi=r.ci_hi, cv=r.cv))
        df = pd.DataFrame([x for x in rows if x["parameter"] == p])
        logp = (p == "Rs")
        for j, (xkey, xlab) in enumerate([("o2_pct", r"O$_2$ (%)"),
                                          ("power_W", "Sputter power (W)")]):
            ax = axes[i, j]
            other = "power_W" if xkey == "o2_pct" else "o2_pct"
            for lev, mk, col in zip(sorted(df[other].unique()),
                                    ["o", "s", "^", "D"],
                                    ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]):
                d = df[df[other] == lev]
                yerr = np.vstack([np.clip(d.theta - d.ci_lo, 0, None),
                                  np.clip(d.ci_hi - d.theta, 0, None)])
                ax.errorbar(d[xkey], d.theta, yerr=yerr, fmt=mk, color=col,
                            ms=4.5, capsize=2, lw=0.9, elinewidth=0.8,
                            label=f"{other.split('_')[0]}={lev:g}")
            if logp:
                ax.set_yscale("log")
            if i == len(params) - 1:
                ax.set_xlabel(xlab)
            if j == 0:
                ax.set_ylabel(labels[p])
            if i == 0 and j == 0:
                ax.legend(title="held factor", ncol=1, frameon=False, fontsize=6.3)
    fig.suptitle("Bootstrap-identifiable parameters vs deposition condition "
                 "(error bars: cycle-bootstrap 95% CI)", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    savefig(fig, "deposition_trends")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "deposition_trends.csv"), index=False)
    print("  wrote results/paper_alt/deposition_trends.csv")


# ----------------------------------------------------------------------------
# (B) HRS interface dielectric response vs stoichiometry
# ----------------------------------------------------------------------------
def hrs_schottky_trend():
    print("[B] HRS Schottky dynamic permittivity vs O2%")
    rm = pd.read_csv(os.path.join(ROOT, "results/variability/regime_maps_all.csv"))
    rm = rm[(rm.state == "RESET_HRS_POST") & (rm.mechanism == "schottky")].copy()
    rm = rm.dropna(subset=["eps_r_dyn"])
    rows = []
    for c in CONDS:
        d = rm[rm.condition == c]
        if len(d) == 0:
            continue
        # representative window = widest (most points)
        w = d.loc[d.n_points.idxmax()]
        o2, pw = DOE[c]
        rows.append(dict(condition=c, o2_pct=o2, power_W=pw,
                         eps_r_dyn=float(w.eps_r_dyn), slope=float(w.slope),
                         r2=float(w.r2), n_points=int(w.n_points)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "hrs_schottky_trend.csv"), index=False)
    print("  wrote results/paper_alt/hrs_schottky_trend.csv")

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    for ax, xkey, xlab, other in [
        (axes[0], "o2_pct", r"O$_2$ (%)", "power_W"),
        (axes[1], "power_W", "Sputter power (W)", "o2_pct")]:
        for lev, mk, col in zip(sorted(df[other].unique()),
                                ["o", "s", "^", "D"],
                                ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]):
            d = df[df[other] == lev]
            ax.scatter(d[xkey], d.eps_r_dyn, marker=mk, color=col, s=34,
                       label=f"{other.split('_')[0]}={lev:g}", zorder=3)
            for _, r in d.iterrows():
                ax.annotate(r.condition, (r[xkey], r.eps_r_dyn),
                            textcoords="offset points", xytext=(4, 3), fontsize=6)
        ax.axhspan(1, 60, color="grey", alpha=0.08, zorder=0)
        ax.set_xlabel(xlab)
        ax.set_ylabel(r"$\varepsilon_r^{\mathrm{dyn}}$ (post-RESET HRS Schottky)")
        ax.legend(frameon=False, fontsize=6.3)
    fig.suptitle("Interface (Schottky) dynamic permittivity of the HRS "
                 "vs deposition condition", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    savefig(fig, "hrs_schottky_trend")


# ----------------------------------------------------------------------------
# (C) Held-out / out-of-sample generalization
# ----------------------------------------------------------------------------
def _load_medoid_and_sim(cond):
    """Return dict[branch] -> (voltage, logI_meas_medoid, logI_sim) on common grid."""
    rep_path = find_one(f"step02_{cond}/*_representative_curve_FIXED.csv")
    val_path = os.path.join(ROOT, f"results/ablation/{cond}/physics_regime_bo/validation.mat")
    if rep_path is None or not os.path.exists(val_path):
        return None
    rep = pd.read_csv(rep_path)
    val = sio.loadmat(val_path, squeeze_me=True, struct_as_record=False)["val"]
    resid = {"SET": np.atleast_1d(val.r_set).astype(float),
             "RESET": np.atleast_1d(val.r_res).astype(float)}
    out = {}
    for br in ("SET", "RESET"):
        m = rep[rep.branch == br].sort_values("butterfly_sequence_index")
        logI_med = m["median_log10_abs_current"].to_numpy()
        V = m["voltage_V"].to_numpy()
        r = resid[br]
        if logI_med.size != r.size:
            n = min(logI_med.size, r.size)
            logI_med, V, r = logI_med[:n], V[:n], r[:n]
        out[br] = (V, logI_med, logI_med + r)  # I_sim = medoid + residual
    return out


def _ensemble_cycles(cond):
    """dict[branch] -> (cycle_ids, logI matrix [n_cycle x n_point]) on common grid."""
    ens_path = find_one(f"step02_{cond}/*_cycle_ensemble.csv")
    if ens_path is None:
        return None
    e = pd.read_csv(ens_path)
    res = {}
    for br in ("SET", "RESET"):
        d = e[e.branch == br]
        piv = d.pivot_table(index="representative_cycle_id",
                            columns="butterfly_sequence_index",
                            values="median_log10_abs_current")
        piv = piv.sort_index(axis=1)
        res[br] = (piv.index.to_numpy(), piv.to_numpy())
    return res


def heldout_validation():
    print("[C] Held-out generalization across measured cycles")
    summary = []
    per_cycle = {}  # cond -> dict(branch -> array of rmse per cycle)
    for cond in CONDS:
        sim = _load_medoid_and_sim(cond)
        ens = _ensemble_cycles(cond)
        if sim is None or ens is None:
            print(f"  {cond}: missing files, skipped")
            continue
        per_cycle[cond] = {}
        for br in ("SET", "RESET"):
            V, logI_med, logI_sim = sim[br]
            cyc_ids, M = ens[br]
            # align grid length
            n = min(M.shape[1], logI_sim.size)
            logI_sim_b = logI_sim[:n]
            M = M[:, :n]
            # per-cycle RMSE of the fitted curve vs each measured cycle
            diff = M - logI_sim_b[None, :]
            rmse = np.sqrt(np.nanmean(diff**2, axis=1))
            per_cycle[cond][br] = rmse
            # in-sample (medoid) RMSE for reference = sqrt(mean (logI_sim-logI_med)^2)
            insample = float(np.sqrt(np.nanmean((logI_sim_b - logI_med[:n])**2)))
            # envelope coverage: fraction of grid points where sim within cycle min..max
            lo = np.nanmin(M, axis=0); hi = np.nanmax(M, axis=0)
            q25 = np.nanpercentile(M, 25, axis=0); q75 = np.nanpercentile(M, 75, axis=0)
            frac_minmax = float(np.mean((logI_sim_b >= lo) & (logI_sim_b <= hi)))
            frac_iqr = float(np.mean((logI_sim_b >= q25) & (logI_sim_b <= q75)))
            summary.append(dict(
                condition=cond, branch=br, n_cycles=int(np.sum(~np.isnan(rmse))),
                rmse_insample=round(insample, 4),
                rmse_heldout_median=round(float(np.nanmedian(rmse)), 4),
                rmse_heldout_p05=round(float(np.nanpercentile(rmse, 5)), 4),
                rmse_heldout_p95=round(float(np.nanpercentile(rmse, 95)), 4),
                frac_within_minmax=round(frac_minmax, 3),
                frac_within_iqr=round(frac_iqr, 3),
            ))
        sset = per_cycle[cond]["SET"]; sres = per_cycle[cond]["RESET"]
        print(f"  {cond}: SET held-out RMSE median {np.nanmedian(sset):.3f} "
              f"(in-sample {summary[-2]['rmse_insample']:.3f}), "
              f"RESET {np.nanmedian(sres):.3f} (in-sample {summary[-1]['rmse_insample']:.3f}), "
              f"n_cycles SET={len(sset)}")
    sdf = pd.DataFrame(summary)
    sdf.to_csv(os.path.join(OUT, "heldout_validation.csv"), index=False)
    print("  wrote results/paper_alt/heldout_validation.csv")

    # --- Figure: per-condition held-out RMSE distributions ---
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), sharey=False)
    for ax, br, title in [(axes[0], "SET", "SET branch"),
                          (axes[1], "RESET", "RESET branch")]:
        data = [per_cycle[c][br][~np.isnan(per_cycle[c][br])] for c in CONDS if c in per_cycle]
        labs = [c for c in CONDS if c in per_cycle]
        bp = ax.boxplot(data, positions=range(len(data)), widths=0.6,
                        showfliers=False, patch_artist=True)
        for box in bp["boxes"]:
            box.set(facecolor="#cfe3f7", alpha=0.8, linewidth=0.7)
        for med in bp["medians"]:
            med.set(color="#1f4e79", linewidth=1.1)
        # overlay in-sample (medoid) RMSE markers
        ins = sdf[sdf.branch == br].set_index("condition")
        ax.scatter(range(len(labs)), [ins.loc[c].rmse_insample for c in labs],
                   marker="*", color="#d62728", s=55, zorder=4,
                   label="in-sample (medoid)")
        ax.set_xticks(range(len(labs)))
        ax.set_xticklabels(labs, rotation=45, fontsize=6.5)
        ax.set_ylabel(r"RMSE of $\log_{10}|I|$ (decades)")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Out-of-sample fit quality: model fitted to the medoid cycle, "
                 "scored on every other measured cycle", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    savefig(fig, "heldout_rmse")

    # --- Figure: S1 overlay vs measured cycle envelope ---
    cond = "S1"
    sim = _load_medoid_and_sim(cond); ens = _ensemble_cycles(cond)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1))
    for ax, br in zip(axes, ("SET", "RESET")):
        V, logI_med, logI_sim = sim[br]
        cyc_ids, M = ens[br]
        n = min(M.shape[1], logI_sim.size, V.size)
        V = V[:n]; logI_sim = logI_sim[:n]; M = M[:, :n]
        lo = np.nanmin(M, axis=0); hi = np.nanmax(M, axis=0)
        q25 = np.nanpercentile(M, 25, axis=0); q75 = np.nanpercentile(M, 75, axis=0)
        med = np.nanmedian(M, axis=0)
        # x = sweep-sample index: the butterfly sweep is non-monotonic in V,
        # so the cycle-to-cycle envelope is only well defined along the sweep
        # sequence (a secondary voltage axis is added on top for reference).
        x = np.arange(n)
        ax.fill_between(x, lo, hi, color="#bbbbbb", alpha=0.45,
                        label="measured cycles min--max")
        ax.fill_between(x, q25, q75, color="#888888", alpha=0.5,
                        label="measured IQR")
        ax.plot(x, med, color="k", lw=1.0, label="measured median")
        ax.plot(x, logI_sim, color="#d62728", lw=1.5, label="fitted (Stanford)")
        ax.set_xlabel("sweep sample index")
        ax.set_ylabel(r"$\log_{10}|I|$")
        ax.set_title(f"S1 {br}")
        # secondary axis: voltage at a few sweep indices
        secx = ax.twiny()
        secx.set_xlim(ax.get_xlim())
        ticks = np.linspace(0, n - 1, 5).astype(int)
        secx.set_xticks(ticks)
        secx.set_xticklabels([f"{V[t]:.1f}" for t in ticks], fontsize=6.5)
        secx.set_xlabel("voltage (V)", fontsize=7)
        if br == "SET":
            ax.legend(frameon=False, fontsize=6.3, loc="lower right")
    fig.suptitle("S1: fitted curve vs measured cycle-to-cycle envelope", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    savefig(fig, "heldout_overlay_S1")

    # aggregate one-liners for the paper
    g = sdf.groupby("branch")
    print("\n  AGGREGATE (for manuscript text):")
    for br in ("SET", "RESET"):
        s = sdf[sdf.branch == br]
        print(f"   {br}: mean in-sample {s.rmse_insample.mean():.3f}, "
              f"mean held-out median {s.rmse_heldout_median.mean():.3f}, "
              f"mean within-minmax {100*s.frac_within_minmax.mean():.1f}%, "
              f"within-IQR {100*s.frac_within_iqr.mean():.1f}%")


if __name__ == "__main__":
    print("Writing reframed-paper figures to results/paper_alt/\n")
    deposition_trends()
    hrs_schottky_trend()
    heldout_validation()
    print("\nDone.")
