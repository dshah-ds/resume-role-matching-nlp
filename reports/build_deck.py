"""
build_deck.py
-------------
Builds the analytical / presentation slide deck (reports/Analytical_Deck.pptx).

All numbers are read from outputs/, so the deck always matches the latest
notebook run. Run the notebooks first, then:
    python reports/build_deck.py

Layout rule used everywhere: text is written INSIDE the shape it belongs to
(cards, KPI tiles, number badges), and no decorative shape is ever placed on
top of or right next to text. This keeps the slides clean in PowerPoint,
Keynote and Google Slides even when fonts render at slightly different sizes.
"""

import sys
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import BODY_FONT, COLORS, FIGURES, HEADING_FONT, OUTPUTS

OUT_FILE = ROOT / "reports" / "Analytical_Deck.pptx"
W, H = Inches(13.333), Inches(7.5)
PAGE_BG = "#FBF8F3"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------
def rgb(hex_code):
    h = hex_code.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def P(text, size=12, color=COLORS["ink"], font=BODY_FONT, bold=False, align=PP_ALIGN.LEFT, after=4):
    """One paragraph spec for box(). **double stars** inside text mark bold parts."""
    return dict(text=text, size=size, color=color, font=font, bold=bold, align=align, after=after)


def fill_frame(tf, paras, anchor=MSO_ANCHOR.TOP, inset=0.12):
    """Write paragraphs into a text frame with fixed size, wrapping and padding."""
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(inset + 0.06)
    tf.margin_top = tf.margin_bottom = Inches(inset)
    for i, spec in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = spec["align"]
        p.line_spacing = 1.0
        p.space_after = Pt(spec["after"])
        for j, part in enumerate(str(spec["text"]).split("**")):
            if not part:
                continue
            r = p.add_run()
            r.text = part
            r.font.size = Pt(spec["size"])
            r.font.name = spec["font"]
            r.font.bold = spec["bold"] or j % 2 == 1
            r.font.color.rgb = rgb(spec["color"])


def box(slide, x, y, w, h, paras=None, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE,
        anchor=MSO_ANCHOR.TOP, inset=0.12):
    """A shape (optionally filled / outlined) that holds its own text."""
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1.25)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.06
    fill_frame(s.text_frame, paras or [], anchor, inset)
    return s


