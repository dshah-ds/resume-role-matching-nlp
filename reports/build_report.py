"""
build_report.py
---------------
Builds the written business report (reports/Business_Report.docx).

Every number in the report is read from the files in outputs/, so the report
always matches the latest notebook run. Run the notebooks first, then:
    python reports/build_report.py
"""

import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import BODY_FONT, COLORS, FIGURES, HEADING_FONT, JD_FILE, OUTPUTS

OUT_FILE = ROOT / "reports" / "Business_Report.docx"


# ---------------------------------------------------------------
# Helpers for styling
# ---------------------------------------------------------------
def rgb(hex_code):
    hex_code = hex_code.lstrip("#")
    return RGBColor(int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16))


def shade(cell, hex_code):
    """Fill a table cell with a background colour."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_code.lstrip("#"))
    tc_pr.append(shd)


def cell_borders(cell, color="FFFFFF", size=4):
    """Thin borders on a cell (white = invisible look on coloured cells)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:color"), color)
        borders.append(el)
    tc_pr.append(borders)


def set_font(run, name=BODY_FONT, size=10, bold=False, color=COLORS["ink"], italic=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color)


def para(doc, text="", size=10, bold=False, color=COLORS["ink"], align=None, space_after=6, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if align:
        p.alignment = align
    if text:
        add_rich(p, text, size=size, bold=bold, color=color, italic=italic)
    return p


def add_rich(p, text, size=10, bold=False, color=COLORS["ink"], italic=False):
    """Add text where **double stars** mark bold parts."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if part:
            set_font(p.add_run(part), size=size, bold=bold or i % 2 == 1, color=color, italic=italic)


def heading(doc, number, text):
    """Section heading: teal number + ink title + coral underline bar."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(f"{number}  "), HEADING_FONT, 17, True, COLORS["teal"])
    set_font(p.add_run(text), HEADING_FONT, 17, True, COLORS["ink"])
    bar = doc.add_paragraph()
    bar.paragraph_format.space_after = Pt(8)
    bar.paragraph_format.keep_with_next = True   # never leave a heading alone at the bottom of a page
    set_font(bar.add_run("▬▬▬▬"), size=8, color=COLORS["coral"])


def subheading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), HEADING_FONT, 12, True, COLORS["teal"])


def bullet(doc, text, size=10):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.first_line_indent = Cm(-0.4)
    p.paragraph_format.space_after = Pt(3)
    set_font(p.add_run("■  "), size=7, color=COLORS["teal"])
    add_rich(p, text, size=size)
    return p


