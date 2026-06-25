#!/usr/bin/env python3
"""
10_population_validation.py
===========================
Split-safe population / device-level validation (roadmap 2.1).

The earlier "out-of-sample" test (08_paper_alt_figures.py) only scores the
fitted medoid curve against OTHER CYCLES OF THE SAME fitted device.  That shows
cycle-to-cycle reproducibility, not that the parameters generalize across the
device population.  This script adds the genuinely held-out test: it scores the
already-fitted model against cycles of devices that were NEVER used for medoid
selection or fitting.

Everything here is pure re-analysis of data already in the repo
(raw_data/<cond>/*.csv + the archived fit residuals); no new HSPICE / MATLAB.

What it does
------------
1. Population index over ALL devices/cycles per condition (one row per cycle,
   one per device), reusing the cycle parser/quality gate of step 01.
2. Deterministic, seeded device-level train/val/test splits per condition.  All
   cycles of a device stay in one split (no device leakage); the device that was
   actually fitted (step02 representative curve) is forced into TRAIN.
3. Unseen-DEVICE validation: the medoid-fitted simulated curve (reconstructed
   from the archived validation residuals, no re-simulation) is scored against
   every good cycle of the TEST-split devices, aligned by half-sweep voltage.
4. Reports BOTH numbers side by side: (a) same-device cycle hold-out (from
   results/paper_alt/heldout_validation.csv) and (b) unseen-device validation,
   per condition and per branch -- never conflated.
5. Acceptance checks: no device in >1 split; the fitted device is excluded from
   val/test; unseen-device cycles come only from devices never fitted/selected.

Outputs (results/population/):
  population_index.csv              one row per (condition, device, cycle)
  population_devices.csv            one row per (condition, device)
  device_splits.csv                 device -> split, is_fitted_device
  unseen_device_validation.csv      per condition/branch: unseen vs same-device
  population_validation_summary.csv aggregate + acceptance-check results
  unseen_device_validation.{pdf,png}

Usage:
  python3 10_population_validation.py                 # all conditions
  python3 10_population_validation.py S1 S2           # a subset
  python3 10_population_validation.py --seed 7 --test-frac 0.25
"""

import argparse
import glob
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "population"
CONDS = [f"S{i}" for i in range(1, 13)]
I_FLOOR = 1e-13


