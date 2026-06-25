#!/usr/bin/env python3
"""Build the single-column DRC/IEDM-style summary as a .docx.

Pages 1-2: continuous writing (no sections). Remaining pages: all figures and
3 tables from the full paper, each with a caption. Figures are embedded from the
existing PNG renders in ../results and ../step02_S1.
"""
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(os.path.dirname(__file__), "main_abstract.docx")

def P(im):
    return os.path.join(ROOT, im)

doc = Document()

sec = doc.sections[0]
sec.top_margin = Inches(0.8)
sec.bottom_margin = Inches(0.8)
sec.left_margin = Inches(0.8)
sec.right_margin = Inches(0.8)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(10)
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.0

def body(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(text)
    return p

# ===================== TITLE BLOCK =====================
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.paragraph_format.space_after = Pt(2)
rt = t.add_run("Device-Guided Calibration of the Stanford RRAM Model: Generalization, Identifiability, and Deposition Trends in Sputter-Deposited TaOₓ Devices")
rt.bold = True
rt.font.size = Pt(14)

a = doc.add_paragraph()
a.alignment = WD_ALIGN_PARAGRAPH.CENTER
a.paragraph_format.space_after = Pt(1)
a.add_run("Md Tawsif Rahman Chowdhury, Alireza Moazzeni, and Gozde Tutuncuoglu").font.size = Pt(10.5)

aff = doc.add_paragraph()
aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
aff.paragraph_format.space_after = Pt(8)
raf = aff.add_run("Department of Electrical and Computer Engineering, Wayne State University, Detroit, MI 48202 USA")
raf.italic = True
raf.font.size = Pt(9)

# ===================== BODY (pages 1-2) =====================
paras = [
"Resistive RAM (RRAM) is a leading candidate for embedded nonvolatile memory and "
"in-memory computing, and almost every circuit- or process-level study of it eventually "
"has to turn a measured current–voltage (I–V) switching loop into a set of compact-model "
"parameters. The Stanford–PKU model is the usual target: it describes bipolar filamentary "
"switching with a single “gap” state variable, a sinh-shaped tunneling current, and a "
"thermally accelerated gap growth/rupture law. The standard way to report such a calibration "
"is to overlay one simulated curve on one measured loop and show that the two match. That "
"picture is necessary but not sufficient. A good overlay does not establish two things a "
"device or process engineer actually needs: (i) that the extracted parameters describe the "
"whole device — every measured cycle — rather than only the single loop that was fitted, and "
"(ii) that each individual number is genuinely pinned down by the data rather than being one "
"of many values that fit equally well. We call the first question generalization and the "
"second identifiability. Both are simple, but they are rarely reported alongside RRAM "
"parameter sets.",

"We built an automated, device-guided extraction flow for the Stanford model and applied it "
"uniformly to twelve sputter-deposited TaOₓ conditions spanning 20–35% oxygen in the sputter "
"ambient and 75–250 W RF power (a face-centered factorial design with four repeated center "
"points; Table I). The flow makes four contributions, which are the novel content of this "
"work. First, it reads the device physics before fitting: every part of the measured loop is "
"classified by conduction mechanism, and that map both guides the fit and flags the regions "
"the Stanford current law physically cannot reproduce. Second, it tests generalization "
"directly, by scoring a fit made on one representative cycle against every other measured "
"cycle of the same device. Third, it audits identifiability, reporting which parameters are "
"repeatable enough to carry physical meaning. Fourth, it uses only those trustworthy "
"parameters to extract deposition trends, and in doing so exposes a device-physics limit of "
"the Stanford model for TaOₓ.",

"The devices are 4-µm cross-point TaOₓ cells with the standard asymmetric Ta-oxide bilayer "
"stack, measured under DC bipolar switching on a Keysight B1500. Each device contributes tens "
"of measured cycles; an automated quality screen removes shorted, open, incomplete, or "
"noise-floor sweeps before any fitting (for the representative S1 device, all 40 cycles pass, "
"mean quality 8.9/10). For each condition the flow then picks one representative cycle "
"automatically — the medoid, the single measured loop closest to the typical (median) "
"behavior of all the cycles — instead of letting a person choose a good-looking trace by eye. "
"Using a real measured loop, rather than an averaged synthetic curve, preserves the true "
"hysteresis order, the switching kinks, and the compliance-limited plateau that the model "
"must reproduce. The remaining cycles are set aside for the generalization and repeatability "
"tests below.",

"Before any fitting, each resistance-state segment of the representative loop is classified as "
"ohmic, Poole–Frenkel, Schottky, or Fowler–Nordheim conduction (Fig. 1). The four candidates "
"are fit to the same common log-current response so their information criteria are directly "
"comparable, a window is flagged ‘ambiguous’ when the best two candidates are statistically "
"close, and the implied dielectric constant is used only to reject physically nonphysical "
"interface fits — never to confirm a mechanism — so the labels are a model-adequacy diagnostic "
"rather than proof of a microscopic mechanism. The model itself — "
"the Stanford Verilog-A description — is then simulated in HSPICE, and its parameters are "
"tuned to match the measured loop on a logarithmic current scale (the sweep spans several "
"decades of current, so a log scale gives all of them fair weight). The search uses Bayesian "
"optimization, a guided search that learns from each trial which parameter values to try next, "
"so it reaches a good fit in a few hundred simulations instead of scanning a grid, followed by "
"a short local polish. Importantly, the parts of the curve the Stanford law cannot represent "
"(the Schottky/FN regions) are down-weighted during fitting so they cannot distort the "
"parameters the model can represent, but they are restored to full weight when we report the "
"final error so the mismatch stays visible.",

"Across all twelve conditions the fits reproduce the measured butterfly curves with a typical "
"error of 0.530 current decades for SET and 0.761 for RESET (Table II). (“Error” here is the "
"root-mean-square gap between simulated and measured current along the sweep; one decade is a "
"factor of ten, so 0.5 decade means the simulated current is typically within about a factor "
"of three of the measurement.) The fits capture the hysteresis order, both switching "
"transitions, the compliance plateau, and the LRS return branch. The leftover error is not "
"random scatter: a simple residual test — the Durbin–Watson statistic, which detects whether "
"the error drifts smoothly along the sweep rather than jittering point to point — shows it is "
"systematic. That is the signature of a missing physical term, not of optimizer failure, and "
"the regime map points to the likely term: the high-resistance state (HRS) is barrier-limited "
"(Schottky-like where a credible window is present), a mechanism the Stanford bulk current law "
"does not contain, although room-temperature DC data cannot cleanly separate it from a "
"near-ohmic trend (Fig. 2). A controlled ablation (Table III) makes the same "
"point from the optimization side: removing the search nearly triples the RESET error, yet the "
"three optimized variants land within a few hundredths of a decade of each other, so a low "
"overlay error by itself cannot single out the right physics.",

"The most important check is whether a fit made on one cycle describes data it never saw. "
"We first score the fitted curve against every other measured cycle of the same device: "
"averaged over conditions this held-out error is 0.542 (SET) and 0.800 (RESET) decades, "
"versus the in-sample 0.530 and 0.761 — a small average gap (Fig. 3), though the per-condition "
"agreement varies and S1 RESET is a flagged outlier, so we report the distribution rather than "
"claiming the two are indistinguishable. The fitted S1 curve stays within the measured "
"cycle-to-cycle envelope along almost the entire sweep, departing only at the SET transition "
"and the HRS approach (Fig. 4). The stronger test is split-safe population validation: "
"over the full population (545 device records, ~10,900 cycles) we form leakage-free "
"device-level splits and score the medoid-fitted model against cycles of entirely unseen "
"devices. The unseen-device median error (0.580 SET, 0.861 RESET) exceeds the same-device "
"value by only ~0.04–0.06 decade, genuine population-scale evidence that the calibration is a "
"property of the device population, not an artifact of which loop we fitted (Fig. 11).",

"A fit that generalizes can still hide parameters that the data do not actually determine. To "
"find them we resample the measurement: we repeatedly draw random subsets of the measured "
"cycles, refit each time, and watch how much each parameter moves — a procedure called the "
"bootstrap. We report each parameter as the bootstrap median with a percentile interval, so "
"the quoted value always sits inside its own error bar, and we flag any parameter whose error "
"bar is set by the prior search box rather than by the data. The branch voltage scales are "
"the most repeatable coordinates (CV ≈ 0.28), consistent with the curvature of the switching "
"branch directly fixing them. In contrast, series resistance is the extreme case of a "
"box-limited parameter: every single bootstrap refit rails against the edge of the search "
"box (100% pinned), so its one-to-two-decade interval reflects the box, not the device "
"(Fig. 5). A purely local sensitivity calculation (a Fisher analysis; Fig. 6) can be "
"misleading here: it makes series resistance look well determined at a single fit, yet that "
"same parameter wanders the most under resampling. Decomposing the Fisher information into its "
"natural directions makes the situation precise (Fig. 9): the matrix is rank deficient "
"(numerical rank roughly 8–14 of 16 directions), with a few stiff well-determined directions "
"and many sloppy ones — a textbook ‘sloppy’ model. We report this rank rather than an exact "
"eigenvalue span, because eigenvalues far below the largest are double-precision noise, not "
"measurable information. The honest conclusion is that DC butterfly data constrain one or "
"two effective combinations far better than they constrain a unique split into current "
"prefactor, gap size, activation energy, and kinetic prefactor.",

"This directly tells a process engineer which extracted numbers may be plotted against "
"deposition — and we test the trends formally rather than by eye. Because the deposition "
"design is a face-centered factorial with four repeated center points, we fit a response "
"surface to each admissible parameter and use the repeats as a built-in noise estimate "
"(a lack-of-fit test). Only the SET voltage scale passes: it rises with oxygen and falls "
"with power, both statistically significant, with no significant lack-of-fit (Fig. 7). The "
"RESET voltage scale shows the same oxygen sign but does not reach significance, and series "
"resistance shows no significant trend at all — so, of the whole Stanford parameter table, "
"exactly one column is currently a defensible process response. The four repeated center-point "
"devices also let us separate cycle-to-cycle from device-to-device scatter: for every "
"parameter the cycle-to-cycle spread is the larger of the two (Fig. 10), so the cycle "
"bootstrap captures the dominant uncertainty and the device-to-device differences are mostly "
"cycling, not fabrication. Finally, the regime classifier yields a process-facing observable "
"that is not a fitting knob at all: the effective dielectric constant of the post-RESET "
"Schottky-like window, measured on every cycle where such a window is credible. Its "
"per-condition median lands between about 5 and 23 — physically reasonable — in the ten "
"conditions that show the window, each with a cycle-bootstrap error bar (Fig. 8), supporting "
"barrier-limited HRS conduction where it is observed. Crucially this observable stays "
"meaningful exactly where the compact-model parameters do not, because it is read from the "
"data, not fitted.",
]
for ptext in paras:
    body(ptext)

concl = doc.add_paragraph()
concl.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
concl.paragraph_format.space_after = Pt(4)
concl.add_run("In summary, ").bold = True
concl.add_run(
"for sputter-deposited TaOₓ the Stanford compact model can be calibrated to within about half "
"a current decade, and — more importantly — that calibration generalizes not only across the "
"cycles of the fitted device but to entirely unseen devices in a split-safe population test. "
"But the fitted parameter table must not be read uniformly: the parameterization is rank "
"deficient (profoundly sloppy), and of all its columns only the SET voltage scale passes a "
"formal deposition-trend test, while series resistance (fully bound-pinned), velocity "
"prefactors, activation energies, and gap geometry behave as numerical fitting knobs rather "
"than process outputs from DC sweeps alone. The same analysis points to the model's physical "
"limitation — the post-RESET HRS is barrier-limited (Schottky-like where credible), a "
"mechanism the Stanford bulk current law lacks, though room-temperature DC data cannot confirm "
"a single microscopic mechanism. The practical recommendation is therefore to report an RRAM "
"compact-model calibration as four items together — fit quality, population-level "
"generalization, parameter identifiability, and conduction-mechanism validity — rather than a "
"single overlay plot, so a reader can tell which extracted numbers are measurements of the "
"device and which are merely well-fitting knobs.")

# ===================== TABLES + FIGURES =====================
doc.add_page_break()

hh = doc.add_paragraph()
hh.paragraph_format.space_after = Pt(6)
rhh = hh.add_run("Tables and Figures")
rhh.bold = True
rhh.font.size = Pt(11)

def table_caption(label, text):
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_before = Pt(2)
    c.paragraph_format.space_after = Pt(2)
    rl = c.add_run(label + " ")
    rl.bold = True; rl.italic = True; rl.font.size = Pt(8.5)
    rc = c.add_run(text)
    rc.italic = True; rc.font.size = Pt(8.5)

def make_table(headers, rows, mean_row=None, widths=None):
    tb = doc.add_table(rows=1, cols=len(headers))
    tb.style = "Table Grid"
    tb.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hdr = tb.rows[0].cells
    for i, h in enumerate(headers):
        p = hdr[i].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h); r.bold = True; r.font.size = Pt(8)
    for row in rows:
        cells = tb.add_row().cells
        for i, v in enumerate(row):
            p = cells[i].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(v)); r.font.size = Pt(8)
    if mean_row:
        cells = tb.add_row().cells
        for i, v in enumerate(mean_row):
            p = cells[i].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(v)); r.bold = True; r.font.size = Pt(8)
    return tb

