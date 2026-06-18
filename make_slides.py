#!/usr/bin/env python3
"""Build an advisor-facing slide deck from main_alt_codex.tex.

Generates results/Stanford_RRAM_advisor_slides.pptx using python-pptx,
embedding the existing result figures.
"""
import os
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- palette -------------------------------------------------------------
NAVY   = RGBColor(0x0E, 0x2A, 0x47)
TEAL   = RGBColor(0x12, 0x9A, 0x8E)
GOLD   = RGBColor(0xF2, 0xA9, 0x00)
LIGHT  = RGBColor(0xF4, 0xF7, 0xFA)
GRAY   = RGBColor(0x44, 0x4B, 0x52)
MIDGRAY= RGBColor(0x6B, 0x73, 0x7B)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
RED    = RGBColor(0xC0, 0x39, 0x2B)

SW, SH = Inches(13.333), Inches(7.5)
prs = Presentation()
prs.slide_width  = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

FIG = os.path.dirname(os.path.abspath(__file__))

def slide():
    return prs.slides.add_slide(BLANK)

def rect(s, x, y, w, h, color, line=None):
    sp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sp.fill.solid(); sp.fill.fore_color.rgb = color
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp

def txt(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
        space_after=4, line_spacing=1.0):
    """runs: list of paragraphs; each paragraph is list of (text,size,color,bold,italic)."""
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Pt(2)
    tf.margin_top = tf.margin_bottom = Pt(2)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        for (t, sz, col, bold, ital) in para:
            r = p.add_run(); r.text = t
            r.font.size = Pt(sz); r.font.color.rgb = col
            r.font.bold = bold; r.font.italic = ital
            r.font.name = "Calibri"
    return tb

def header(s, kicker, title):
    rect(s, 0, 0, SW, Inches(1.15), NAVY)
    rect(s, 0, Inches(1.15), SW, Pt(4), TEAL)
    txt(s, Inches(0.55), Inches(0.12), Inches(12.3), Inches(0.35),
        [[(kicker.upper(), 12, GOLD, True, False)]])
    txt(s, Inches(0.55), Inches(0.40), Inches(12.3), Inches(0.7),
        [[(title, 26, WHITE, True, False)]], anchor=MSO_ANCHOR.MIDDLE)

def footer(s, n):
    txt(s, Inches(0.55), Inches(7.08), Inches(10), Inches(0.3),
        [[("Device-Guided Calibration of the Stanford RRAM Model  ·  Chowdhury, Moazzeni, Tutuncuoglu  ·  Wayne State University",
           9, MIDGRAY, False, False)]])
    txt(s, Inches(12.4), Inches(7.08), Inches(0.7), Inches(0.3),
        [[(str(n), 9, MIDGRAY, True, False)]], align=PP_ALIGN.RIGHT)

def add_image(s, path, x, y, w, h, caption=None):
    """Fit image inside box (x,y,w,h) preserving aspect, centered."""
    im = Image.open(path); ar = im.size[0]/im.size[1]
    boxar = w/h
    if ar > boxar:
        iw = w; ih = int(w/ar)
    else:
        ih = h; iw = int(h*ar)
    ix = x + (w-iw)//2; iy = y + (h-ih)//2
    s.shapes.add_picture(path, ix, iy, iw, ih)
    if caption:
        txt(s, x, y+h+Pt(2), w, Inches(0.45),
            [[(caption, 10, MIDGRAY, False, True)]], align=PP_ALIGN.CENTER)

def bullet(s, x, y, w, h, items, size=15, gap=8, lead=TEAL):
    paras = []
    for it in items:
        if isinstance(it, tuple):
            head, rest = it
            paras.append([("▸  ", size, lead, True, False),
                          (head, size, NAVY, True, False),
                          (rest, size, GRAY, False, False)])
        else:
            paras.append([("▸  ", size, lead, True, False),
                          (it, size, GRAY, False, False)])
    txt(s, x, y, w, h, paras, space_after=gap, line_spacing=1.05)