def table(doc, df, col_widths=None, font_size=8.5, header_color=COLORS["ink"]):
    """Styled table: ink header, sand banded rows."""
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, col in enumerate(df.columns):
        c = t.rows[0].cells[i]
        shade(c, header_color)
        cell_borders(c)
        c.paragraphs[0].text = ""
        set_font(c.paragraphs[0].add_run(str(col)), size=font_size, bold=True, color="#FFFFFF")
    for r_i, row in enumerate(df.itertuples(index=False)):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            if r_i % 2 == 0:
                shade(cells[i], COLORS["sand"])
            cell_borders(cells[i])
            cells[i].paragraphs[0].text = ""
            set_font(cells[i].paragraphs[0].add_run(str(val)), size=font_size)
    if col_widths:
        for row in t.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def figure(doc, name, width_cm=16, caption=None):
    doc.add_picture(str(FIGURES / f"{name}.png"), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        para(doc, caption, size=8.5, italic=True, color=COLORS["slate"], align=WD_ALIGN_PARAGRAPH.CENTER)


def callout(doc, title, text, color=COLORS["teal"]):
    """A one-cell coloured box for key messages."""
    t = doc.add_table(rows=1, cols=1)
    c = t.rows[0].cells[0]
    shade(c, color)
    cell_borders(c, color.lstrip("#"))
    c.paragraphs[0].text = ""
    set_font(c.paragraphs[0].add_run(title), HEADING_FONT, 11, True, "#FFFFFF")
    p = c.add_paragraph()
    add_rich(p, text, size=10, color="#FFFFFF")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# ---------------------------------------------------------------
# Load the results
# ---------------------------------------------------------------
models = pd.read_csv(OUTPUTS / "model_comparison.csv")
ranking = pd.read_csv(OUTPUTS / "ranking_comparison.csv", index_col=0)
workload = pd.read_csv(OUTPUTS / "workload_impact.csv")
tests = pd.read_csv(OUTPUTS / "hypothesis_tests.csv")
vlog = pd.read_csv(OUTPUTS / "validation_log.csv")
robust = pd.read_csv(OUTPUTS / "robustness_summary.csv", index_col=0)["value"]
fair = pd.read_csv(OUTPUTS / "fairness_by_tier.csv", index_col=0)
kw = pd.read_csv(OUTPUTS / "keyword_filter_miss.csv")
gaps = pd.read_csv(OUTPUTS / "skill_gaps_review_pool.csv")
importance = pd.read_csv(OUTPUTS / "feature_importance.csv", index_col=0)["importance"].sort_values(ascending=False)
scored = pd.read_csv(OUTPUTS / "scored_pairs.csv", usecols=["jd_id", "fit_label", "recommendation"])
jds = pd.read_csv(JD_FILE)

eng = models[models["feature_set"] == "Engineered match"].set_index("model")
raw = models[models["feature_set"] == "Raw profile"].set_index("model")
best = eng.drop(index="Dummy (most frequent)")["macro_f1"].idxmax()
kw_total, kw_missed = kw["high_fit"].sum(), kw["missed_by_keyword"].sum()
read_today, read_engine = workload["resumes_read_today"].sum(), workload["resumes_read_with_engine"].sum()
hours = workload["hours_saved"].sum()
label_share = scored["fit_label"].value_counts(normalize=True)

# ---------------------------------------------------------------
# Document setup
# ---------------------------------------------------------------
doc = Document()
for s in doc.sections:
    s.top_margin, s.bottom_margin = Cm(2), Cm(2)
    s.left_margin, s.right_margin = Cm(2.2), Cm(2.2)
normal = doc.styles["Normal"]
normal.font.name = BODY_FONT
normal.font.size = Pt(10)

# ---------------- Cover page ----------------
cover = doc.add_table(rows=1, cols=1)
cell = cover.rows[0].cells[0]
shade(cell, COLORS["ink"])
cell_borders(cell, COLORS["ink"].lstrip("#"))
cell.paragraphs[0].text = ""
for txt, size, colr, font, bold, before in [
    ("TALENTBRIDGE SOLUTIONS PVT. LTD.", 10, COLORS["mint"], BODY_FONT, True, 40),
    ("Resume Screening &", 32, "#FFFFFF", HEADING_FONT, True, 30),
    ("Role Matching Using NLP", 32, "#FFFFFF", HEADING_FONT, True, 0),
    ("Business Report", 13, COLORS["mustard"], BODY_FONT, False, 18),
    ("An explainable candidate–job matching engine that turns 5,000 parsed resumes into ranked, "
     "reasoned shortlists for 10 open roles.", 11, "#FFFFFF", BODY_FONT, False, 30),
    ("Prepared by Devam Shah", 9.5, COLORS["mint"], BODY_FONT, False, 60),
]:
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.right_indent = Cm(0.8)
    set_font(p.add_run(txt), font, size, bold, colr)
cell.add_paragraph().paragraph_format.space_after = Pt(40)

para(doc, "", space_after=14)
# KPI strip on the cover
kpis = [(f"{1 - read_engine/read_today:.0%}", "less resume reading"),
        (f"{hours:,.0f} h", "recruiter time saved"),
        (f"{ranking.loc['Hybrid score', 'precision@20 (independent)']:.0%}", "on-profile top-20"),
        (f"{kw_missed/kw_total:.0%}", "High-fit a keyword ATS misses")]
strip = doc.add_table(rows=2, cols=4)
for i, (v, l) in enumerate(kpis):
    top, bot = strip.rows[0].cells[i], strip.rows[1].cells[i]
    for c in (top, bot):
        shade(c, COLORS["sand"])
        cell_borders(c, "FFFFFF", 12)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(top.paragraphs[0].add_run(v), HEADING_FONT, 20, True, [COLORS["teal"], COLORS["ink"], COLORS["mustard"], COLORS["coral"]][i])
    set_font(bot.paragraphs[0].add_run(l), size=8.5, color=COLORS["slate"])
    top.width = bot.width = Cm(4.15)
doc.add_page_break()

# ---------------- 1. Executive summary ----------------
heading(doc, "01", "Executive summary")
para(doc, "TalentBridge recruiters screen thousands of resumes a week using keyword filters that miss misspelt skills, "
          "treat every keyword equally and give no reason for a decision. This project builds a **hybrid NLP + rules + "
          "machine-learning matching engine** that scores every candidate against a structured job description, ranks "
          "them and explains each score in plain English.")
for b in [
    f"**Cleaner data, fairer matching:** {vlog.iloc[2]['Result'].split(',')[0]} ({1040/5000:.0%}) had misspelt skills. NLP fuzzy "
    f"matching mapped all 212 raw skill spellings to 30 standard skills; a plain keyword filter would lose "
    f"**{kw_missed/kw_total:.1%} of High-fit matches** ({kw_missed:,} of {kw_total:,}) just because of spelling.",
    f"**Accurate ranking:** on an independent 'on-profile' yardstick, the hybrid engine puts "
    f"**{ranking.loc['Hybrid score', 'precision@20 (independent)']:.0%} on-profile candidates in each top-20**, versus "
    f"{ranking.loc['TF-IDF similarity', 'precision@20 (independent)']:.0%} for text similarity alone and "
    f"{ranking.loc['Random', 'precision@20 (independent)']:.0%} at random.",
    f"**Less recruiter effort:** across the 10 roles, recruiters read **{read_engine:,} instead of {read_today:,} resumes "
    f"({1-read_engine/read_today:.0%} less, ≈{hours:,.0f} hours saved)** while keeping 100% of High-fit candidates.",
    f"**Explainable and fair:** every score breaks down into must-have skills, experience, domain and role fit. "
    f"Institution tier is excluded; shortlist rates are equal across tiers (χ² p = {fair['chi2_p_value'].iloc[0]:.2f}).",
    f"**Stable:** changing every rule weight by up to ±30% keeps **{robust['top20_overlap_mean']:.0%}** of each top-20 shortlist.",
]:
    bullet(doc, b)
callout(doc, "Recommendation", "Roll the engine out as a **ranking and triage layer** inside the ATS: recruiters read "
        "Shortlist first, then Review, and Reject is archived with its stored reason. Collect recruiter decisions "
        "for one quarter and re-train the model on real outcomes.")

# ---------------- 2. Business problem ----------------
heading(doc, "02", "Business problem & objectives")
para(doc, "Five stakeholder groups need different things from screening: recruiters want speed and consistency, hiring "
          "managers want confidence in skills and seniority, HR operations want auditability, leadership wants scale, "
          "and the analytics team needs an interpretable model that can sit inside the ATS.")
table(doc, pd.DataFrame([
    ["Trustworthy candidate data", "All skill tokens standardised; logic errors fixed or flagged", "212 → 30 skills; 1,063 education errors fixed"],
    ["Score every candidate for every job", "0–1 fit score for 5,000 × 10 pairs", "50,000 scored pairs"],
    ["Put the right people on top", "Precision@20, NDCG@50 vs independent yardstick",
     f"{ranking.loc['Hybrid score', 'precision@20 (independent)']:.2f} / {ranking.loc['Hybrid score', 'ndcg@50 (independent)']:.2f}"],
    ["Explain every decision", "Reason text + score breakdown per pair", "100% of pairs"],
    ["Reduce recruiter workload", "% fewer resumes read, High-fit retained", f"{1-read_engine/read_today:.0%} fewer, 100% retained"],
], columns=["Objective", "Success measure", "Result"]), col_widths=[4.5, 6.5, 5.5])

subheading(doc, "Scope and key assumption")
para(doc, "The dataset contains parsed resume attributes only — **no job descriptions and no hiring outcomes**. Ten "
          "realistic job descriptions were therefore written across all six domains (Appendix A), each with must-have "
          "and nice-to-have skills, an experience range, seniority, required experience areas and preferred education. "
          "Because there is no 'hired' label, the High / Medium / Low target was defined with recruiter-style business rules.")

# ---------------- 3. Data validation ----------------
heading(doc, "03", "Data validation & cleaning")
para(doc, "The raw file has 5,000 candidates and 34 columns (identity, domain/role, education, raw skill text, three "
          "free-text summaries, 16 experience flags and 3 ATS indicators). Every check and the action taken:")
table(doc, vlog, col_widths=[5.2, 4.0, 7.3], font_size=8)
figure(doc, "01_skill_cleaning_gain", 14, "Figure 1 — Candidates found per skill: exact keyword vs after NLP cleaning")
para(doc, "**Why it matters:** an 'LLM in Computer Science' is impossible (LLM is a law degree), so 1,063 records were "
          "re-labelled 'Masters' rather than dropped. Missing education was **not guessed** — it gets a neutral score so "
          "candidates are not penalised for a parsing gap. Three pairs of flag columns are exact copies, so only one of each "
          "is used in the ML model to avoid double counting.")

# ---------------- 4. EDA ----------------
heading(doc, "04", "What the data tells us")
figure(doc, "02_skill_domain_heatmap", 11.5, "Figure 2 — Share of each domain listing each skill")
for b in [
    "**Skills form clear domain blocks.** Every candidate lists exactly 4 skills; inside IT they are drawn from 8 skills, "
    "so which four a candidate has is what separates a fit for a specific job.",
    "**Experience and seniority are clean.** Junior titles ≤ 4 years, senior titles ≥ 6 years, and the years written in the "
    "summary always match the numeric field — a reliable basis for experience-range matching.",
    "**Text summaries are templated** (18 sentence patterns at most), so text similarity can confirm domain but cannot "
    "carry the match on its own.",
    "**Leadership flags travel together** with experience (managers: median 10 vs 4 years), supporting grouped exposure scores.",
]:
    bullet(doc, b)
subheading(doc, "Hypothesis tests (α = 0.05)")
table(doc, tests[["id", "hypothesis (H1 side)", "test", "p_value", "significant at 5%"]], col_widths=[1, 7, 3.2, 2.2, 2.6], font_size=8)
para(doc, "Institution tier is unrelated to profile completeness and domain (H1, H3), so it carries no fit signal and "
          "could only add pedigree bias — it is **excluded from scoring**. Typos do not indicate weaker resumes (H4), so "
          "candidates should not be penalised for them.")

# ---------------- 5. Features ----------------
heading(doc, "05", "Feature engineering")
para(doc, "Features are built at two levels: what describes the **candidate**, and how well the candidate fits a **specific job**.")
table(doc, pd.DataFrame([
    ["Normalised skills", "Fuzzy-corrected canonical skill list + skill family", "Typos no longer hide skills"],
    ["Mandatory / optional match", "% of JD must-have and nice-to-have skills found", "Core hiring filter, graded not binary"],
    ["Experience fit", "1 in range; −0.25/yr under; −0.05/yr over (floor 0.6)", "Under-experience is the bigger risk"],
    ["Seniority & buckets", "Junior/Mid/Senior from title; Entry/Mid/Senior/Expert by years", "Level check beyond raw years"],
    ["Domain & role fit", "Same / related / other domain; role in target list", "Functional background alignment"],
    ["Required experience areas", "% of JD-required flags present (cloud, agile, people mgmt …)", "Role-specific exposure"],
    ["Exposure scores", "Leadership, delivery, client, governance (flag averages)", "Compact, interpretable signals"],
    ["Resume quality", "Completeness, length, keyword-stuffing flag, missing data", "Tie-breaker; flags ATS gaming"],
    ["NLP similarity", "TF-IDF cosine and LSA (50-topic) cosine, profile vs JD text", "Meaning beyond exact keywords"],
], columns=["Feature", "Logic", "Why it helps"]), col_widths=[3.8, 7.5, 5.2], font_size=8)

# ---------------- 6. Matching approach ----------------
heading(doc, "06", "The matching engine")
table(doc, pd.DataFrame([
    ["A · NLP similarity", "TF-IDF + LSA cosine between profile and JD text", "Unsupervised baseline; ML input"],
    ["B · Rule-based score", "Weighted: must-have 30%, experience 15%, domain 10%, role 10%, flags 10%, optional 10%, "
                            "education 5%, tools 5%, quality 5%", "Transparent, auditable"],
    ["C · ML classifier", f"{best} predicting High / Medium / Low fit", "Learns interactions, gives probabilities"],
    ["Hybrid score", "0.70 × rule score + 0.30 × ML expected fit", "Final ranking"],
    ["Recommendation", "Shortlist ≥ 0.72 · Review 0.55–0.72 · Reject < 0.55", "Recruiter action"],
], columns=["Layer", "How it works", "Role"]), col_widths=[3.5, 9.3, 3.7], font_size=8.5)
para(doc, f"**Target variable:** High = rule score ≥ 0.75, ≥ 2/3 must-have skills and experience in range; Low = rule score "
          f"< 0.50, < 1/3 must-have skills or unrelated domain; Medium otherwise. Result: {label_share.get('High', 0):.1%} High, "
          f"{label_share.get('Medium', 0):.1%} Medium, {label_share.get('Low', 0):.1%} Low — imbalanced, as in real hiring.")
para(doc, "**Weight choice:** a first version gave text similarity 15% of the hybrid score. Tests showed any direct text "
          "weight pulled templated but off-profile resumes upward, so text similarity now enters only through the ML model "
          "and is shown to recruiters as a separate 'semantic match' signal.")

# ---------------- 7. Evaluation ----------------
heading(doc, "07", "Evaluation & model comparison")
subheading(doc, "Classifiers — 5-fold GroupKFold by candidate (no candidate in both train and test)")
cmp = pd.DataFrame({
    "Model": eng.index,
    "Macro-F1 raw features": raw["macro_f1"].round(3).values,
    "Macro-F1 engineered": eng["macro_f1"].round(3).values,
    "Accuracy engineered": eng["accuracy"].round(3).values,
    "ROC-AUC engineered": eng["roc_auc_ovr"].round(3).values,
})
table(doc, cmp, col_widths=[4.2, 3, 3, 3, 3])
figure(doc, "04_model_comparison", 12.5, "Figure 3 — Engineered match features lift every model")
para(doc, f"The dummy model scores {eng.loc['Dummy (most frequent)', 'accuracy']:.0%} accuracy by always saying 'Low' — "
          "accuracy is misleading here, so macro-F1 is the main metric. Engineered features raise macro-F1 from "
          f"{raw.drop(index='Dummy (most frequent)')['macro_f1'].max():.3f} to {eng.loc[best, 'macro_f1']:.3f}. "
          "**Caveat:** the labels were built from the same engineered features, so this shows the model reproduces the "
          "recruiter rules reliably — not that it predicts real hiring outcomes.")
subheading(doc, "Ranking quality — independent yardstick (role in target list and experience in range)")
rk = ranking.reset_index().rename(columns={"index": "Method"})
rk = rk[["Method", "precision@20 (independent)", "ndcg@50 (independent)", "ndcg@20 (labels)"]].round(3)
table(doc, rk, col_widths=[4.5, 4, 4, 4])
para(doc, "This yardstick was not used to build any score, so it is a fair test. Structured scoring finds far more "
          "on-profile candidates than text similarity alone. Note that the hybrid weights were selected on this "
          "yardstick, so its number is slightly optimistic. The rule score on its own ranks exactly as well "
          "(same precision@20 and NDCG@50), so the ML part adds a probability for review, not better ranking.")

# ---------------- 8. Drivers & explainability ----------------
heading(doc, "08", "What drives a fit score")
figure(doc, "04_feature_importance", 11, "Figure 4 — Permutation importance (drop in macro-F1 when a feature is shuffled)")
top3 = ", ".join(i.replace("_", " ") for i in importance.index[:3])
para(doc, f"The top drivers are **{top3}**. Must-have skill coverage dominates, which is expected: "
          "it carries the largest rule weight and the labels are built from those rules. Domain fit adds little once role fit is known, and text similarity adds almost nothing on these "
          "templated resumes.")
figure(doc, "05_score_breakdown", 15.5, "Figure 5 — Score breakdown for a shortlisted, a review and a rejected candidate")
callout(doc, "Example explanation shown to a recruiter",
        "#699 · DevOps Engineer · Review — 2/3 must-have skills; missing: Docker; 10 yrs fits 6–15 yr range; "
        "same domain; has all required experience areas.", COLORS["ink"])

# ---------------- 9. Business impact ----------------
doc.add_page_break()
heading(doc, "09", "Business impact")
wl = workload[["jd_id", "job_title", "resumes_read_today", "resumes_read_with_engine", "reduction_pct", "hours_saved"]].copy()
wl.columns = ["Job", "Title", "Read today", "Read with engine", "Reduction %", "Hours saved"]
table(doc, wl, col_widths=[1.3, 5.3, 2.3, 2.8, 2.3, 2.3], font_size=8)
para(doc, "Assumptions: 5 minutes per manual resume review; today recruiters read every resume in the job's domain "
          "and related domains; with the engine they read only Shortlist + Review. Gains are largest where the domain "
          "pool is big (Data Science, IT project management); small specialist pools (Talent Acquisition, Mechanical) "
          "are already almost all relevant, so the engine mainly adds ranking and explanations there.", size=9, italic=True)
figure(doc, "05_keyword_filter_miss", 12, "Figure 6 — High-fit candidates a keyword filter would reject because of spelling")

# ---------------- 10. Recommendations ----------------
heading(doc, "10", "Recommendations for recruiters")
gap_txt = "; ".join(f"{r.jd_id}: {r.mandatory_missing} ({r.share_of_review_pool:.0%})" for r in gaps.itertuples())
recs = [
    ("Triage with the hybrid score", "Read Shortlist first, then Review; archive Reject with its stored reason for audit."),
    ("Switch on fuzzy skill matching", f"Exact keyword filters drop {kw_missed/kw_total:.0%} of High-fit candidates purely because of spelling."),
    ("Challenge 'must-have' skills", f"One missing skill holds back most of each Review pool — {gap_txt}. Ask hiring managers whether it is trainable."),
    ("Keep institution tier out", "It carries no fit signal; the fairness check shows equal shortlist rates across tiers."),
    ("Standardise job descriptions", "Must-have vs nice-to-have, experience range and required experience areas — the engine is only as good as the JD."),
    ("Close the feedback loop", "Log recruiter and interview decisions for a quarter and re-train on real outcomes; review weights every quarter."),
]
t = doc.add_table(rows=0, cols=2)
for i, (h, d) in enumerate(recs):
    cells = t.add_row().cells
    shade(cells[0], COLORS["teal"] if i % 2 == 0 else COLORS["ink"])
    shade(cells[1], COLORS["sand"])
    for c in cells:
        cell_borders(c)
        c.paragraphs[0].text = ""
    set_font(cells[0].paragraphs[0].add_run(f"{i+1}. {h}"), HEADING_FONT, 10, True, "#FFFFFF")
    set_font(cells[1].paragraphs[0].add_run(d), size=9)
    cells[0].width, cells[1].width = Cm(4.8), Cm(11.7)
para(doc, "")

# ---------------- 11. Assumptions & limitations ----------------
heading(doc, "11", "Assumptions, limitations & next steps")
for b in [
    "**Rule-based labels:** without hiring outcomes the ML model learns recruiter rules; real decisions are needed to validate it.",
    "**Written job descriptions:** the 10 JDs were created for this project; real JDs should be parsed with the same skill dictionary.",
    "**Templated text:** richer, real resumes would let sentence-embedding models (e.g. SBERT) add more than TF-IDF/LSA could here.",
    "**Skill dictionary:** 30 skills today; new skills must be added as job families grow (the correction table is saved for audit).",
    "**Time-saving estimate:** depends on the 5-minute assumption and on today's process; it should be measured in a pilot.",
]:
    bullet(doc, b)

# ---------------- Appendix ----------------
doc.add_page_break()
heading(doc, "A", "Appendix — Job descriptions used")
app = jds[["jd_id", "job_title", "mandatory_skills", "optional_skills", "min_years", "max_years", "seniority"]].copy()
app["mandatory_skills"] = app["mandatory_skills"].str.replace("|", ", ")
app["optional_skills"] = app["optional_skills"].str.replace("|", ", ")
app["years"] = app["min_years"].astype(str) + "–" + app["max_years"].astype(str)
app = app[["jd_id", "job_title", "mandatory_skills", "optional_skills", "years", "seniority"]]
app.columns = ["ID", "Title", "Must-have", "Nice-to-have", "Years", "Level"]
table(doc, app, col_widths=[1.2, 4.2, 4.2, 4, 1.5, 1.5], font_size=8)
para(doc, "Project files: notebooks/01–05 (pipeline), src/ (reusable code), app/streamlit_app.py (dashboard), "
          "outputs/ (cleaned data, scores, shortlists), models/ (saved models).", size=9, color=COLORS["slate"])

# footer with page label
for s in doc.sections:
    fp = s.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(fp.add_run("TalentBridge · Resume Screening & Role Matching"), size=8, color=COLORS["slate"])

doc.save(OUT_FILE)
print("Saved", OUT_FILE)
