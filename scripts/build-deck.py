"""Build the GoldLens round-2 deck from the Hack in Hills template.

Usage: build-deck.py TEMPLATE.pptx MEDIA_DIR SCREENS_DIR OUTPUT.pptx
Reuses the template master, header strip, cover art and logos. Every diagram is native, editable shapes.
All numbers come from docs/OPPORTUNITY_EVALUATION.md, docs/CONTRACT_MATRIX.md and docs/BUILD_LOG.md.
"""
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

template, media, screens, output = (Path(a) for a in sys.argv[1:5])

INK, GOLD, SLATE, LINE, PANEL = "1B2430", "C8962E", "5B6B7B", "D9DEE4", "F4F6F8"
GOLD_SOFT, GREEN, RED, BLUE, WHITE = "F7EEDB", "2E8B57", "B94A48", "3D5A80", "FFFFFF"
HEAD, BODY, MONO = "Montserrat", "Calibri", "Consolas"
SCALE = 1.25  # slide is 20in wide, so point sizes are scaled up for legibility
rgb = RGBColor.from_string
LEFT, CENTER = PP_ALIGN.LEFT, PP_ALIGN.CENTER

prs = Presentation(str(template))
# Keep the template master/layouts; drop the old slides.
for slide_id in list(prs.slides._sldIdLst):
    prs.part.drop_rel(slide_id.rId)
    prs.slides._sldIdLst.remove(slide_id)
layout = next((l for l in prs.slide_layouts if not len(l.placeholders)), prs.slide_layouts[len(prs.slide_layouts) - 1])
SW, SH = prs.slide_width, prs.slide_height  # 20in x 11.25in


def box(slide, x, y, w, h, fill=PANEL, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, dash=False, lw=1.0):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line); s.line.width = Pt(lw)
        if dash:
            from pptx.enum.dml import MSO_LINE
            s.line.dash_style = MSO_LINE.DASH
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, paras, size=14, color=INK, bold=False, align=LEFT, anchor=MSO_ANCHOR.TOP, font=BODY, shape=None, space=0):
    s = shape or slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = anchor
    paras = [paras] if isinstance(paras, (str, list)) and (isinstance(paras, str) or (paras and isinstance(paras[0], tuple))) else paras
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        runs = [(para, {})] if isinstance(para, str) else para
        for chunk, o in runs:
            r = p.add_run(); r.text = chunk
            r.font.name = o.get("font", font); r.font.size = Pt(round(o.get("size", size) * SCALE, 1))
            r.font.bold = o.get("bold", bold); r.font.color.rgb = rgb(o.get("color", color))
    return s


def label(slide, x, y, w, h, fill, content, size=14, color=WHITE, bold=True, shape=MSO_SHAPE.ROUNDED_RECTANGLE, align=CENTER, font=BODY, line=None, radius=0.2):
    s = box(slide, x, y, w, h, fill=fill, line=line, shape=shape, radius=radius)
    text(slide, x, y, w, h, content, size=size, color=color, bold=bold, align=align, anchor=MSO_ANCHOR.MIDDLE, font=font, shape=s)
    return s


def badge(slide, x, y, n, d=0.55, fill=GOLD, color=WHITE, size=16):
    return label(slide, x, y, d, d, fill, str(n), size=size, color=color, shape=MSO_SHAPE.OVAL)


def arrow(slide, x, y, w=0.6, h=0.5, fill=GOLD):
    s = box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.RIGHT_ARROW)
    return s


def header(slide, kicker, title):
    slide.shapes.add_picture(str(media / "image4.png"), 0, 0, SW, Emu(1205517))
    text(slide, 0.6, 1.4, 12, 0.35, kicker.upper(), size=10, color=GOLD, bold=True, font=BODY)
    text(slide, 0.6, 1.7, 18.8, 0.8, title.upper(), size=24, bold=True, font=HEAD)
    text(slide, 0.6, 10.75, 18.8, 0.35, "GoldLens · Team ERROR 404 · Paper research only. Demo data is synthetic and labelled as such.", size=9, color=SLATE)


def new_slide(notes):
    s = prs.slides.add_slide(layout)
    s.notes_slide.notes_text_frame.text = notes
    return s