# ---- Table I: DOE ----
table_caption("TABLE I.", "Deposition design of experiments. The center point "
              "(27.5%, 162.5 W) is replicated four times (S9–S12).")
make_table(["Sample", "O₂ (%)", "Power (W)"],
           [["S1","20","75"],["S2","20","250"],["S3","35","75"],["S4","35","250"],
            ["S5","20","162.5"],["S6","35","162.5"],["S7","27.5","75"],
            ["S8","27.5","250"],["S9–S12","27.5","162.5"]])

# ---- Table II: fit quality ----
table_caption("TABLE II.", "Validation fit quality per condition: unweighted RMSE of "
              "log₁₀|I| (decades) and Durbin–Watson (DW) statistics.")
make_table(["Cond.","RMSE(SET)","RMSE(RESET)","DW(SET)","DW(RESET)"],
           [["S1","0.500","0.689","0.86","0.85"],["S2","0.772","1.016","0.46","0.56"],
            ["S3","0.566","0.659","0.72","0.98"],["S4","0.514","0.730","0.82","0.90"],
            ["S5","0.508","0.805","0.85","0.74"],["S6","0.468","0.650","0.94","0.93"],
            ["S7","0.477","0.726","1.04","0.91"],["S8","0.495","1.001","1.03","0.54"],
            ["S9","0.510","0.700","0.92","1.04"],["S10","0.508","0.718","1.00","0.98"],
            ["S11","0.494","0.753","0.92","0.88"],["S12","0.548","0.681","0.96","1.01"]],
           mean_row=["Mean","0.530","0.761","—","—"])