def metric_card(s, x, y, w, h, big, label, sub=None, accent=TEAL):
    rect(s, x, y, w, h, WHITE)
    rect(s, x, y, w, Pt(5), accent)
    txt(s, x, y+Inches(0.18), w, Inches(0.7),
        [[(big, 30, accent, True, False)]], align=PP_ALIGN.CENTER)
    txt(s, x, y+Inches(0.85), w, Inches(0.5),
        [[(label, 12.5, NAVY, True, False)]], align=PP_ALIGN.CENTER)
    if sub:
        txt(s, x, y+h-Inches(0.45), w, Inches(0.4),
            [[(sub, 10, MIDGRAY, False, True)]], align=PP_ALIGN.CENTER)

# table helper
def table(s, x, y, w, headers, rows, colw=None, fs=11, hfs=11.5,
          rowh=Inches(0.32), hrowh=Inches(0.36)):
    ncol = len(headers); nrow = len(rows)+1
    gtbl = s.shapes.add_table(nrow, ncol, x, y, w, hrowh+rowh*len(rows)).table
    if colw:
        total = sum(colw)
        for j, cw in enumerate(colw):
            gtbl.columns[j].width = Emu(int(w * cw/total))
    gtbl.rows[0].height = hrowh
    for i in range(1, nrow):
        gtbl.rows[i].height = rowh
    # header
    for j, htext in enumerate(headers):
        c = gtbl.cell(0, j); c.text = htext
        c.fill.solid(); c.fill.fore_color.rgb = NAVY
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        p.runs[0].font.size = Pt(hfs); p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE; p.runs[0].font.name = "Calibri"
        c.margin_top = c.margin_bottom = Pt(1)
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            c = gtbl.cell(i, j); c.text = str(val)
            c.fill.solid()
            c.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
            p.runs[0].font.size = Pt(fs)
            p.runs[0].font.color.rgb = GRAY
            p.runs[0].font.bold = (j == 0)
            p.runs[0].font.name = "Calibri"
            c.margin_top = c.margin_bottom = Pt(1)
            c.margin_left = Pt(6)
    return gtbl

# =========================================================================
# Slide 1 — Title
# =========================================================================
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, Inches(4.55), SW, Pt(4), TEAL)
rect(s, Inches(0.0), Inches(0.0), Pt(10), SH, GOLD)
txt(s, Inches(0.9), Inches(0.85), Inches(11.5), Inches(0.4),
    [[("IEEE TRANSACTIONS ON NANOTECHNOLOGY  ·  MANUSCRIPT IN PREPARATION", 13, GOLD, True, False)]])
txt(s, Inches(0.9), Inches(1.7), Inches(11.6), Inches(2.4),
    [[("Device-Guided Calibration of the", 34, WHITE, True, False)],
     [("Stanford RRAM Compact Model", 34, WHITE, True, False)],
     [("Generalization, Identifiability, and Deposition Trends in", 19, RGBColor(0xBF,0xD6,0xE6), False, True)],
     [("Sputter-Deposited TaOₓ Devices", 19, RGBColor(0xBF,0xD6,0xE6), False, True)]],
    space_after=6, line_spacing=1.02)
txt(s, Inches(0.9), Inches(4.85), Inches(11.5), Inches(0.8),
    [[("Md Tawsif Rahman Chowdhury", 17, WHITE, True, False),
      ("    ·    Alireza Moazzeni    ·    Gozde Tutuncuoglu", 16, RGBColor(0xCF,0xDC,0xE6), False, False)]])
txt(s, Inches(0.9), Inches(5.5), Inches(11.5), Inches(0.4),
    [[("Department of Electrical & Computer Engineering, Wayne State University", 14, RGBColor(0x9F,0xB6,0xC6), False, False)]])
# tagline strip
rect(s, Inches(0.9), Inches(6.25), Inches(11.5), Inches(0.7), RGBColor(0x14,0x3A,0x5E))
txt(s, Inches(1.1), Inches(6.25), Inches(11.1), Inches(0.7),
    [[("Fit quality is not enough — we also report ", 14.5, WHITE, False, False),
      ("cycle-to-cycle generalization", 14.5, GOLD, True, False),
      (" and ", 14.5, WHITE, False, False),
      ("parameter identifiability", 14.5, GOLD, True, False),
      (" with every extraction.", 14.5, WHITE, False, False)]],
    anchor=MSO_ANCHOR.MIDDLE)

