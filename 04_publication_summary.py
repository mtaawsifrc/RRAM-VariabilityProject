#!/usr/bin/env python3
"""Aggregate per-condition TaO-Fit results into publication assets.

Reads results/S*_taofit/{refined,fisher_report,validation}.mat and writes:
  results/publication/parameter_table.csv     - fitted params + Fisher rel. uncertainty + identifiability flag
  results/publication/fit_quality.csv         - RMSE / Durbin-Watson per condition
  results/publication/identifiability_heatmap.{png,pdf}
  results/publication/fit_quality.{png,pdf}
  results/publication/key_parameters.{png,pdf}

Pure analysis of existing outputs; does not re-run any fit.
"""
import os, glob
import numpy as np
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "results", "publication")
os.makedirs(OUT, exist_ok=True)
CONDS = [f"S{i}" for i in range(1, 13)]
ID_THRESH = 0.5  # rel_sigma < 0.5  => "identifiable" (matches stage2 well_idx)


def load(p):
    return sio.loadmat(p, squeeze_me=True, struct_as_record=False)


def sc(x):
    a = np.ravel(np.asarray(x))
    return float(a[0]) if a.size and a.dtype.kind in "fiu" else np.nan


def get(cond):
    d = os.path.join(ROOT, "results", f"{cond}_taofit")
    ref = load(os.path.join(d, "refined.mat"))["refined"]
    names = [str(x) for x in np.ravel(ref.priors.names)]
    theta = np.asarray(ref.theta, dtype=float).ravel()
    active = set(str(x) for x in np.ravel(ref.active_names))
    fish = load(os.path.join(d, "fisher_report.mat"))["fish"]
    rel = np.asarray(fish.rel_sigma, dtype=float).ravel()
    F = np.asarray(fish.F, dtype=float)
    eig = np.asarray(fish.eigvals, dtype=float).ravel()
    pos = eig[eig > 0]
    cond_num = (pos.max() / pos.min()) if pos.size else np.nan
    fisher_ok = bool(np.count_nonzero(F))
    val = load(os.path.join(d, "validation.mat"))["val"]
    return dict(names=names, theta=theta, active=active, rel=rel,
                cond_num=cond_num, fisher_ok=fisher_ok,
                rmse_set=sc(val.rmse_set), rmse_res=sc(val.rmse_res),
                dw_set=sc(val.dw_set), dw_res=sc(val.dw_res))


data = {c: get(c) for c in CONDS}
NAMES = data["S1"]["names"]
ACTIVE = [n for n in NAMES if n in data["S1"]["active"]]

# ---- parameter table (value | rel_sigma | identifiable) ----
rows = []
hdr = ["condition"]
for n in ACTIVE:
    hdr += [f"{n}", f"{n}_relsig", f"{n}_identif"]
hdr += ["n_identifiable", "fisher_cond_number", "fisher_ok"]
rows.append(",".join(hdr))
for c in CONDS:
    d = data[c]
    idx = {n: i for i, n in enumerate(d["names"])}
    cells = [c]
    nid = 0
    for n in ACTIVE:
        i = idx[n]
        v, r = d["theta"][i], d["rel"][i]
        ok = int(np.isfinite(r) and r < ID_THRESH)
        nid += ok
        cells += [f"{v:.6g}", f"{r:.4g}", str(ok)]
    cells += [str(nid), f"{d['cond_num']:.4g}", str(int(d["fisher_ok"]))]
    rows.append(",".join(cells))
with open(os.path.join(OUT, "parameter_table.csv"), "w") as f:
    f.write("\n".join(rows) + "\n")

# ---- fit quality table ----
with open(os.path.join(OUT, "fit_quality.csv"), "w") as f:
    f.write("condition,rmse_set_dec,rmse_res_dec,dw_set,dw_res\n")
    for c in CONDS:
        d = data[c]
        f.write(f"{c},{d['rmse_set']:.4f},{d['rmse_res']:.4f},{d['dw_set']:.4f},{d['dw_res']:.4f}\n")