# 1. Cover -------------------------------------------------------------------------------------
s = new_slide("Introduce GoldLens in one sentence: a local research tool that compares MCX gold futures fairly and raises paper-only alerts. "
              "Say the team name and who built what. Mention up front that nothing here executes trades.")
cover = Image.open(media / "image1.jpg").rotate(90, expand=True)
w, h = cover.size
cover.crop((0, int(h * 0.12), w, int(h * 0.12) + int(w / 4.46))).save(screens / "cover-banner.jpg", quality=92)
s.shapes.add_picture(str(screens / "cover-banner.jpg"), 0, 0, SW, Emu(4096000))
s.shapes.add_picture(str(media / "image2.png"), Emu(318675), Emu(296224), Emu(7240346), Emu(791925))
s.shapes.add_picture(str(media / "image3.png"), Emu(12520575), Emu(296231), Emu(5599601), Emu(791925))
text(s, 0.6, 4.75, 12, 1.2, "GoldLens", size=52, bold=True, font=HEAD)
text(s, 0.6, 6.05, 16, 0.9, "Point-in-time research alerts for MCX gold futures", size=23, color=SLATE)
for i, (chip, fill) in enumerate([("Local-first", INK), ("Exact-expiry pairing", INK), ("Paper research only", GOLD)]):
    label(s, 0.7 + i * 3.55, 7.05, 3.35, 0.6, fill, chip, size=15)
text(s, 0.6, 8.3, 4, 0.4, "TEAM ERROR 404", size=14, color=GOLD, bold=True)
for i, (name, role) in enumerate([("Anjela Joseph", "Backend & system integration"), ("Jose Mathew Moolayil", "Frontend & UI/UX"), ("Johaan Liju James", "AI/ML & API logic")]):
    x = 0.6 + i * 6.2
    box(s, x, 8.8, 5.9, 1.4, fill=PANEL)
    text(s, x + 0.15, 8.95, 5.6, 0.5, name, size=20, bold=True)
    text(s, x + 0.15, 9.5, 5.6, 0.5, role, size=15, color=SLATE)

# 2. Problem statement -------------------------------------------------------------------------
s = new_slide("This is the required problem-statement slide. Read the dark banner aloud. Then walk the cards left to right: the four contracts differ in quote size, "
              "lot, purity and delivery basis. The GOLDM example is a hand check from our contract matrix: 74,625 per 10 g is 7,462.50 per gram, "
              "and 7,492.50 per gram once converted to 999 purity. End on why it matters: costs and liquidity can erase a paper edge.")
header(s, "Slide 2", "Problem statement")
box(s, 0.6, 2.5, 18.8, 1.45, fill=INK)
box(s, 0.6, 2.5, 0.18, 1.45, fill=GOLD, radius=0.0)
text(s, 1.0, 2.5, 18.2, 1.45, [[("Four MCX gold futures look alike, but their quotes are not directly comparable. ", {}),
     ("Mixing them up produces false arbitrage signals and misleading backtests.", {"color": "F1D58C"})]],
     size=21, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 4.15, 9, 0.45, "Same metal, four different quotes", size=17, bold=True, color=SLATE)
contracts = [("GOLDM", "10 g", "100 g", "0.995", "Ahmedabad", {"lot", "purity"}),
             ("GOLDTEN", "10 g", "10 g", "0.999", "Ahmedabad", set()),
             ("GOLDGUINEA", "8 g", "8 g", "0.999", "Ahmedabad", {"quote"}),
             ("GOLDPETAL", "1 g", "1 g", "0.999", "Mumbai", {"quote", "basis"})]