# =========================================================================
# Slide 2 — Motivation
# =========================================================================
s = slide()
header(s, "Motivation", "A good overlay is necessary — but not sufficient")
bullet(s, Inches(0.55), Inches(1.45), Inches(6.7), Inches(4.6), [
    ("Compact models are usually calibrated ", "by matching one measured I–V loop. A clean overlay can be reached even when very different parameter sets fit equally well."),
    ("The risk: ", "fit knobs get mistaken for material/process information — two fits with identical butterfly curves can disagree on Eₐ, Rₛ, or gap geometry."),
    ("We separate two questions rarely reported for RRAM:", ""),
], size=15, gap=12)
# two definition cards
cy = Inches(3.6)
rect(s, Inches(0.75), cy, Inches(6.3), Inches(1.05), WHITE); rect(s, Inches(0.75), cy, Pt(5), Inches(1.05), TEAL)
txt(s, Inches(1.0), cy+Inches(0.1), Inches(6.0), Inches(0.9),
    [[("Generalization", 15, TEAL, True, False)],
     [("Does a fit to one representative cycle predict the other measured cycles of the same device?", 12.5, GRAY, False, False)]], space_after=2)
cy2 = Inches(4.85)
rect(s, Inches(0.75), cy2, Inches(6.3), Inches(1.05), WHITE); rect(s, Inches(0.75), cy2, Pt(5), Inches(1.05), GOLD)
txt(s, Inches(1.0), cy2+Inches(0.1), Inches(6.0), Inches(0.9),
    [[("Identifiability", 15, RGBColor(0xC8,0x8A,0x00), True, False)],
     [("Which fitted parameters stay stable when the measured cycle population is resampled?", 12.5, GRAY, False, False)]], space_after=2)
# right panel: the claim
rect(s, Inches(7.5), Inches(1.5), Inches(5.25), Inches(4.55), LIGHT)
rect(s, Inches(7.5), Inches(1.5), Inches(5.25), Inches(0.55), NAVY)
txt(s, Inches(7.7), Inches(1.5), Inches(5.0), Inches(0.55),
    [[("Our position", 14, WHITE, True, False)]], anchor=MSO_ANCHOR.MIDDLE)
txt(s, Inches(7.8), Inches(2.25), Inches(4.7), Inches(3.6),
    [[("Reliable compact-model extraction must report ", 15, GRAY, False, False),
      ("three", 15, NAVY, True, False),
      (" things together:", 15, GRAY, False, False)],
     [("", 6, GRAY, False, False)],
     [("1   Fit quality", 16, NAVY, True, False)],
     [("2   Cycle-to-cycle generalization", 16, NAVY, True, False)],
     [("3   Parameter identifiability", 16, NAVY, True, False)],
     [("", 6, GRAY, False, False)],
     [("…plus conduction-regime validity, so we know where the device physics sits outside the model.", 13, MIDGRAY, False, True)]],
    space_after=8, line_spacing=1.05)
footer(s, 2)

# =========================================================================
# Slide 3 — Devices & DOE
# =========================================================================
s = slide()
header(s, "Devices & Experiment", "Twelve TaOₓ deposition conditions (DOE)")
bullet(s, Inches(0.55), Inches(1.45), Inches(6.3), Inches(4.4), [
    ("Sputter-deposited TaOₓ ", "cross-point RRAM, 4 µm feature, asymmetric Ta-oxide bilayer stack."),
    ("Two fab-facing knobs: ", "O₂ fraction (20–35%) and RF sputter power (75–250 W)."),
    ("Face-centered factorial ", "with 4 replicated center points (S9–S12) — lets us test which extracted parameter is stable enough to plot vs. process."),
    ("Bipolar DC switching ", "on a Keysight B1500; automated quality screen rejects shorted / open / noise-floor sweeps."),
    ("S1 reference device: ", "all 40 cycles pass, mean quality 8.9/10."),
], size=14, gap=10)
# DOE table
table(s, Inches(7.35), Inches(1.55), Inches(5.4),
      ["Sample", "O₂ (%)", "Power (W)"],
      [["S1","20","75"],["S2","20","250"],["S3","35","75"],["S4","35","250"],
       ["S5","20","162.5"],["S6","35","162.5"],["S7","27.5","75"],["S8","27.5","250"],
       ["S9–S12","27.5","162.5  (×4 center)"]],
      colw=[1.2,1,1.6], fs=12, hfs=12.5, rowh=Inches(0.40))