def _load_step01_module():
    """Load 01_extract_clean_cycles.py (name starts with a digit) by path."""
    spec = importlib.util.spec_from_file_location(
        "extract01", str(ROOT / "01_extract_clean_cycles.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # needed for dataclass type resolution
    spec.loader.exec_module(mod)
    return mod


EX = _load_step01_module()


class _QArgs:
    """Quality-gate thresholds mirroring 01_extract_clean_cycles defaults."""
    current_floor = I_FLOOR
    min_points = 40
    min_vspan = 1.0
    min_abs_vmax = 0.5
    min_peak_current = 1e-9
    max_peak_current = 1.0
    min_dynamic_decades = 0.5
    require_set_reset = True


# ---------------------------------------------------------------------------
# 1. Population index
# ---------------------------------------------------------------------------
def build_population_index(conds):
    """Enumerate every cycle of every device per condition from raw_data/."""
    qargs = _QArgs()
    cyc_rows, dev_rows = [], []
    for c in conds:
        if not (ROOT / "raw_data" / c).is_dir():
            print(f"  [{c}] no raw_data dir; skipped")
            continue
        cycles = _collect_condition(c)
        per_dev = {}
        for cyc in cycles:
            q = EX.cycle_quality(cyc, qargs)
            branches = set(b.title and EX.infer_branch(b.title, b.voltage)
                           for b in cyc.blocks)
            cyc_rows.append(dict(
                condition=c, device_id=cyc.device_id, cycle_id=cyc.cycle_number,
                file=cyc.path.name, is_good=bool(q["is_good"]),
                quality_score=q["quality_score"], reject_reason=q["reject_reason"],
                has_set=int("SET" in branches), has_reset=int("RESET" in branches),
            ))
            d = per_dev.setdefault(cyc.device_id,
                                   dict(total=0, good=0))
            d["total"] += 1
            d["good"] += int(q["is_good"])
        for dev, d in per_dev.items():
            dev_rows.append(dict(condition=c, device_id=dev,
                                 total_cycles=d["total"], good_cycles=d["good"]))
        ng = sum(r["good"] for r in per_dev.values())
        print(f"  [{c}] {len(per_dev)} devices, {len(cycles)} cycles, "
              f"{ng} good cycles")
    return pd.DataFrame(cyc_rows), pd.DataFrame(dev_rows)


def fitted_device(cond):
    """Device_id of the representative curve actually fitted for this condition."""
    hits = sorted(glob.glob(str(ROOT / f"step02_{cond}/*_representative_curve_FIXED.csv")))
    if not hits:
        return None
    try:
        rep = pd.read_csv(hits[0], usecols=["device_id"])
        return str(rep["device_id"].iloc[0])
    except Exception:
        # fall back to filename: <cond>_<device>_representative_curve_FIXED.csv
        stem = Path(hits[0]).name
        return stem.replace(f"{cond}_", "").replace(
            "_representative_curve_FIXED.csv", "")


# ---------------------------------------------------------------------------
# 2. Deterministic device-level splits (no device leakage)
# ---------------------------------------------------------------------------
def make_device_splits(dev_df, conds, seed, val_frac, test_frac):
    rows = []
    for c in conds:
        d = dev_df[(dev_df.condition == c) & (dev_df.good_cycles > 0)]
        devices = sorted(d.device_id.unique())
        if not devices:
            continue
        fit_dev = fitted_device(c)
        rng = np.random.default_rng(abs(hash((seed, c))) % (2**32))
        others = [x for x in devices if x != fit_dev]
        rng.shuffle(others)
        n = len(others)
        n_test = int(round(test_frac * len(devices)))
        n_val = int(round(val_frac * len(devices)))
        test = set(others[:n_test])
        val = set(others[n_test:n_test + n_val])
        for dev in devices:
            if dev == fit_dev:
                split = "train"          # fitted device forced into train
            elif dev in test:
                split = "test"
            elif dev in val:
                split = "val"
            else:
                split = "train"
            rows.append(dict(condition=c, device_id=dev, split=split,
                             is_fitted_device=int(dev == fit_dev)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Reconstruct the fitted simulated curve (no re-simulation)
# ---------------------------------------------------------------------------
def load_medoid_sim(cond):
    """dict[branch] -> (V_signed, logI_sim) on the medoid grid, plus medoid id."""
    rep_hits = sorted(glob.glob(str(ROOT / f"step02_{cond}/*_representative_curve_FIXED.csv")))
    val_path = ROOT / f"results/ablation/{cond}/physics_regime_bo/validation.mat"
    if not rep_hits or not val_path.exists():
        return None
    rep = pd.read_csv(rep_hits[0])
    val = sio.loadmat(val_path, squeeze_me=True, struct_as_record=False)["val"]
    resid = {"SET": np.atleast_1d(val.r_set).astype(float),
             "RESET": np.atleast_1d(val.r_res).astype(float)}
    out = {}
    for br in ("SET", "RESET"):
        m = rep[rep.branch == br].sort_values("butterfly_sequence_index")
        logI_med = m["median_log10_abs_current"].to_numpy(float)
        V = m["voltage_V"].to_numpy(float)
        r = resid[br]
        nmin = min(logI_med.size, r.size, V.size)
        if nmin < 5:
            continue
        out[br] = (V[:nmin], logI_med[:nmin] + r[:nmin])   # I_sim = medoid + resid
    return out


def _halves(V):
    """Indices of the rising-|V| and falling-|V| half-sweeps (split at |V| peak)."""
    a = np.abs(V)
    ipk = int(np.argmax(a))
    fwd = np.arange(0, ipk + 1)
    ret = np.arange(ipk, len(V))
    return fwd, ret


def _interp_sim_to_target(Vsim, logIsim, Vtgt, logItgt):
    """RMSE of sim-vs-target log10|I| aligned by |V| within each half-sweep."""
    diffs = []
    for sidx, tidx in ((_halves(Vsim)[0], _halves(Vtgt)[0]),
                       (_halves(Vsim)[1], _halves(Vtgt)[1])):
        xs = np.abs(Vsim[sidx]); ys = logIsim[sidx]
        xt = np.abs(Vtgt[tidx]); yt = logItgt[tidx]
        o = np.argsort(xs)
        xs, ys = xs[o], ys[o]
        keep = (xt >= xs.min()) & (xt <= xs.max()) & np.isfinite(yt)
        if keep.sum() < 3:
            continue
        ys_at_t = np.interp(xt[keep], xs, ys)
        diffs.append(yt[keep] - ys_at_t)
    if not diffs:
        return np.nan
    d = np.concatenate(diffs)
    return float(np.sqrt(np.nanmean(d**2)))


_CYCLE_CACHE = {}


def _collect_condition(cond):
    """collect_cycles for one condition, cached (parse each folder once)."""
    if cond not in _CYCLE_CACHE:
        folder = ROOT / "raw_data" / cond
        _CYCLE_CACHE[cond] = (EX.collect_cycles(folder, recursive=False)
                              if folder.is_dir() else [])
    return _CYCLE_CACHE[cond]


def device_cycle_curves(cond, device_id):
    """Per good cycle of one device -> dict[branch] -> (V_signed, log10|I|)."""
    qargs = _QArgs()
    out = []
    for cyc in _collect_condition(cond):
        if cyc.device_id != device_id:
            continue
        if not EX.cycle_quality(cyc, qargs)["is_good"]:
            continue
        branch_curves = {}
        for b in cyc.blocks:
            br = EX.infer_branch(b.title, b.voltage)
            if br not in ("SET", "RESET"):
                continue
            v = np.asarray(b.voltage, float)
            i = np.asarray(b.current, float)
            ok = np.isfinite(v) & np.isfinite(i)
            if ok.sum() < 5:
                continue
            logI = np.log10(np.abs(i[ok]) + I_FLOOR)
            branch_curves[br] = (v[ok], logI)
        if branch_curves:
            out.append((cyc.cycle_number, branch_curves))
    return out


# ---------------------------------------------------------------------------
# 4. Unseen-device validation
# ---------------------------------------------------------------------------
def unseen_device_validation(conds, splits, heldout_csv):
    same = None
    if heldout_csv.exists():
        same = pd.read_csv(heldout_csv)
    rows, per_cycle_store = [], {}
    for c in conds:
        sim = load_medoid_sim(c)
        if sim is None:
            print(f"  [{c}] no archived medoid simulation; skipped")
            continue
        test_devs = splits[(splits.condition == c) &
                           (splits.split == "test")].device_id.tolist()
        fit_dev = fitted_device(c)
        per_cycle_store[c] = {"SET": [], "RESET": []}
        n_dev_used = {"SET": set(), "RESET": set()}
        for dev in test_devs:
            if dev == fit_dev:           # acceptance guard (should never happen)
                continue
            for _cyc, curves in device_cycle_curves(c, dev):
                for br in ("SET", "RESET"):
                    if br not in sim or br not in curves:
                        continue
                    Vsim, logIsim = sim[br]
                    Vt, logIt = curves[br]
                    rmse = _interp_sim_to_target(Vsim, logIsim, Vt, logIt)
                    if np.isfinite(rmse):
                        per_cycle_store[c][br].append(rmse)
                        n_dev_used[br].add(dev)
        for br in ("SET", "RESET"):
            arr = np.array(per_cycle_store[c][br], float)
            sd_med = np.nan
            if same is not None:
                s = same[(same.condition == c) & (same.branch == br)]
                if len(s):
                    sd_med = float(s.rmse_heldout_median.iloc[0])
            rows.append(dict(
                condition=c, branch=br,
                n_test_devices=len(n_dev_used[br]),
                n_unseen_cycles=int(arr.size),
                unseen_rmse_median=round(float(np.median(arr)), 4) if arr.size else np.nan,
                unseen_rmse_p25=round(float(np.percentile(arr, 25)), 4) if arr.size else np.nan,
                unseen_rmse_p75=round(float(np.percentile(arr, 75)), 4) if arr.size else np.nan,
                same_device_heldout_median=sd_med,
                unseen_minus_samedevice=(round(float(np.median(arr)) - sd_med, 4)
                                         if arr.size and np.isfinite(sd_med) else np.nan),
            ))
        nS = len(per_cycle_store[c]["SET"]); nR = len(per_cycle_store[c]["RESET"])
        print(f"  [{c}] unseen-device cycles: SET={nS} RESET={nR} "
              f"from {len(test_devs)} test devices")
    return pd.DataFrame(rows), per_cycle_store


# ---------------------------------------------------------------------------
# Acceptance checks
# ---------------------------------------------------------------------------
def acceptance_checks(splits, conds):
    checks = []
    # (1) no device in more than one split (per condition device ids are unique
    #     rows already, but guard against accidental duplication)
    dup = splits.groupby(["condition", "device_id"]).size()
    checks.append(dict(check="no_device_in_multiple_splits",
                       passed=bool((dup <= 1).all()),
                       detail=f"max rows per device = {int(dup.max()) if len(dup) else 0}"))
    # (2) fitted device never in val/test
    leak = splits[(splits.is_fitted_device == 1) & (splits.split != "train")]
    checks.append(dict(check="fitted_device_in_train_only",
                       passed=bool(len(leak) == 0),
                       detail=f"{len(leak)} fitted-device rows outside train"))
    # (3) every condition has >=1 test device distinct from the fitted device
    ok = True
    detail = []
    for c in conds:
        t = splits[(splits.condition == c) & (splits.split == "test")]
        fit_dev = fitted_device(c)
        n = int((t.device_id != fit_dev).sum())
        detail.append(f"{c}:{n}")
        ok = ok and n >= 1
    checks.append(dict(check="each_condition_has_unseen_test_devices",
                       passed=bool(ok), detail=" ".join(detail)))
    return pd.DataFrame(checks)


def plot_unseen(val_df, per_cycle_store, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4))
    for ax, br in zip(axes, ("SET", "RESET")):
        labs = [c for c in CONDS if c in per_cycle_store and
                per_cycle_store[c][br]]
        data = [np.array(per_cycle_store[c][br]) for c in labs]
        if data:
            bp = ax.boxplot(data, positions=range(len(data)), widths=0.6,
                            showfliers=False, patch_artist=True)
            for box in bp["boxes"]:
                box.set(facecolor="#ffe0b3", alpha=0.9, linewidth=0.7)
            for med in bp["medians"]:
                med.set(color="#b35900", linewidth=1.1)
        sub = val_df[val_df.branch == br].set_index("condition")
        sd = [sub.loc[c].same_device_heldout_median if c in sub.index else np.nan
              for c in labs]
        ax.scatter(range(len(labs)), sd, marker="*", color="#1f77b4", s=55,
                   zorder=4, label="same-device held-out median")
        ax.set_xticks(range(len(labs)))
        ax.set_xticklabels(labs, rotation=45, fontsize=6.5)
        ax.set_ylabel(r"unseen-device RMSE of $\log_{10}|I|$ (decades)")
        ax.set_title(f"{br} branch")
        ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Unseen-DEVICE validation: medoid-fitted model scored on "
                 "held-out devices' cycles", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    for ext in ("pdf", "png"):
        fig.savefig(str(path) + f".{ext}")
    plt.close(fig)
    print(f"  wrote {path}.pdf (+png)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("conditions", nargs="*", default=None)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--test-frac", type=float, default=0.2)
    args = ap.parse_args()
    conds = args.conditions or CONDS
    OUT.mkdir(parents=True, exist_ok=True)

    print("[1] Building population index from raw_data/ ...")
    cyc_df, dev_df = build_population_index(conds)
    if cyc_df.empty:
        raise SystemExit("No cycles found in raw_data/; nothing to validate.")
    cyc_df.to_csv(OUT / "population_index.csv", index=False)
    dev_df.to_csv(OUT / "population_devices.csv", index=False)
    tot_dev = dev_df.device_id.nunique() if "device_id" in dev_df else 0
    tot_good = int(dev_df.good_cycles.sum())
    print(f"  population: {len(dev_df)} device-conditions, {tot_good} good cycles")

    print("[2] Deterministic device-level splits (no leakage) ...")
    splits = make_device_splits(dev_df, conds, args.seed, args.val_frac,
                                args.test_frac)
    splits.to_csv(OUT / "device_splits.csv", index=False)

    print("[3/4] Unseen-device validation ...")
    heldout_csv = ROOT / "results" / "paper_alt" / "heldout_validation.csv"
    val_df, per_cycle_store = unseen_device_validation(conds, splits, heldout_csv)
    val_df.to_csv(OUT / "unseen_device_validation.csv", index=False)
    if not val_df.empty:
        plot_unseen(val_df, per_cycle_store, OUT / "unseen_device_validation")

    print("[5] Acceptance checks ...")
    checks = acceptance_checks(splits, conds)
    # aggregate summary
    agg = {}
    for br in ("SET", "RESET"):
        s = val_df[val_df.branch == br].dropna(subset=["unseen_rmse_median"])
        agg[f"unseen_{br}_mean_median"] = round(float(s.unseen_rmse_median.mean()), 4) if len(s) else np.nan
        agg[f"samedevice_{br}_mean_median"] = round(float(s.same_device_heldout_median.mean()), 4) if len(s) else np.nan
        agg[f"gap_{br}_mean"] = round(float(s.unseen_minus_samedevice.mean()), 4) if len(s) else np.nan
        agg[f"unseen_{br}_total_cycles"] = int(s.n_unseen_cycles.sum()) if len(s) else 0
    summ = pd.DataFrame([dict(metric=k, value=v) for k, v in agg.items()])
    summ = pd.concat([summ, checks.rename(columns={"check": "metric",
                                                    "passed": "value"})[["metric", "value", "detail"]]],
                     ignore_index=True)
    summ.to_csv(OUT / "population_validation_summary.csv", index=False)
    print(checks.to_string(index=False))
    print("\n  AGGREGATE (for manuscript):")
    for br in ("SET", "RESET"):
        print(f"   {br}: unseen-device mean median {agg[f'unseen_{br}_mean_median']} "
              f"vs same-device {agg[f'samedevice_{br}_mean_median']} "
              f"(gap {agg[f'gap_{br}_mean']}), "
              f"{agg[f'unseen_{br}_total_cycles']} unseen cycles")
    print(f"\nWrote results/population/ ({len(splits)} device rows).")


if __name__ == "__main__":
    main()