for i, (sym, quote, lot, purity, basis, odd) in enumerate(contracts):
    x, y = 0.6 + (i % 2) * 4.75, 4.65 + (i // 2) * 2.55
    box(s, x, y, 4.55, 2.35, fill=PANEL, line=LINE)
    text(s, x + 0.1, y + 0.08, 4.3, 0.5, sym, size=19, bold=True, font=HEAD)
    for j, (key, name, val) in enumerate([("quote", "Quote per", quote), ("lot", "Lot size", lot), ("purity", "Purity", purity), ("basis", "Basis", basis)]):
        yy = y + 0.7 + j * 0.39
        text(s, x + 0.1, yy, 1.9, 0.38, name, size=14, color=SLATE)
        text(s, x + 2.0, yy, 2.4, 0.38, val, size=15, bold=True, color=GOLD if key in odd else INK)
text(s, 10.3, 4.15, 9, 0.45, "Three ways a spread signal goes wrong", size=17, bold=True, color=SLATE)
pitfalls = [("Units and purity", "GOLDM ₹74,625 per 10 g is ₹7,492.50 per gram at 999 purity. Same quote, different number."),
            ("Expiry", "A month label is not an expiry date. Only exact-date matches can be paired."),
            ("Future data", "A backtest that peeks at later prices looks great and proves nothing.")]
for i, (head, body) in enumerate(pitfalls):
    y = 4.65 + i * 1.7
    box(s, 10.3, y, 9.1, 1.5, fill=WHITE, line=LINE)
    badge(s, 10.5, y + 0.45, i + 1)
    text(s, 11.3, y + 0.12, 8.0, 0.45, head, size=18, bold=True)
    text(s, 11.3, y + 0.58, 8.0, 0.85, body, size=15, color=SLATE)
label(s, 0.6, 9.95, 18.8, 0.7, GOLD_SOFT, "Why it matters: a paper edge that ignores costs and liquidity can turn negative once they are counted.", size=16, color=INK, line=GOLD, radius=0.15)

# 3. Solution ----------------------------------------------------------------------------------
s = new_slide("GoldLens is a pipeline, not a black box. Each step is a module in the backend and each can be inspected in the UI. "
              "The three tiles are our unique value: we only use what was knowable at the chosen time, we refuse to alert on bad inputs, and we never show a probability we have not calibrated.")
header(s, "Solution", "From raw quotes to a paper alert")
steps = [("Ingest & validate", "Source, unit, currency, observed and available time"),
         ("Normalize", "Every quote to INR per gram at 999 purity"),
         ("Pair exactly", "Same exact expiry date. Never inferred from a month"),
         ("Score the spread", "Z-score vs ten prior common sessions only"),
         ("Cost filter", "BASE, STRESS and SEVERE cost scenarios"),
         ("Paper alert", "In-app notice, then follow its outcome")]
for i, (head, body) in enumerate(steps):
    x = 0.6 + i * 3.2
    box(s, x, 2.6, 2.8, 3.4, fill=PANEL, line=LINE)
    badge(s, x + 0.2, 2.8, i + 1, fill=GOLD if i == 5 else INK)
    text(s, x + 0.1, 3.5, 2.6, 0.9, head, size=18, bold=True, font=BODY)
    text(s, x + 0.1, 4.45, 2.6, 1.5, body, size=14, color=SLATE)
    if i < 5:
        arrow(s, x + 2.86, 4.05, 0.28, 0.4)
text(s, 0.6, 6.4, 12, 0.5, "What makes it different", size=20, bold=True)
tiles = [("Point-in-time", "Only records observed and available at the cutoff. Contract specs are immutable versions."),
         ("Fails closed", "Missing, stale or unevaluated inputs give no alert. Real data never falls back to synthetic."),
         ("Honest by design", "No probability until calibration is evaluated. Costs and liquidity are always shown.")]
for i, (head, body) in enumerate(tiles):
    x = 0.6 + i * 6.4
    box(s, x, 7.05, 6.0, 3.0, fill=INK)
    box(s, x, 7.05, 6.0, 0.14, fill=GOLD, radius=0.0)
    text(s, x + 0.25, 7.4, 5.5, 0.6, head, size=22, bold=True, color="F1D58C", font=HEAD)
    text(s, x + 0.25, 8.2, 5.5, 1.7, body, size=16, color=WHITE)

# 4. Prototype screens -------------------------------------------------------------------------
s = new_slide("This is the real running prototype, captured from the browser. Left is Monitor: watchlist with exact expiry, freshness and source time. "
              "Right is Alerts: what the evaluation supports, then session rules. Walk the five-step flow at the bottom. The synthetic banner is always visible.")
header(s, "Prototype", "Two screens, one workflow")
for i, (img, head, body) in enumerate([("monitor.png", "Monitor", "Watchlist by exact expiry, with freshness, source and availability time"),
                                       ("alerts-evidence.png", "Alerts", "What the evaluation supports, plus rules for each paper session")]):
    x = 0.6 + i * 9.7
    box(s, x - 0.08, 2.5, 9.26, 5.86, fill=INK, radius=0.02)
    s.shapes.add_picture(str(screens / img), Inches(x), Inches(2.58), Inches(9.1), Inches(5.69))
    text(s, x, 8.5, 9.1, 0.45, head, size=20, bold=True)
    text(s, x, 8.95, 9.1, 0.45, body, size=14, color=SLATE)
flow = ["Watch exact contracts", "Set alert rules", "Scan at a cutoff", "Review evidence", "Follow paper outcome"]
for i, f in enumerate(flow):
    label(s, 0.6 + i * 3.8, 9.75, 3.55, 0.7, INK if i < 4 else GOLD, f, size=15, shape=MSO_SHAPE.PENTAGON, radius=0)

# 5. Anatomy of an alert -----------------------------------------------------------------------
s = new_slide("This is one real alert, from the synthetic demo. The z-score is large because the synthetic data has an injected anomaly, which we state openly. "
              "Point at each numbered part: identity and timing, the supporting observations, costs under three scenarios, uncertainty text, and the follow-up paper outcome. "
              "Note that no probability is shown.")
header(s, "How the prototype works", "Anatomy of one alert")
IMG_W = 8.9
IMG_H = IMG_W * 1089 / 1216
box(s, 0.52, 2.52, IMG_W + 0.16, IMG_H + 0.16, fill=INK, radius=0.015)
s.shapes.add_picture(str(screens / "alert-card.png"), Inches(0.6), Inches(2.6), Inches(IMG_W), Inches(IMG_H))
parts = [(100, "Identity and timing", "Both contracts, exact expiry, signal time, five-session horizon, model version, expiry of the signal"),
         (350, "Supporting observations", "Z-score, spread and ten prior sessions. 22 source records with observed and available times. No probability: calibration is unevaluated"),
         (560, "Estimated costs", "BASE, STRESS and SEVERE, itemised for both legs, entry and exit"),
         (800, "Liquidity and settlement uncertainty", "Daily proxies only. Delivery terms shown per leg. Nothing implied as guaranteed"),
         (970, "Paper outcome", "Pending until entry and exit dates are observed. Missing data is never counted as a loss")]
for i, (py, head, body) in enumerate(parts):
    y = 2.6 + py * IMG_W / 1216
    badge(s, 9.3, y - 0.3, i + 1)
    text(s, 10.2, y - 0.5, 9.2, 0.45, head, size=19, bold=True)
    text(s, 10.2, y - 0.05, 9.2, 0.85, body, size=15, color=SLATE)

# 6. Architecture -----------------------------------------------------------------------------
s = new_slide("Business math lives in the Python backend. The browser only displays API results. Everything binds to 127.0.0.1. "
              "Synthetic and real data live in separate SQLite files and never mix. An alert is only allowed if the model implementation still matches the evaluation report by hash.")
header(s, "Technology & architecture", "How it is built")
box(s, 0.6, 2.6, 3.7, 5.9, fill=PANEL, line=LINE)
text(s, 0.7, 2.7, 3.5, 0.5, "Browser", size=20, bold=True, font=HEAD)
text(s, 0.7, 3.3, 3.5, 1.2, "Next.js · React · TypeScript · Tailwind", size=15, color=SLATE)
label(s, 0.85, 4.7, 3.2, 0.65, INK, "Monitor", size=16)
label(s, 0.85, 5.5, 3.2, 0.65, INK, "Alerts", size=16)
text(s, 0.7, 6.4, 3.5, 1.9, "Displays API results only. No financial calculation in the frontend.", size=14, color=SLATE)
arrow(s, 4.4, 5.3, 0.75, 0.55)
text(s, 4.2, 5.9, 1.2, 0.6, "127.0.0.1 only", size=11, color=SLATE, align=CENTER)
box(s, 5.3, 2.6, 8.3, 5.9, fill=WHITE, line=INK, lw=1.75)
text(s, 5.4, 2.65, 8.1, 0.5, "FastAPI · Pydantic · Pandas", size=20, bold=True, font=HEAD)
mods = [("ingestion", "validated import"), ("reference", "immutable spec versions"), ("normalization", "INR/g at 999 purity"), ("research", "exact-expiry snapshot"),
        ("monitor", "watchlist, freshness"), ("opportunity", "z-score, costs, labels"), ("opportunity_evaluation", "walk-forward test"), ("alerts", "dedup, cooldown, outcomes")]
for i, (m, d) in enumerate(mods):
    x, y = 5.45 + (i % 2) * 4.0, 3.3 + (i // 2) * 1.28
    box(s, x, y, 3.85, 1.12, fill=PANEL, line=LINE)
    text(s, x + 0.1, y + 0.1, 3.65, 0.45, m, size=15, bold=True, font=MONO, color=BLUE)
    text(s, x + 0.1, y + 0.58, 3.65, 0.45, d, size=14, color=SLATE)
arrow(s, 13.7, 5.3, 0.75, 0.55)
stores = [("SQLite · synthetic", "invented demo data", GOLD), ("SQLite · real", "imported data only", BLUE),
          ("Alert store", "one per dataset", SLATE), ("Evaluation report", "hash-bound to model", SLATE)]
for i, (head, sub, color) in enumerate(stores):
    y = 2.6 + i * 1.5
    c = box(s, 14.6, y, 4.8, 1.3, fill=color, shape=MSO_SHAPE.CAN, radius=0)
    text(s, 14.6, y + 0.2, 4.8, 1.0, [[(head, {"bold": True, "size": 16})], [(sub, {"size": 13})]], color=WHITE, align=CENTER, anchor=MSO_ANCHOR.MIDDLE, shape=c)
for i, (txt, fill) in enumerate([("pytest: 165 backend tests", INK), ("Playwright: browser checks on the real UI", INK), ("Synthetic and real never mix", GOLD)]):
    label(s, 0.6 + i * 6.35, 9.2, 6.1, 0.7, fill, txt, size=15)
text(s, 0.6, 10.0, 18.8, 0.5, "All services bind to loopback only. No deployment, no external notification channel, no trade execution.", size=14, color=SLATE)

# 7. Gates ---------------------------------------------------------------------------------------
s = new_slide("This is the heart of the safety story. An alert must pass every gate. If any gate fails, the app records the reason and shows it. "
              "The order is simplified here; the exact order is in backend/alerts.py. For real data, the second gate always fails today because no model has been evaluated on real data.")
header(s, "Alert logic", "Nine gates before an alert appears")
gates = ["Required inputs present and valid", "Dataset has an evaluated model", "Inputs fresh within your limit", "|z| at or above your threshold",
         "Estimated costs available", "SEVERE-cost filter passed (model policy)", "Not a duplicate: pair, date, direction", "Outside the cooldown", "Not expired"]
for i, g in enumerate(gates):
    w = 12.2 - i * 0.55
    x = 0.6 + (12.2 - w) / 2
    label(s, x, 2.55 + i * 0.74, w, 0.64, [INK, "26364A", "26364A", "34495E", "34495E", BLUE, BLUE, "4A6B96", "4A6B96"][i], f"{i + 1}   {g}", size=15, bold=False, align=CENTER, radius=0.25)
label(s, 3.2, 9.3, 7.0, 0.85, GOLD, "In-app paper alert", size=22, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3)
text(s, 13.2, 2.55, 6.2, 0.9, "Every “no” is stored with its reason", size=20, bold=True)
reasons = [("MISSING_INPUTS", RED), ("STALE", RED), ("COST_FILTER", BLUE), ("DEDUPLICATED", BLUE), ("COOLDOWN", BLUE), ("MODEL_NOT_EVALUATED", RED)]
for i, (r, c) in enumerate(reasons):
    label(s, 13.3 + (i % 2) * 3.15, 3.6 + (i // 2) * 0.85, 3.0, 0.65, WHITE, r, size=13, color=c, font=MONO, line=c, radius=0.25)
box(s, 13.2, 6.5, 6.2, 3.65, fill=GOLD_SOFT, line=GOLD)
text(s, 13.4, 6.65, 5.8, 3.4, [[("Real data today", {"bold": True, "size": 18})],
     [("No model has been evaluated on real data, so real alerts are always suppressed. Nothing falls back to synthetic.", {"size": 15})],
     [("Settings you can change", {"bold": True, "size": 18})],
     [("Policy, minimum |z|, severe-cost threshold, max input age, cooldown, lifetime.", {"size": 15})]], space=6)

# 8. Evidence -----------------------------------------------------------------------------------
s = new_slide("Be upfront here. This is a synthetic test with deliberately injected anomalies, one matched expiry, ten held-out decisions and a single completed outcome. "
              "The baseline alerted once and was positive under BASE and STRESS costs but negative under SEVERE. The cost-filtered model abstained, so there is nothing to compare. "
              "We withhold confidence intervals on purpose. This slide shows how the system measures itself, not that it makes money.")
header(s, "Evaluation", "What the numbers show, and what they do not")
box(s, 0.6, 2.5, 7.4, 6.3, fill=PANEL, line=LINE)
text(s, 0.8, 2.6, 7.0, 0.8, "Alerts across 10 held-out decisions", size=18, bold=True)
for row, (name, count, color) in enumerate([("Fixed-z baseline", 1, GOLD), ("Cost-filtered model", 0, BLUE)]):
    y = 3.7 + row * 2.3
    text(s, 0.8, y, 7.0, 0.45, name, size=16, color=SLATE, bold=True)
    for k in range(10):
        on = k < count
        box(s, 0.9 + k * 0.67, y + 0.6, 0.52, 0.52, fill=color if on else WHITE, line=color, shape=MSO_SHAPE.OVAL, lw=1.75)
    text(s, 0.8, y + 1.2, 7.0, 0.5, f"{count} alert" + ("s" if count != 1 else ""), size=15, bold=True, color=color)
text(s, 0.8, 7.95, 7.0, 0.8, "The cost-filtered model abstained on all 10 decisions.", size=14, color=SLATE)
text(s, 8.4, 2.5, 11, 0.5, "The baseline's one completed outcome: net return in basis points", size=18, bold=True)
cd = CategoryChartData(); cd.categories = ["BASE costs", "STRESS costs", "SEVERE costs"]; cd.add_series("Net return (bps)", (57.32, 17.18, -43.03))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(8.4), Inches(3.05), Inches(11.0), Inches(5.75), cd)
ch = gf.chart
ch.has_legend = False; ch.has_title = False; ch.font.size = Pt(17); ch.font.name = BODY
plot = ch.plots[0]; plot.gap_width = 70; plot.vary_by_categories = False; plot.series[0].invert_if_negative = False
plot.has_data_labels = True
dl = plot.data_labels; dl.number_format = '+0.0" bps";-0.0" bps"'; dl.number_format_is_linked = False
dl.font.size = Pt(19); dl.font.bold = True; dl.position = XL_LABEL_POSITION.OUTSIDE_END
for i, c in enumerate([GREEN, GREEN, RED]):
    pt = plot.series[0].points[i]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(c)
# PowerPoint renders negative bars white unless each data point also disables invertIfNegative.
from lxml import etree
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
for dpt in plot.series[0]._element.findall(f"{{{C}}}dPt"):
    if dpt.find(f"{{{C}}}invertIfNegative") is None:
        inv = etree.SubElement(dpt, f"{{{C}}}invertIfNegative"); inv.set("val", "0")
        dpt.remove(inv); dpt.insert(1, inv)
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
ch.category_axis.format.line.color.rgb = rgb(SLATE)
ch.value_axis.has_major_gridlines = True
ch.value_axis.major_gridlines.format.line.color.rgb = rgb(LINE)
ch.value_axis.minimum_scale = -70; ch.value_axis.maximum_scale = 80
ch.value_axis.tick_labels.font.size = Pt(15)
box(s, 0.6, 9.05, 18.8, 1.55, fill=GOLD_SOFT, line=GOLD)
text(s, 0.85, 9.1, 18.3, 1.45, [[("Read this carefully. ", {"bold": True}), ("Synthetic data with injected anomalies, one expiry, one completed outcome. "
     "Costs are assumed budgets and prices are daily proxies, not fills. No confidence interval is shown because the sample is too small. This is not evidence of profit.", {})]],
     size=16, anchor=MSO_ANCHOR.MIDDLE)

# 9. Progress -----------------------------------------------------------------------------------
s = new_slide("Progress is stated as facts we have verified. The four tiles are test results from our build log. "
              "The right column is deliberately honest: real verified MCX data has not been loaded yet, so calibration and real cost evidence are still open.")
header(s, "Current progress", "What works today, and what does not yet")
for i, (num, cap) in enumerate([("165", "backend tests passing"), ("17", "browser check groups passing: 10 Alerts, 7 Monitor"), ("2", "screens: Monitor and Alerts"), ("1", "evaluated model: opportunity-v1")]):
    x = 0.6 + i * 4.75
    box(s, x, 2.55, 4.55, 1.75, fill=INK)
    text(s, x + 0.15, 2.6, 4.2, 0.95, num, size=44, bold=True, color="F1D58C", font=HEAD)
    text(s, x + 0.15, 3.5, 4.2, 0.7, cap, size=15, color=WHITE)
done = ["Monitor with exact-expiry watchlist and freshness", "Versioned specs and point-in-time storage", "Deterministic model with walk-forward evaluation",
        "In-app paper alerts: dedup, cooldown, expiry, outcome history", "Real-data failures stay failures, with no synthetic fallback"]
todo = ["Load verified real MCX specifications and prices", "Evaluate across several expiries and market regimes", "Calibrate probabilities, only if evidence supports it",
        "Measure real costs and liquidity; add scheduled scans"]
text(s, 0.6, 4.65, 9, 0.5, "Built and verified", size=20, bold=True, color=GREEN)
text(s, 10.3, 4.65, 9, 0.5, "Not done yet", size=20, bold=True, color=RED)
for i, d in enumerate(done):
    y = 5.3 + i * 0.95
    label(s, 0.6, y + 0.1, 0.5, 0.5, GREEN, "✓", size=16, shape=MSO_SHAPE.OVAL)
    text(s, 1.3, y, 8.5, 0.75, d, size=16, anchor=MSO_ANCHOR.MIDDLE)
for i, d in enumerate(todo):
    y = 5.3 + i * 0.95
    box(s, 10.3, y + 0.1, 0.5, 0.5, fill=WHITE, line=RED, shape=MSO_SHAPE.OVAL, lw=2.0)
    text(s, 11.0, y, 8.4, 0.75, d, size=16, anchor=MSO_ANCHOR.MIDDLE)

# 10. Roadmap + close ---------------------------------------------------------------------------
s = new_slide("Roadmap follows the evidence gates, not dates. Users: traders and analysts first, then brokerages, then education. "
              "Close by repeating the guardrails and thank the judges.")
header(s, "Future scope", "Where this goes next")
box(s, 1.2, 4.1, 17.6, 0.12, fill=LINE, radius=0.0)
road = [("Now", "Synthetic prototype: Monitor, Alerts, evaluation harness", INK), ("Next", "Verified real MCX specs and prices through the importer", BLUE),
        ("Then", "Multi-expiry evaluation. Calibrate probabilities if evidence allows", BLUE), ("Later", "Scheduled scans, exportable reports, broker integrations", SLATE)]
for i, (when, what, color) in enumerate(road):
    x = 0.9 + i * 4.7
    badge(s, x + 1.7, 3.88, i + 1, d=0.56, fill=color)
    label(s, x, 2.6, 4.2, 0.6, color, when, size=18)
    text(s, x, 4.75, 4.2, 1.5, what, size=16, color=SLATE, align=CENTER)
text(s, 0.6, 6.5, 12, 0.5, "Who it is for", size=20, bold=True)
for i, who in enumerate(["Commodity traders and analysts", "Brokerages and fintech apps", "Finance students and educators"]):
    label(s, 0.6 + i * 6.35, 7.15, 6.1, 0.8, PANEL, who, size=17, color=INK, bold=True, line=LINE)
box(s, 0.6, 8.5, 18.8, 2.05, fill=INK)
text(s, 0.9, 8.6, 12, 0.9, "Thank you", size=36, bold=True, color="F1D58C", font=HEAD)
text(s, 0.9, 9.5, 17.5, 0.9, "Team ERROR 404  ·  No guaranteed arbitrage. No future data. No made-up data. No trade execution.", size=17, color=WHITE)

assert len(prs.slides) <= 10, "slide limit is 10"
prs.save(str(output))
print(f"saved {output} with {len(prs.slides)} slides")