txt(s, Inches(7.35), Inches(6.05), Inches(5.4), Inches(0.4),
    [[("Deposition design of experiments (Table I).", 10.5, MIDGRAY, False, True)]], align=PP_ALIGN.CENTER)
footer(s, 3)

# =========================================================================
# Slide 4 — Extraction pipeline
# =========================================================================
s = slide()
header(s, "Methodology", "A device-first extraction pipeline")
steps = [
    ("1", "Medoid cycle", "pick the representative measured sweep by ranked quality"),
    ("2", "Regime classify", "ohmic / PF / Schottky / FN per segment"),
    ("3", "Physics priors", "regime-tied prior windows for 21 parameters"),
    ("4", "Mechanism loss", "down-weight Schottky/FN points the model can't represent"),
    ("5", "Bayesian opt.", "HSPICE-in-the-loop, 48+160 evals, then Nelder–Mead"),
    ("6", "Generalization", "score the medoid fit on every other cycle"),
    ("7", "Identifiability", "200 cycle-bootstrap refits + Fisher cross-check"),
    ("8", "Ablation", "isolate what priors / regime / BO each contribute"),
]
x0, y0 = Inches(0.55), Inches(1.55)
cw, ch = Inches(2.95), Inches(1.55)
gapx, gapy = Inches(0.18), Inches(0.30)
for i, (num, head, body) in enumerate(steps):
    r, c = divmod(i, 4)
    x = x0 + c*(cw+gapx); y = y0 + r*(ch+gapy)
    rect(s, x, y, cw, ch, WHITE)
    rect(s, x, y, cw, Inches(0.5), NAVY)
    # number badge
    bd = s.shapes.add_shape(MSO_SHAPE.OVAL, x+Inches(0.12), y+Inches(0.09), Inches(0.32), Inches(0.32))
    bd.fill.solid(); bd.fill.fore_color.rgb = GOLD; bd.line.fill.background(); bd.shadow.inherit=False
    tfb = bd.text_frame; tfb.word_wrap=False
    pp = tfb.paragraphs[0]; pp.alignment=PP_ALIGN.CENTER
    rr=pp.add_run(); rr.text=num; rr.font.size=Pt(14); rr.font.bold=True; rr.font.color.rgb=NAVY
    txt(s, x+Inches(0.52), y+Inches(0.04), cw-Inches(0.6), Inches(0.42),
        [[(head, 14.5, WHITE, True, False)]], anchor=MSO_ANCHOR.MIDDLE)
    txt(s, x+Inches(0.15), y+Inches(0.6), cw-Inches(0.3), Inches(0.9),
        [[(body, 11.5, GRAY, False, False)]], line_spacing=1.0)
# arrow note
txt(s, Inches(0.55), Inches(5.85), Inches(12.2), Inches(0.7),
    [[("Stanford–PKU Verilog-A model (rram_v_1_0_0): ", 13, NAVY, True, False),
      ("Iₜₕ = I₀·exp(−g/g₀)·sinh(V/V₀), gap evolves thermally.  Polarity-split V₀, Eₐ, ν₀, g; shared scale/parasitic terms.  616 HSPICE transients per point estimate.",
       13, GRAY, False, False)]], line_spacing=1.05)
footer(s, 4)

