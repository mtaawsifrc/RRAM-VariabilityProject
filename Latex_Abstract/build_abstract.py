#!/usr/bin/env python3
"""Build the 3-page single-column DRC/IEDM-style summary as a .docx.

Pages 1-2: continuous writing (no sections). Page 3: figures with captions.
Figures are embedded from the existing PNG renders in ../results and ../step02_S1.
"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(os.path.dirname(__file__), "main_abstract.docx")

def P(im):  # absolute image path
    return os.path.join(ROOT, im)

doc = Document()

# ---- page geometry ----
sec = doc.sections[0]
sec.top_margin = Inches(0.85)
sec.bottom_margin = Inches(0.85)
sec.left_margin = Inches(0.85)
sec.right_margin = Inches(0.85)

# ---- base style ----
normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(10)
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.0

def body(text, justify=True, space_after=4, first_indent=0.0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if first_indent:
        p.paragraph_format.first_line_indent = Inches(first_indent)
    r = p.add_run(text)
    return p

# ===================== TITLE BLOCK =====================
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.paragraph_format.space_after = Pt(2)
rt = t.add_run("Device-Guided Calibration of the Stanford RRAM Compact Model for "
               "Sputter-Deposited TaOₓ Devices:\n"
               "How Much of a Fitted Parameter Set Can We Trust?")
rt.bold = True
rt.font.size = Pt(14)

a = doc.add_paragraph()
a.alignment = WD_ALIGN_PARAGRAPH.CENTER
a.paragraph_format.space_after = Pt(1)
ra = a.add_run("Md Taawsif Rahman Chowdhury, Atefeh Moazzeni, and Gozde Tutuncuoglu")
ra.font.size = Pt(10.5)

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
"points). The flow makes four contributions, which are the novel content of this work. "
"First, it reads the device physics before fitting: every part of the measured loop is "
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
"ohmic, Poole–Frenkel, Schottky, or Fowler–Nordheim conduction (Fig. 1). Because some of "
"these signatures look almost identical over a short voltage span, we add a physical sanity "
"check: the measured slope is converted into an effective dielectric constant, and a label is "
"accepted only if that value is physically reasonable for the 7-nm oxide. The model itself — "
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
"error of 0.530 current decades for SET and 0.761 for RESET. (“Error” here is the "
"root-mean-square gap between simulated and measured current along the sweep; one decade is a "
"factor of ten, so 0.5 decade means the simulated current is typically within about a factor "
"of three of the measurement.) The fits capture the hysteresis order, both switching "
"transitions, the compliance plateau, and the LRS return branch. The leftover error is not "
"random scatter: a simple residual test — the Durbin–Watson statistic, which detects whether "
"the error drifts smoothly along the sweep rather than jittering point to point — shows it is "
"systematic. That is the signature of a missing physical term, not of optimizer failure, and "
"the regime map tells us which term: the high-resistance state (HRS) is interface-limited "
"Schottky conduction in 92.5–100% of cycles for every condition (Fig. 2), a mechanism the "
"Stanford bulk current law does not contain.",

"The most important check is whether a fit made on one cycle describes the cycles it never "
"saw. We score the fitted curve, point by point, against every measured cycle of the device. "
"Averaged over conditions, this held-out error is 0.542 (SET) and 0.800 (RESET) decades, "
"versus the in-sample 0.530 and 0.761 — a gap of only about 0.01–0.04 decade (Fig. 3). For "
"every condition the fitted-cycle value sits inside the spread of the held-out cycles. In "
"other words, the representative cycle is simply the most central member of a population the "
"model reproduces uniformly: the calibration is a property of the device, not an artifact of "
"which loop we happened to fit.",

"A fit that generalizes can still hide parameters that the data do not actually determine. To "
"find them we resample the measurement: we repeatedly draw random subsets of the measured "
"cycles, refit each time, and watch how much each parameter moves — a procedure called the "
"bootstrap. A parameter with a small spread relative to its size (a small coefficient of "
"variation, CV) is repeatably determined; a large CV means many values fit the data about "
"equally well. The branch voltage scales are the most repeatable coordinates (CV ≈ 0.28), "
"consistent with the curvature of the switching branch directly fixing them. In contrast, "
"series resistance and the velocity prefactors are unstable (CV > 1), and the current scale "
"and activation energies vary substantially (Fig. 4). A purely local sensitivity calculation "
"(a Fisher analysis, which only asks how sharply the fit error changes if a parameter is "
"nudged at the best fit) can be misleading here: it can make series resistance look well "
"determined at a single fit, yet that same parameter wanders the most under resampling. We "
"therefore trust the repeatability test and keep the local calculation only as a cross-check. "
"The honest conclusion is that DC butterfly data constrain effective branch scales and "
"switching-field combinations far better than they constrain a unique split into current "
"prefactor, gap size, activation energy, and kinetic prefactor.",

"This directly tells a process engineer which extracted numbers may be plotted against "
"deposition. Only the repeatable branch voltage scales are admissible, and they do vary "
"systematically — for example, the RESET voltage scale trends lower at the high-oxygen, "
"low-power corners than at the oxygen-poor corners (Fig. 5). Series resistance, although it "
"often looks locally well determined, carries bootstrap intervals spanning one to two orders "
"of magnitude; its apparent process variation cannot be separated from cycle-to-cycle noise "
"and must not be read as a deposition trend. Finally, the regime classifier yields a "
"process-facing physical observable that is not a fitting knob at all: the effective "
"dielectric constant of the post-RESET Schottky barrier. It lands between about 4.7 and 32 — "
"physically reasonable — for all twelve conditions (Fig. 6), confirming that the HRS is "
"interface-limited Schottky emission across the entire process window, and that this "
"mechanism, absent from the Stanford bulk law, sets the floor on achievable RESET accuracy.",
]
for ptext in paras:
    body(ptext)

# bold "In summary" conclusion paragraph
concl = doc.add_paragraph()
concl.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
concl.paragraph_format.space_after = Pt(4)
r1 = concl.add_run("In summary, ")
r1.bold = True
concl.add_run(
"for sputter-deposited TaOₓ the Stanford compact model can be calibrated to within about half "
"a current decade, and — more importantly — that calibration generalizes from one "
"representative cycle to the full measured-cycle population of the device. But the fitted "
"parameter table must not be read uniformly: only the branch voltage scales and "
"switching-field combinations are repeatable enough to compare across deposition conditions, "
"while series resistance, velocity prefactors, activation energies, and gap geometry behave as "
"numerical fitting knobs rather than process outputs from DC sweeps alone. The same analysis "
"pinpoints the model's physical limitation — the post-RESET HRS is Schottky-limited in nearly "
"every cycle of every condition, a mechanism the Stanford bulk current law lacks. The "
"practical recommendation is therefore to report an RRAM compact-model calibration as four "
"items together — fit quality, cycle-to-cycle generalization, parameter identifiability, and "
"conduction-mechanism validity — rather than a single overlay plot, so a reader can tell which "
"extracted numbers are measurements of the device and which are merely well-fitting knobs.")

# ===================== FIGURES (page 3) =====================
doc.add_page_break()

fh = doc.add_paragraph()
fh.paragraph_format.space_after = Pt(6)
rfh = fh.add_run("Figures")
rfh.bold = True
rfh.font.size = Pt(11)

# (filename, display_width_in, caption_runs[(bold,text)])
figs = [
 ("step02_S1/S1_B6-01-4um-12_regime_overview.png", 3.0,
  ("Fig. 1.", " Conduction-regime classification of the four resistance-state segments of a "
   "representative S1 cycle. The two low-resistance (LRS) segments are ohmic (R²≥0.98); the "
   "two high-resistance (HRS) segments are Schottky-limited, with a Fowler–Nordheim window near "
   "the SET transition. This map tells the fitter where the Stanford bulk current law can and "
   "cannot follow the data.")),
 ("results/variability/mechanism_map.png", 3.0,
  ("Fig. 2.", " Dominant conduction mechanism and its cycle-to-cycle stability for every "
   "resistance-state segment and all twelve deposition conditions. The post-SET LRS is "
   "consistently ohmic; the post-RESET HRS is Schottky-dominant in 92.5–100% of cycles "
   "everywhere.")),
 ("results/paper_alt/heldout_rmse.png", 3.0,
  ("Fig. 3.", " Out-of-sample test. Box plots show the error (in current decades) when the model "
   "fitted to one representative cycle is scored against every other measured cycle of the same "
   "device; stars mark the in-sample value. The two are nearly equal, so the fit describes the "
   "whole device, not just the loop it was trained on.")),
 ("results/variability/parameter_cv.png", 3.0,
  ("Fig. 4.", " Repeatability of each fitted parameter across 200 bootstrap refits per condition "
   "(color = log of the coefficient of variation; bluer = more repeatable). Branch voltage "
   "scales are repeatable; series resistance and the velocity prefactors are not. This is our "
   "primary identifiability evidence.")),
 ("results/paper_alt/deposition_trends.png", 2.7,
  ("Fig. 5.", " Process trends for the repeatable parameters (error bars: cycle-bootstrap 95% "
   "interval). Branch voltage scales (middle, bottom) move systematically with deposition; "
   "series resistance (top) spans up to two decades and cannot serve as a process output, even "
   "though a single fit appears to prefer a value.")),
 ("results/paper_alt/hrs_schottky_trend.png", 3.0,
  ("Fig. 6.", " Effective dielectric constant inferred from the post-RESET Schottky window vs. "
   "oxygen (left) and power (right). The shaded band is the physically admissible range; all "
   "twelve conditions fall inside it, confirming interface-limited HRS conduction across the "
   "entire process window.")),
]

# 2-column table layout for compactness
table = doc.add_table(rows=3, cols=2)
table.autofit = True
cells = [table.cell(r, c) for r in range(3) for c in range(2)]
for cell, (fname, w, (lbl, captxt)) in zip(cells, figs):
    cp = cell.paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_after = Pt(2)
    run = cp.add_run()
    run.add_picture(P(fname), width=Inches(w))
    cap = cell.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.paragraph_format.space_after = Pt(8)
    rl = cap.add_run(lbl)
    rl.bold = True
    rl.italic = True
    rl.font.size = Pt(8)
    rc = cap.add_run(captxt)
    rc.italic = True
    rc.font.size = Pt(8)

doc.save(OUT)
print("saved", OUT)