# ---- Table III: ablation ----
table_caption("TABLE III.", "Ablation over all 12 conditions: unweighted validation RMSE "
              "(decades), mean ± standard deviation across conditions.")
make_table(["Variant","RMSE(SET)","RMSE(RESET)"],
           [["Regime-conditioned + weighting","0.530 ± 0.081","0.761 ± 0.123"],
            ["Physics priors + BO","0.546 ± 0.077","0.756 ± 0.124"],
            ["Uninformative priors + BO","0.537 ± 0.076","0.755 ± 0.126"],
            ["Physics priors, no BO","0.571 ± 0.115","1.528 ± 0.434"]])

doc.add_paragraph().paragraph_format.space_after = Pt(2)

# ---- Figures (2-column grid) ----
figs = [
 ("step02_S1/S1_B6-01-4um-12_regime_overview.png", 2.9,
  ("Fig. 1.", " Conduction-regime classification (common-response fit) of the four "
   "resistance-state segments of a representative S1 cycle. The two low-resistance (LRS) "
   "segments are ohmic (R²≥0.98); the two high-resistance (HRS) segments are barrier-limited, "
   "with a Schottky-like window where the implied permittivity is admissible. This map tells "
   "the fitter where the Stanford bulk current law can and cannot follow the data.")),
 ("results/variability/mechanism_map.png", 2.9,
  ("Fig. 2.", " Dominant conduction mechanism and its cycle-to-cycle stability for every "
   "resistance-state segment and all twelve conditions. The post-SET LRS is consistently ohmic; "
   "the high-resistance segments are barrier-limited but not cleanly separable, with a robust "
   "Schottky-like signature at higher voltage and many windows flagged ambiguous.")),
 ("results/paper_alt/heldout_rmse.png", 2.9,
  ("Fig. 3.", " Out-of-sample test. Box plots show the error (in current decades) when the model "
   "fitted to one representative cycle is scored against every other measured cycle of the same "
   "device; stars mark the in-sample value. The two are nearly equal — the fit describes the "
   "whole device, not just the loop it was trained on.")),
 ("results/paper_alt/heldout_overlay_S1.png", 2.9,
  ("Fig. 4.", " S1 fitted curve (red) against the measured cycle-to-cycle envelope (min–max and "
   "interquartile bands, with the measured median) along the sweep; the secondary axis marks "
   "voltage. The fit stays inside the measured spread except at the SET transition and the HRS "
   "approach.")),
 ("results/variability/parameter_cv.png", 2.9,
  ("Fig. 5.", " Repeatability of each fitted parameter across 200 bootstrap refits per condition "
   "(color = log of the coefficient of variation; bluer = more repeatable). Branch voltage "
   "scales are repeatable; series resistance and the velocity prefactors are not. This is our "
   "primary identifiability evidence.")),
 ("results/publication/identifiability_heatmap.png", 2.9,
  ("Fig. 6.", " Fisher relative (log-coordinate) uncertainty for the 16 active "
   "parameters across the twelve conditions, shown only as a cross-check. The Fisher matrix is "
   "rank deficient (numerical rank ≈8–14/16), so individual parameters are not certified from "
   "this map alone; conclusions are drawn only where it agrees with Fig. 5.")),
 ("results/paper_alt/deposition_trends.png", 2.6,
  ("Fig. 7.", " Process trends for the repeatable parameters (points: bootstrap median; error "
   "bars: cycle-bootstrap 95% interval). A formal response-surface test (center points as "
   "pure error) finds only the SET voltage scale significant in oxygen and power; series "
   "resistance (top) spans up to two decades and is not a process output.")),
 ("results/paper_alt/hrs_schottky_trend.png", 2.9,
  ("Fig. 8.", " Effective dielectric constant of the post-RESET Schottky-like window, measured "
   "on every cycle where the window is credible, shown as the per-condition median with a "
   "cycle-bootstrap 95% interval. The shaded band is the physically admissible range; the ten "
   "conditions with such a window fall inside it, supporting barrier-limited HRS conduction "
   "where it is observed.")),
 ("results/robustness/sloppy_spectrum.png", 2.9,
  ("Fig. 9.", " Sloppiness of the Stanford parameterization. Left: normalized Fisher eigenvalue "
   "spectra for all twelve conditions; the matrix is rank deficient (a few stiff directions, "
   "many sloppy ones below the numerical floor). Right: how much each parameter participates in "
   "the single best-determined direction — a coupled current-scale/gap combination, not any one "
   "microscopic parameter.")),
 ("results/robustness/variance_components.png", 2.9,
  ("Fig. 10.", " Cycle-to-cycle vs. device-to-device spread from the four repeated center-point "
   "devices (S9–S12). For every parameter the cycle-to-cycle spread dominates, so the scatter "
   "among nominally identical devices is mostly cycling, not fabrication.")),
 ("results/population/unseen_device_validation.png", 2.9,
  ("Fig. 11.", " Split-safe unseen-device validation. Box plots: per-cycle error when the "
   "medoid-fitted model is scored against cycles of held-out devices never used for selection "
   "or fitting (leakage-free device-level splits over 545 device records); stars mark the "
   "same-device held-out median. The model generalizes to unseen devices with only a modest "
   "median increase.")),
]

nrows = (len(figs) + 1) // 2
table = doc.add_table(rows=nrows, cols=2)
table.autofit = True
cells = [table.cell(r, c) for r in range(nrows) for c in range(2)]
for cell, (fname, w, (lbl, captxt)) in zip(cells, figs):
    cp = cell.paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_after = Pt(2)
    cp.add_run().add_picture(P(fname), width=Inches(w))
    cap = cell.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.paragraph_format.space_after = Pt(8)
    rl = cap.add_run(lbl); rl.bold = True; rl.italic = True; rl.font.size = Pt(8)
    rc = cap.add_run(captxt); rc.italic = True; rc.font.size = Pt(8)

doc.save(OUT)
print("saved", OUT)