# =========================================================================
# Slide 5 — Conduction regimes
# =========================================================================
s = slide()
header(s, "Result 1 · Device Physics", "Ohmic LRS, Schottky-limited HRS — across the whole DOE")
add_image(s, os.path.join(FIG, "step02_S1/S1_B6-01-4um-12_regime_overview.png"),
          Inches(0.5), Inches(1.4), Inches(6.4), Inches(4.4),
          caption="S1 regime classification of the four resistance-state segments (Fig. 1).")
add_image(s, os.path.join(FIG, "results/variability/mechanism_map.png"),
          Inches(7.05), Inches(1.55), Inches(5.8), Inches(2.2),
          caption="Dominant mechanism & cycle stability, all 12 conditions (Fig. 2).")
bullet(s, Inches(7.05), Inches(4.25), Inches(5.8), Inches(2.4), [
    ("Post-SET LRS ", "is ohmic-dominant for every condition (66–100% stability)."),
    ("Post-RESET HRS ", "is Schottky-dominant in 92.5–100% of cycles, εᵣᵈʸⁿ = 4.7–34 (physically admissible)."),
    ("PF is rare ", "— it is not the dominant mechanism for any state/condition."),
    ("Implication: ", "Stanford bulk sinh law has no explicit Schottky branch → expect a RESET residual floor."),
], size=12.5, gap=7)
footer(s, 5)

# =========================================================================
# Slide 6 — Fit quality
# =========================================================================
s = slide()
header(s, "Result 2 · Point Estimate", "The fits reproduce the measured butterfly curves")
metric_card(s, Inches(0.55), Inches(1.5), Inches(2.95), Inches(1.95),
            "0.530", "Mean SET RMSE", "log₁₀|I| decades", TEAL)
metric_card(s, Inches(3.65), Inches(1.5), Inches(2.95), Inches(1.95),
            "0.761", "Mean RESET RMSE", "harder: Schottky HRS", GOLD)
# small per-condition table
table(s, Inches(0.55), Inches(3.85), Inches(6.1),
      ["Cond.", "RMSE SET", "RMSE RESET", "DW SET", "DW RESET"],
      [["S1","0.500","0.689","0.86","0.85"],
       ["S2","0.772","1.016","0.46","0.56"],
       ["S6","0.468","0.650","0.94","0.93"],
       ["S8","0.495","1.001","1.03","0.54"],
       ["Mean","0.530","0.761","—","—"]],
      colw=[1,1.2,1.4,1,1.2], fs=11, hfs=10.5, rowh=Inches(0.33))
txt(s, Inches(0.55), Inches(6.0), Inches(6.1), Inches(0.4),
    [[("Excerpt of Table II (12 conditions total).", 10.5, MIDGRAY, False, True)]])
bullet(s, Inches(7.0), Inches(1.55), Inches(5.85), Inches(4.6), [
    ("Captured: ", "hysteresis order, SET & RESET transitions, compliance region, LRS return branch."),
    ("Largest residuals ", "sit at the SET transition and the Schottky-limited HRS approach — exactly where the regime map warned the current law is incomplete."),
    ("Durbin–Watson < 2 everywhere: ", "residuals are correlated along the sweep — remaining error is systematic model mismatch, not measurement scatter."),
    ("S2 is the worst case ", "(O₂-poor, high power): largest RESET RMSE, lowest SET DW, least stable Schottky assignment."),
], size=13.5, gap=11)
footer(s, 6)

# =========================================================================
# Slide 7 — Generalization
# =========================================================================
s = slide()
header(s, "Result 3 · Generalization", "A one-cycle fit predicts every other cycle")
add_image(s, os.path.join(FIG, "results/paper_alt/heldout_rmse.png"),
          Inches(0.5), Inches(1.45), Inches(6.5), Inches(2.7),
          caption="Held-out per-cycle RMSE; stars = in-sample medoid (Fig. 4).")
add_image(s, os.path.join(FIG, "results/paper_alt/heldout_overlay_S1.png"),
          Inches(0.5), Inches(4.55), Inches(6.5), Inches(2.15),
          caption="S1 fit vs. measured cycle-to-cycle envelope (Fig. 5).")