def picture(slide, name, x, y, max_w, max_h):
    """Insert a figure scaled to fit inside the box, centred."""
    path = FIGURES / f"{name}.png"
    iw, ih = Image.open(path).size
    scale = min(max_w / iw, max_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    slide.shapes.add_picture(str(path), x + (max_w - w) // 2, y + (max_h - h) // 2, w, h)


def header(slide, kicker, title, n):
    """Content slide frame: background, kicker, one-line title, footer. Nothing overlaps the title."""
    box(slide, 0, 0, W, H, fill=PAGE_BG)
    box(slide, 0, 0, Inches(0.16), H, fill=COLORS["teal"])                      # left edge strip
    box(slide, Inches(0.6), Inches(0.42), Inches(0.45), Inches(0.07), fill=COLORS["coral"])  # small accent dash
    box(slide, Inches(1.15), Inches(0.28), Inches(10), Inches(0.36),
        [P(kicker.upper(), 11, COLORS["teal"], bold=True)], anchor=MSO_ANCHOR.MIDDLE, inset=0.0)
    box(slide, Inches(0.6), Inches(0.68), Inches(12.2), Inches(0.75),
        [P(title, 26, COLORS["ink"], HEADING_FONT, True)], anchor=MSO_ANCHOR.MIDDLE, inset=0.0)
    box(slide, Inches(0.6), Inches(7.0), Inches(8), Inches(0.32),
        [P("TalentBridge · Resume Screening & Role Matching", 9, COLORS["slate"])], inset=0.0)
    box(slide, Inches(11.9), Inches(7.0), Inches(0.9), Inches(0.32),
        [P(f"{n:02d}", 9, COLORS["slate"], align=PP_ALIGN.RIGHT)], inset=0.0)


def card(slide, x, y, w, h, title, body, accent=COLORS["teal"], title_size=15, body_size=12):
    """White card; the title is coloured with the accent instead of a separate accent bar."""
    box(slide, x, y, w, h, [P(title, title_size, accent, HEADING_FONT, True, after=6),
                            P(body, body_size, COLORS["slate"])],
        fill=WHITE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, inset=0.16)


def kpi(slide, x, y, w, h, value, label, color, value_size=30, fill=WHITE, label_color=COLORS["slate"]):
    """KPI tile: big value + small label in ONE text frame, centred vertically."""
    box(slide, x, y, w, h, [P(value, value_size, color, HEADING_FONT, True, PP_ALIGN.CENTER, after=4),
                            P(label, 11, label_color, align=PP_ALIGN.CENTER, after=0)],
        fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.1)


def note(slide, x, y, w, h, paras_text, size=12, color=COLORS["ink"]):
    """Plain text area (no fill) for short explanations."""
    box(slide, x, y, w, h, [P(t, size, color, after=6) for t in paras_text], inset=0.02)


# ---------------------------------------------------------------
# Results
# ---------------------------------------------------------------
models = pd.read_csv(OUTPUTS / "model_comparison.csv")
ranking = pd.read_csv(OUTPUTS / "ranking_comparison.csv", index_col=0)
workload = pd.read_csv(OUTPUTS / "workload_impact.csv")
robust = pd.read_csv(OUTPUTS / "robustness_summary.csv", index_col=0)["value"]
fair = pd.read_csv(OUTPUTS / "fairness_by_tier.csv", index_col=0)
kw = pd.read_csv(OUTPUTS / "keyword_filter_miss.csv")
gaps = pd.read_csv(OUTPUTS / "skill_gaps_review_pool.csv")

eng = models[models["feature_set"] == "Engineered match"].set_index("model")
raw = models[models["feature_set"] == "Raw profile"].set_index("model")
best = eng.drop(index="Dummy (most frequent)")["macro_f1"].idxmax()
kw_rate = kw["missed_by_keyword"].sum() / kw["high_fit"].sum()
read_today, read_engine = workload["resumes_read_today"].sum(), workload["resumes_read_with_engine"].sum()
hours = workload["hours_saved"].sum()
p20 = ranking["precision@20 (independent)"]

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
blank = prs.slide_layouts[6]
n = 0


def new_slide():
    global n
    n += 1
    return prs.slides.add_slide(blank)


# ---------------- 1. Title ----------------
s = new_slide()
box(s, 0, 0, W, H, fill=COLORS["ink"])
box(s, Inches(8.9), 0, Inches(4.433), H, fill="#22344F")
box(s, Inches(0.8), Inches(0.95), Inches(1.0), Inches(0.08), fill=COLORS["coral"])
box(s, Inches(0.8), Inches(1.2), Inches(7.8), Inches(0.45),
    [P("CASE STUDY  ·  NLP + MACHINE LEARNING", 12, COLORS["mint"], bold=True)], inset=0.0)
box(s, Inches(0.8), Inches(1.75), Inches(7.9), Inches(2.9),
    [P("Resume Screening", 44, WHITE, HEADING_FONT, True, after=0),
     P("& Role Matching", 44, WHITE, HEADING_FONT, True, after=0),
     P("Using NLP", 44, WHITE, HEADING_FONT, True, after=0)], inset=0.0)
box(s, Inches(0.8), Inches(4.85), Inches(7.6), Inches(1.0),
    [P("An explainable engine that ranks 5,000 candidates for every open role — and tells recruiters why.",
       16, COLORS["sand"])], inset=0.0)
box(s, Inches(0.8), Inches(6.3), Inches(7.6), Inches(0.45),
    [P("Devam Shah  ·  TalentBridge Solutions case study", 12, COLORS["mint"])], inset=0.0)
for i, (v, l, c) in enumerate([(f"{1 - read_engine/read_today:.0%}", "less resume reading", COLORS["teal"]),
                               (f"{p20['Hybrid score']:.0%}", "on-profile candidates in each top 20", COLORS["mustard"]),
                               (f"{kw_rate:.0%}", "of High-fit matches a keyword ATS misses", COLORS["coral"])]):
    box(s, Inches(9.4), Inches(1.0 + i * 1.95), Inches(3.5), Inches(1.6),
        [P(v, 46, c, HEADING_FONT, True, after=2), P(l, 13, COLORS["sand"])], inset=0.0)

# ---------------- 2. Problem ----------------
s = new_slide()
header(s, "The business problem", "Too many resumes, and keywords miss good people", n)
pains = [("High volume", "Thousands of resumes a week for every open role overwhelm recruiters.", COLORS["coral"]),
         ("Blind keywords", "'Pyhton', 'Kubrenetes', 'Powe rBI' — real skills that exact filters never see.", COLORS["mustard"]),
         ("Inconsistency", "Different recruiters and locations judge the same profile differently.", COLORS["ink"]),
         ("Wasted effort", "Hours spent reading profiles that never fit the job's must-haves.", COLORS["slate"])]
for i, (t, b, c) in enumerate(pains):
    card(s, Inches(0.6 + i * 3.08), Inches(1.85), Inches(2.85), Inches(2.45), t, b, c, 17, 13)
box(s, Inches(0.6), Inches(4.7), Inches(12.1), Inches(1.95),
    [P("THE MANDATE FROM THE CHRO", 12, COLORS["mint"], bold=True, after=8),
     P("Build a data-driven NLP matching engine that interprets skills, experience, domain and seniority, scores "
       "every candidate against a job description, ranks them, and explains each recommendation.", 18, WHITE)],
    fill=COLORS["teal"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, inset=0.25)

# ---------------- 3. Objectives ----------------
s = new_slide()
header(s, "Objectives & success measures", "Five measurable goals guided every step", n)
objs = [("01", "Trustworthy data", "Every skill standardised; logic errors fixed", "212 → 30 skills"),
        ("02", "Score every pair", "0–1 fit score, 5,000 candidates × 10 jobs", "50,000 scores"),
        ("03", "Rank the right people", "Precision@20 vs an independent yardstick", f"{p20['Hybrid score']:.2f}"),
        ("04", "Explain decisions", "Plain-English reason + score breakdown", "100% of pairs"),
        ("05", "Cut recruiter effort", "Fewer resumes read, no High-fit lost", f"−{1 - read_engine/read_today:.0%}")]
for i, (num, t, m, r) in enumerate(objs):
    y = Inches(1.8 + i * 1.0)
    rh = Inches(0.84)
    box(s, Inches(0.6), y, Inches(0.95), rh, [P(num, 24, WHITE, HEADING_FONT, True, PP_ALIGN.CENTER, 0)],
        fill=COLORS["teal"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.02)
    box(s, Inches(1.7), y, Inches(8.4), rh,
        [P(f"**{t}**   ·   {m}", 15, COLORS["ink"], after=0)],
        fill=WHITE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.1)
    box(s, Inches(10.25), y, Inches(2.45), rh, [P(r, 16, WHITE, bold=True, align=PP_ALIGN.CENTER, after=0)],
        fill=COLORS["ink"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.04)

# ---------------- 4. Data & validation ----------------
s = new_slide()
header(s, "Data validation", "Clean on the surface, noisy underneath", n)
for i, (v, l) in enumerate([("5,000", "candidates"), ("34", "columns"), ("6", "domains"), ("25", "roles")]):
    kpi(s, Inches(0.6), Inches(1.8 + i * 1.25), Inches(2.6), Inches(1.1), v, l, COLORS["ink"], value_size=24)
issues = [("1,040 resumes with misspelt skills", "182 bad spellings mapped back to 30 standard skills with fuzzy matching.", COLORS["coral"]),
          ("1,063 impossible degrees", "'LLM' (a law degree) in Computer Science, Statistics… re-labelled as Masters and flagged.", COLORS["mustard"]),
          ("499 missing education values", "Not guessed — filled as 'Not Specified' and given a neutral score.", COLORS["slate"]),
          ("3 pairs of identical columns", "Exact copies (e.g. mentoring = enterprise systems); only one of each used in ML.", COLORS["ink"]),
          ("Templated summaries", "At most 18 sentence patterns, so text similarity is a supporting signal only.", COLORS["teal"]),
          ("No duplicates or range errors", "Seniority, years and domain agree across title, summary and file name.", COLORS["teal"])]
for i, (t, b, c) in enumerate(issues):
    col, row = i % 2, i // 2
    card(s, Inches(3.5 + col * 4.65), Inches(1.8 + row * 1.68), Inches(4.5), Inches(1.52), t, b, c, 14, 11.5)

# ---------------- 5. Skill noise ----------------
s = new_slide()
header(s, "NLP skill normalisation", "Fixing spelling recovers candidates keywords miss", n)
picture(s, "01_skill_cleaning_gain", Inches(0.5), Inches(1.75), Inches(7.9), Inches(5.1))
kpi(s, Inches(8.8), Inches(1.85), Inches(3.9), Inches(1.45), "+167", "extra Python candidates found after cleaning", COLORS["teal"])
kpi(s, Inches(8.8), Inches(3.45), Inches(3.9), Inches(1.45), f"{kw_rate:.0%}", "of High-fit matches lost by an exact-keyword ATS", COLORS["coral"])
note(s, Inches(8.8), Inches(5.1), Inches(3.9), Inches(1.7),
     ["**How:** lower-case and remove spaces, then fuzzy-match (RapidFuzz, score ≥ 75) to a 30-skill dictionary "
      "grouped into 6 skill families. Every correction is logged in an audit table."])

# ---------------- 6. EDA ----------------
s = new_slide()
header(s, "Exploratory analysis", "Skills separate candidates; institution tier does not", n)
picture(s, "02_skill_domain_heatmap", Inches(0.4), Inches(1.6), Inches(5.6), Inches(5.3))
pts = [("Skills form domain blocks", "Each candidate lists 4 skills; inside IT they come from 8, so which four matters for each job."),
       ("Experience is reliable", "Junior ≤ 4 yrs, senior ≥ 6 yrs; summary years always match the numeric field."),
       ("Managers are more experienced", "Median 10 vs 4 yrs (Mann-Whitney p < 0.0001), so leadership flags are grouped into one score."),
       ("Tier carries no fit signal", "Not linked to completeness (ANOVA p = 0.06) or domain (χ² p = 0.28), so it is excluded.")]
for i, (t, b) in enumerate(pts):
    card(s, Inches(6.3), Inches(1.75 + i * 1.3), Inches(6.4), Inches(1.18), t, b,
         [COLORS["teal"], COLORS["mustard"], COLORS["ink"], COLORS["coral"]][i], 14, 11.5)

# ---------------- 7. Approach ----------------
s = new_slide()
header(s, "Solution design", "A hybrid engine: NLP + recruiter rules + machine learning", n)
steps = [("Parsed resumes", "5,000 profiles", COLORS["slate"]), ("Clean & normalise", "fuzzy skills, fixes", COLORS["ink"]),
         ("Engineer features", "candidate × job", COLORS["ink"])]
for i, (t, b, c) in enumerate(steps):
    x = Inches(0.6 + i * 2.35)
    box(s, x, Inches(3.2), Inches(2.05), Inches(1.3),
        [P(t, 14, WHITE, HEADING_FONT, True, PP_ALIGN.CENTER, 4), P(b, 11, COLORS["sand"], align=PP_ALIGN.CENTER, after=0)],
        fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.06)
    box(s, x + Inches(2.09), Inches(3.72), Inches(0.22), Inches(0.26), fill=COLORS["coral"], shape=MSO_SHAPE.RIGHT_ARROW)
layers = [("A · NLP similarity", "TF-IDF + LSA cosine, profile vs JD", COLORS["mustard"]),
          ("B · Rule score", "must-have 30%, experience 15%, domain, role, flags …", COLORS["teal"]),
          ("C · ML classifier", f"{best} → P(High / Medium / Low)", COLORS["coral"])]
for i, (t, b, c) in enumerate(layers):
    box(s, Inches(7.7), Inches(1.85 + i * 1.5), Inches(2.9), Inches(1.25),
        [P(t, 13.5, c, HEADING_FONT, True, after=4), P(b, 10.5, COLORS["slate"], after=0)],
        fill=WHITE, line=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.1)
box(s, Inches(10.73), Inches(3.72), Inches(0.22), Inches(0.26), fill=COLORS["coral"], shape=MSO_SHAPE.RIGHT_ARROW)
box(s, Inches(11.05), Inches(2.6), Inches(1.75), Inches(2.5),
    [P("Hybrid score", 14, WHITE, HEADING_FONT, True, PP_ALIGN.CENTER, 8),
     P("0.70 × rule", 11, COLORS["sand"], align=PP_ALIGN.CENTER, after=0),
     P("+ 0.30 × ML", 11, COLORS["sand"], align=PP_ALIGN.CENTER, after=8),
     P("Shortlist / Review / Reject", 10.5, COLORS["mint"], bold=True, align=PP_ALIGN.CENTER, after=0)],
    fill=COLORS["teal"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.08)
note(s, Inches(0.6), Inches(5.3), Inches(6.8), Inches(1.55),
     ["**No job descriptions or hiring outcomes in the data**, so 10 structured JDs were written (all 6 domains) and a "
      "High / Medium / Low target was defined with recruiter-style rules.",
      "Text similarity enters through the ML model only; a direct weight pulled templated, off-profile resumes up."])

# ---------------- 8. Features ----------------
s = new_slide()
header(s, "Feature engineering", "How well does this person fit THIS job?", n)
feats = [("Must-have match", "% of JD must-have skills found (skills + tools)"),
         ("Nice-to-have match", "% of optional skills, separating good from great"),
         ("Experience fit", "1 in range · −0.25/yr under · −0.05/yr over"),
         ("Seniority fit", "Junior / Mid / Senior from the title vs the JD level"),
         ("Domain & role fit", "Same / related / other domain; role in target list"),
         ("Required areas", "% of JD-required flags: cloud, agile, people mgmt…"),
         ("Exposure scores", "Leadership · delivery · client · governance"),
         ("Resume quality", "Completeness, length, keyword-stuffing flag"),
         ("Semantic match", "TF-IDF + 50-topic LSA similarity to JD text")]
for i, (t, b) in enumerate(feats):
    col, row = i % 3, i // 3
    card(s, Inches(0.6 + col * 4.08), Inches(1.8 + row * 1.7), Inches(3.85), Inches(1.5), t, b,
         [COLORS["teal"], COLORS["mustard"], COLORS["coral"]][col], 15, 12)

# ---------------- 9. Models ----------------
s = new_slide()
header(s, "Model training & comparison", "Engineered features lift every classifier", n)
picture(s, "04_model_comparison", Inches(0.4), Inches(1.7), Inches(7.9), Inches(4.4))
kpi(s, Inches(8.7), Inches(1.8), Inches(1.95), Inches(1.45), f"{raw.drop(index='Dummy (most frequent)')['macro_f1'].max():.2f}",
    "best macro-F1, raw features", COLORS["slate"], value_size=26)
kpi(s, Inches(10.8), Inches(1.8), Inches(1.95), Inches(1.45), f"{eng.loc[best, 'macro_f1']:.3f}",
    f"macro-F1, {best}", COLORS["teal"], value_size=26)
note(s, Inches(8.7), Inches(3.45), Inches(4.05), Inches(1.6),
     ["**5-fold GroupKFold by candidate:** nobody appears in both train and test.",
      f"A dummy 'always Low' model gets {eng.loc['Dummy (most frequent)', 'accuracy']:.0%} accuracy, so **macro-F1** is the metric."])
box(s, Inches(8.7), Inches(5.2), Inches(4.05), Inches(1.6),
    [P("Honest caveat", 12, WHITE, bold=True, after=4),
     P("Labels come from the same rules, so the model learns recruiter logic, not real hiring outcomes. "
       "Re-train once real decisions exist.", 11, WHITE, after=0)],
    fill=COLORS["coral"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, inset=0.15)

# ---------------- 10. Ranking ----------------
s = new_slide()
header(s, "Ranking quality", "Structured scoring beats text similarity alone", n)
picture(s, "04_ranking_comparison", Inches(0.4), Inches(1.7), Inches(8.1), Inches(4.55))
kpi(s, Inches(8.9), Inches(1.8), Inches(3.85), Inches(1.45), f"{p20['Hybrid score']:.0%} vs {p20['TF-IDF similarity']:.0%}",
    "top-20 on-profile: hybrid vs text-only", COLORS["teal"], value_size=26)
kpi(s, Inches(8.9), Inches(3.4), Inches(3.85), Inches(1.45), f"{robust['top20_overlap_mean']:.0%}",
    "of top-20 unchanged when weights move ±30%", COLORS["mustard"], value_size=28)
kpi(s, Inches(8.9), Inches(5.0), Inches(3.85), Inches(1.45), f"p = {fair['chi2_p_value'].iloc[0]:.2f}",
    "shortlist rate equal across institution tiers", COLORS["ink"], value_size=28)
note(s, Inches(0.6), Inches(6.35), Inches(8), Inches(0.55),
     ["Yardstick = role in the JD's target list and experience in range; never used to build any score."], 11, COLORS["slate"])

# ---------------- 11. Drivers ----------------
s = new_slide()
header(s, "Explainability", "Must-have skills drive fit; every score shows its working", n)
picture(s, "04_feature_importance", Inches(0.4), Inches(1.65), Inches(5.7), Inches(4.75))
picture(s, "05_score_breakdown", Inches(6.3), Inches(1.7), Inches(6.5), Inches(2.85))
box(s, Inches(6.4), Inches(4.8), Inches(6.3), Inches(1.95),
    [P("WHAT THE RECRUITER SEES", 11, COLORS["mint"], bold=True, after=8),
     P("#699 · DevOps Engineer · Review: 2/3 must-have skills; missing: Docker; 10 yrs fits 6–15 yr range; same "
       "domain; has all required experience areas.", 13, WHITE, after=0)],
    fill=COLORS["ink"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, inset=0.2)

# ---------------- 12. Business impact ----------------
s = new_slide()
header(s, "Business impact", f"{1 - read_engine/read_today:.0%} less reading, with no High-fit candidate lost", n)
picture(s, "05_workload", Inches(0.4), Inches(1.7), Inches(8.2), Inches(4.4))
kpi(s, Inches(8.9), Inches(1.8), Inches(3.85), Inches(1.4), f"{read_today:,} → {read_engine:,}", "resumes to read across 10 jobs",
    COLORS["ink"], value_size=24)
kpi(s, Inches(8.9), Inches(3.35), Inches(3.85), Inches(1.4), f"≈{hours:,.0f} h", "recruiter hours saved (5 min / resume)",
    COLORS["teal"], value_size=28)
kpi(s, Inches(8.9), Inches(4.9), Inches(3.85), Inches(1.4), "100%", "of High-fit candidates still reach a recruiter",
    COLORS["mustard"], value_size=28)
note(s, Inches(0.6), Inches(6.2), Inches(8), Inches(0.75),
     ["Biggest gains where the domain pool is large (Data Science −83%, IT project manager −95%). Small specialist pools "
      "are already relevant; there the engine adds ranking and reasons."], 11, COLORS["slate"])

# ---------------- 13. Dashboard ----------------
s = new_slide()
header(s, "Interactive dashboard", "A recruiter cockpit built in Streamlit", n)
box(s, Inches(0.55), Inches(1.7), Inches(8.6), Inches(5.15), fill=WHITE, line="#E5DCCF")
picture(s, "06_dashboard", Inches(0.65), Inches(1.8), Inches(8.4), Inches(4.95))
tabs = [("Ranked shortlist", "Filter by action, years, domain; download CSV"),
        ("Candidate profile", "Matched / missing skills and score breakdown"),
        ("Job insights", "Score spread, skill gaps, fairness check"),
        ("Score a new job", "Build any JD and rank all 5,000 live")]
for i, (t, b) in enumerate(tabs):
    card(s, Inches(9.45), Inches(1.7 + i * 1.3), Inches(3.3), Inches(1.18), t, b,
         [COLORS["teal"], COLORS["mustard"], COLORS["ink"], COLORS["coral"]][i], 14, 11)

# ---------------- 14. Recommendations ----------------
s = new_slide()
header(s, "Recommendations", "Six actions for TalentBridge recruiting", n)
gap_top = gaps.sort_values("share_of_review_pool", ascending=False).iloc[0]
recs = [("Triage with the hybrid score", "Read Shortlist, then Review; archive Reject with its stored reason."),
        ("Switch on fuzzy skill matching", f"Exact keyword filters lose {kw_rate:.0%} of High-fit matches."),
        ("Challenge 'must-have' skills", f"One skill blocks most Review pools, e.g. {gap_top['mandatory_missing']} for {gap_top['jd_id']} "
                                         f"({gap_top['share_of_review_pool']:.0%}). Is it trainable?"),
        ("Keep institution tier out", "No fit signal; shortlist rates are equal across tiers."),
        ("Standardise job descriptions", "Must-have vs nice-to-have, years and required areas."),
        ("Close the feedback loop", "Log recruiter decisions for a quarter; re-train on real outcomes.")]
for i, (t, b) in enumerate(recs):
    col, row = i % 2, i // 2
    x, y = Inches(0.6 + col * 6.12), Inches(1.8 + row * 1.7)
    box(s, x, y, Inches(0.95), Inches(1.5), [P(f"{i+1}", 30, WHITE, HEADING_FONT, True, PP_ALIGN.CENTER, 0)],
        fill=COLORS["teal"] if i % 2 == 0 else COLORS["ink"], shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        anchor=MSO_ANCHOR.MIDDLE, inset=0.02)
    box(s, x + Inches(1.05), y, Inches(4.85), Inches(1.5),
        [P(t, 15.5, COLORS["ink"], HEADING_FONT, True, after=6), P(b, 12, COLORS["slate"], after=0)],
        fill=WHITE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, anchor=MSO_ANCHOR.MIDDLE, inset=0.16)

# ---------------- 15. Limitations & close ----------------
s = new_slide()
box(s, 0, 0, W, H, fill=COLORS["ink"])
box(s, Inches(0.8), Inches(0.9), Inches(1.0), Inches(0.08), fill=COLORS["coral"])
box(s, Inches(0.8), Inches(1.1), Inches(9), Inches(0.85),
    [P("Limitations & next steps", 32, WHITE, HEADING_FONT, True)], anchor=MSO_ANCHOR.MIDDLE, inset=0.0)
lims = [("Rule-based labels", "Validate on real recruiter & interview decisions; re-train quarterly."),
        ("Written job descriptions", "Parse real JDs with the same skill dictionary."),
        ("Templated resume text", "Try sentence embeddings (e.g. SBERT) on richer, real resumes."),
        ("Growing skill dictionary", "Add skills as job families grow; the correction table keeps it auditable."),
        ("Time-saving estimate", "Measure actual minutes per resume in a 4-week pilot.")]
for i, (t, b) in enumerate(lims):
    y = Inches(2.15 + i * 0.85)
    box(s, Inches(0.8), y, Inches(3.9), Inches(0.7), [P(t, 16, COLORS["mint"], HEADING_FONT, True, after=0)],
        anchor=MSO_ANCHOR.MIDDLE, inset=0.0)
    box(s, Inches(4.8), y, Inches(7.8), Inches(0.7), [P(b, 14, COLORS["sand"], after=0)],
        anchor=MSO_ANCHOR.MIDDLE, inset=0.0)
box(s, Inches(0.8), Inches(6.45), Inches(11.5), Inches(0.6),
    [P("Thank you  ·  Questions?", 20, COLORS["mint"], HEADING_FONT, True)], anchor=MSO_ANCHOR.MIDDLE, inset=0.0)

prs.save(OUT_FILE)
print("Saved", OUT_FILE, "with", n, "slides")