# ---- Figure: identifiability heatmap (rel_sigma, log scale) ----
M = np.full((len(ACTIVE), len(CONDS)), np.nan)
for j, c in enumerate(CONDS):
    idx = {n: i for i, n in enumerate(data[c]["names"])}
    for i, n in enumerate(ACTIVE):
        M[i, j] = data[c]["rel"][idx[n]]
fig, ax = plt.subplots(figsize=(8, 7))
logM = np.log10(np.clip(M, 1e-3, 1e3))
im = ax.imshow(logM, aspect="auto", cmap="RdYlGn_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(CONDS))); ax.set_xticklabels(CONDS, rotation=45, ha="right")
ax.set_yticks(range(len(ACTIVE))); ax.set_yticklabels(ACTIVE)
# mark identifiable cells (rel_sigma < threshold)
for i in range(len(ACTIVE)):
    for j in range(len(CONDS)):
        if np.isfinite(M[i, j]) and M[i, j] < ID_THRESH:
            ax.text(j, i, "●", ha="center", va="center", fontsize=5, color="black")
cb = fig.colorbar(im, ax=ax); cb.set_label(r"$\log_{10}$ relative uncertainty  $\sigma_\theta/|\theta|$ (Fisher CRLB)")
ax.set_title(f"Parameter identifiability across conditions\n(● = identifiable, rel. uncertainty < {ID_THRESH})")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT, f"identifiability_heatmap.{ext}"), dpi=300)
plt.close(fig)

# ---- Figure: fit quality per condition ----
x = np.arange(len(CONDS)); w = 0.38
fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
a1.bar(x - w/2, [data[c]["rmse_set"] for c in CONDS], w, label="SET")
a1.bar(x + w/2, [data[c]["rmse_res"] for c in CONDS], w, label="RESET")
a1.set_ylabel("RMSE (decades)"); a1.legend(); a1.grid(axis="y", alpha=.3)
a1.set_title("Fit quality per condition")
a2.bar(x - w/2, [data[c]["dw_set"] for c in CONDS], w, label="SET")
a2.bar(x + w/2, [data[c]["dw_res"] for c in CONDS], w, label="RESET")
a2.axhline(2.0, ls="--", c="k", lw=1, label="DW=2 (no autocorr.)")
a2.set_ylabel("Durbin-Watson"); a2.set_xticks(x); a2.set_xticklabels(CONDS, rotation=45, ha="right")
a2.legend(); a2.grid(axis="y", alpha=.3)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT, f"fit_quality.{ext}"), dpi=300)
plt.close(fig)

# ---- Figure: key shared parameters across conditions (with CRLB error bars) ----
KEY = ["I0", "g0", "Rs", "V0_set", "V0_res", "gamma0_set"]
fig, axes = plt.subplots(2, 3, figsize=(11, 6))
for ax, n in zip(axes.ravel(), KEY):
    vals, errs = [], []
    for c in CONDS:
        idx = {nm: i for i, nm in enumerate(data[c]["names"])}
        i = idx[n]; v = data[c]["theta"][i]; r = data[c]["rel"][i]
        vals.append(v); errs.append(abs(v) * r if np.isfinite(r) else 0)
    ax.errorbar(range(len(CONDS)), vals, yerr=errs, fmt="o-", capsize=3, ms=4)
    ax.set_title(n); ax.set_xticks(range(len(CONDS)))
    ax.set_xticklabels(CONDS, rotation=90, fontsize=6); ax.grid(alpha=.3)
fig.suptitle("Extracted parameters vs condition (error bars = Fisher CRLB)")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT, f"key_parameters.{ext}"), dpi=300)
plt.close(fig)

# ---- console summary ----
print("Fisher computed (nonzero F):", sum(data[c]["fisher_ok"] for c in CONDS), "/ 12")
print("Mean #identifiable params/condition:",
      np.mean([sum(int(np.isfinite(data[c]["rel"][i]) and data[c]["rel"][i] < ID_THRESH)
                   for i, n in enumerate(data[c]["names"]) if n in ACTIVE) for c in CONDS]))
print("Wrote ->", OUT)