# metric cards on right
metric_card(s, Inches(7.3), Inches(1.5), Inches(2.6), Inches(1.8),
            "0.012", "SET gap", "held-out − in-sample", TEAL)
metric_card(s, Inches(10.15), Inches(1.5), Inches(2.6), Inches(1.8),
            "0.039", "RESET gap", "decades", GOLD)
bullet(s, Inches(7.3), Inches(3.6), Inches(5.55), Inches(3.2), [
    ("Held-out medians ", "0.542 (SET) / 0.800 (RESET) vs. in-sample 0.530 / 0.761."),
    ("Every condition: ", "in-sample RMSE falls inside the held-out interquartile range."),
    ("Coverage: ", "fitted SET curve stays inside the measured min–max band at 77% of points (63% for RESET)."),
    ("Takeaway: ", "the fit describes the device population — not a memorized trace. Lower RESET coverage = missing Schottky branch, not overfitting."),
], size=13, gap=9)
footer(s, 7)

# =========================================================================
# Slide 8 — Identifiability
# =========================================================================
s = slide()
header(s, "Result 4 · Identifiability", "What the DC data actually constrain")
add_image(s, os.path.join(FIG, "results/variability/parameter_cv.png"),
          Inches(0.5), Inches(1.45), Inches(6.4), Inches(4.3),
          caption="Cycle-bootstrap CV, 200 refits × 12 conditions — primary evidence (Fig. 6).")
bullet(s, Inches(7.1), Inches(1.5), Inches(5.75), Inches(3.4), [
    ("Repeatable: ", "branch voltage scales V₀, median CV ≈ 0.28 — the butterfly curvature pins them down."),
    ("Not repeatable: ", "Rₛ (CV 1.44), velocity prefactors ν₀ (1.19 / 1.28), I₀ and Eₐ also vary widely (CV > 1)."),
    ("Fisher cross-check ", "agrees on the broad picture, but condition numbers 10¹⁸–10⁶⁶ make it a local sensitivity map only."),
    ("Rₛ is the cautionary case: ", "looks locally well-determined at one optimum, yet swings under cycle resampling."),
], size=13, gap=10)
# bottom banner conclusion
rect(s, Inches(7.1), Inches(5.15), Inches(5.75), Inches(1.45), NAVY)
txt(s, Inches(7.35), Inches(5.3), Inches(5.3), Inches(1.2),
    [[("Bottom line", 13, GOLD, True, False)],
     [("DC butterfly data constrain effective branch scales & switching-field combinations — not a unique split into prefactors, activation energies, and gap geometry.",
       13.5, WHITE, False, False)]], space_after=4, line_spacing=1.05)
footer(s, 8)

# =========================================================================
# Slide 9 — Ablation
# =========================================================================
s = slide()
header(s, "Result 5 · Ablation", "What each ingredient actually buys")
table(s, Inches(0.6), Inches(1.7), Inches(7.0),
      ["Variant", "RMSE SET", "RMSE RESET"],
      [["Regime-conditioned + weighting", "0.530 ± 0.081", "0.761 ± 0.123"],
       ["Physics priors + BO", "0.546 ± 0.077", "0.756 ± 0.124"],
       ["Uninformative priors + BO", "0.537 ± 0.076", "0.755 ± 0.126"],
       ["Physics priors, no BO", "0.571 ± 0.115", "1.528 ± 0.434"]],
      colw=[3.2,1.7,1.7], fs=12.5, hfs=12.5, rowh=Inches(0.55))
txt(s, Inches(0.6), Inches(4.4), Inches(7.0), Inches(0.4),
    [[("Unweighted validation RMSE so weighting gives no scoring advantage (Table IV).", 11, MIDGRAY, False, True)]])
bullet(s, Inches(8.0), Inches(1.7), Inches(4.85), Inches(4.5), [
    ("Optimization is the must-have: ", "no-BO RESET balloons to 1.53 decades vs. ~0.76 for optimized variants."),
    ("Three optimized variants ", "land at nearly identical overlay error."),
    ("So priors/regime don't lower the overlay — ", "they stop the fit from abusing unsupported Schottky/FN HRS regions to distort Stanford bulk parameters."),
    ("Reinforces the thesis: ", "overlay alone can't establish physical extraction. Generalization + identifiability decide what's trustworthy."),
], size=13, gap=11)
footer(s, 9)

# =========================================================================
# Slide 10 — Deposition trends
# =========================================================================
s = slide()
header(s, "Result 6 · Process Trends", "Only identifiable parameters get a response surface")
add_image(s, os.path.join(FIG, "results/paper_alt/deposition_trends.png"),
          Inches(0.5), Inches(1.45), Inches(5.0), Inches(4.6),
          caption="Bootstrap-identifiable parameters vs. deposition (Fig. 8).")
add_image(s, os.path.join(FIG, "results/paper_alt/hrs_schottky_trend.png"),
          Inches(5.65), Inches(1.55), Inches(7.1), Inches(2.4),
          caption="Post-RESET HRS dynamic permittivity vs. O₂ and power (Fig. 9).")
bullet(s, Inches(5.65), Inches(4.25), Inches(7.1), Inches(2.5), [
    ("V₀,SET and V₀,RESET ", "have tight bootstrap CIs and move systematically with deposition → usable process trends."),
    ("Rₛ spans 1–2 decades ", "in its bootstrap CI — locally Fisher-identifiable, but must NOT be a response-surface output."),
    ("HRS εᵣᵈʸⁿ = 4.7–32 ", "for all 12 conditions; ~3× scatter across center points (S9–S12) reveals interface variability — an automated extension of prior manual analysis."),
], size=12.5, gap=8)
footer(s, 10)

# =========================================================================
# Slide 11 — Conclusions
# =========================================================================
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, 0, Pt(10), SH, GOLD)
txt(s, Inches(0.8), Inches(0.55), Inches(11.5), Inches(0.5),
    [[("TAKEAWAYS", 14, GOLD, True, False)]])
txt(s, Inches(0.8), Inches(1.0), Inches(11.7), Inches(0.8),
    [[("Report extraction with three numbers, not one", 30, WHITE, True, False)]])
rect(s, Inches(0.8), Inches(1.85), Inches(11.6), Pt(3), TEAL)
concl = [
    ("Fits are accurate", "Mean RMSE 0.530 (SET) / 0.761 (RESET) decades across all 12 TaOₓ conditions."),
    ("…and they generalize", "One-cycle fit predicts held-out cycles within 0.012 / 0.039 decades — the device, not one trace."),
    ("Most parameters aren't identifiable", "Only branch voltage scales V₀ are repeatable (CV ≈ 0.28); Rₛ, ν₀, Eₐ, gap geometry are not (CV > 1)."),
    ("Process trends, conservatively", "Only V₀ supports a deposition response surface; Rₛ cannot, despite looking locally identifiable."),
    ("Model adequacy is the RESET floor", "Post-RESET HRS is Schottky-dominant in 92.5–100% of cycles — outside the Stanford bulk sinh law."),
]
y = Inches(2.25)
for head, body in concl:
    bd = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.85), y+Inches(0.07), Inches(0.28), Inches(0.28))
    bd.fill.solid(); bd.fill.fore_color.rgb = TEAL; bd.line.fill.background(); bd.shadow.inherit=False
    txt(s, Inches(1.35), y, Inches(11.2), Inches(0.85),
        [[(head + "  —  ", 16.5, GOLD, True, False),
          (body, 15, RGBColor(0xDD,0xE6,0xEE), False, False)]], line_spacing=1.02)
    y += Inches(0.92)
rect(s, Inches(0.8), Inches(6.95), Inches(11.6), Inches(0.001), TEAL)
txt(s, Inches(0.8), Inches(6.95), Inches(11.7), Inches(0.45),
    [[("Next: add a barrier-limited HRS branch to the compact model — the regime map already supplies the target windows and slopes.",
       13, RGBColor(0x9F,0xB6,0xC6), False, True)]])

out = os.path.join(FIG, "results", "Stanford_RRAM_advisor_slides.pptx")
prs.save(out)
print("Saved:", out, "| slides:", len(prs.slides._sldIdLst))
