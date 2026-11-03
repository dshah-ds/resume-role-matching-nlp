"""
streamlit_app.py
----------------
Interactive recruiter dashboard for the resume screening engine.

Run from the project folder:
    streamlit run app/streamlit_app.py

Tabs
  1. Ranked shortlist   - ranked candidates for a job with the reason for each score
  2. Candidate profile  - why one candidate got their score (score breakdown)
  3. Job insights       - score distribution, skill gaps, domains, fairness by tier
  4. Score a new job    - build your own job description and rank all candidates live
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# make "src" importable when the app is started from any folder
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cleaning import CANONICAL_SKILLS, CANONICAL_TOOLS, load_cleaned
from src.config import (CANDIDATE_FEATURES_FILE, COLORS, FIT_COLORS, JD_FILE, MODELS, SCORED_FILE)
from src.features import build_pair_features, to_list
from src.matching import (RULE_WEIGHTS, assign_fit_label, explain, hybrid_score, recommendation,
                          rule_score, text_similarity)

st.set_page_config(page_title="TalentBridge · Resume Matcher", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------
# Small bit of custom styling (headline font + KPI cards)
# ---------------------------------------------------------------
st.markdown(f"""
<style>
h1, h2, h3 {{ font-family: Georgia, serif !important; color: {COLORS['ink']}; }}
.kpi {{ background: white; border-left: 6px solid {COLORS['teal']}; border-radius: 6px;
        padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
.kpi .v {{ font-size: 24px; font-weight: 700; color: {COLORS['ink']}; }}
.kpi .l {{ font-size: 13px; color: {COLORS['slate']}; }}
.tag {{ display:inline-block; padding:2px 10px; margin:2px; border-radius:12px; font-size:13px; }}
</style>
""", unsafe_allow_html=True)

REC_COLORS = {"Shortlist": COLORS["teal"], "Review": COLORS["mustard"], "Reject": COLORS["coral"]}
FLAG_OPTIONS = ["cloud_experience_flag", "ml_experience_flag", "agile_scrum_experience_flag",
                "client_facing_experience_flag", "delivery_lead_experience_flag", "people_management_flag",
                "management_experience_flag", "project_management_experience_flag", "compliance_experience_flag",
                "documentation_heavy_role_flag", "stakeholder_management_experience_flag",
                "multi_vendor_coordination_flag", "process_compliance_experience_flag", "mentoring_experience_flag"]


# ---------------------------------------------------------------
# Data loading (cached so it only runs once)
# ---------------------------------------------------------------
@st.cache_data
def load_data():
    scored = pd.read_csv(SCORED_FILE)
    for c in ["mandatory_matched", "mandatory_missing", "optional_matched"]:
        scored[c] = scored[c].fillna("").apply(lambda s: [x for x in str(s).split("|") if x])
    cands = load_cleaned(CANDIDATE_FEATURES_FILE)
    jds = pd.read_csv(JD_FILE)
    scored = scored.merge(cands[["candidate_id", "candidate_name", "primary_role", "primary_domain",
                                 "highest_education", "education_field", "institution_tier",
                                 "technical_skills_raw", "skills_clean", "tools_clean"]], on="candidate_id")
    scored["rank"] = scored.groupby("jd_id")["hybrid_score"].rank(ascending=False, method="first").astype(int)
    return scored, cands, jds


@st.cache_resource
def load_models():
    return (joblib.load(MODELS / "tfidf_vectorizer.pkl"), joblib.load(MODELS / "lsa_svd.pkl"),
            joblib.load(MODELS / "fit_classifier.pkl"))


def kpi(col, value, label, color=COLORS["teal"]):
    col.markdown(f'<div class="kpi" style="border-left-color:{color}"><div class="v">{value}</div>'
                 f'<div class="l">{label}</div></div>', unsafe_allow_html=True)


def tags(items, color):
    return " ".join(f'<span class="tag" style="background:{color}22;color:{color};border:1px solid {color}">{i}</span>'
                    for i in items) or "<i>none</i>"


def score_pairs_live(cands, jd, tfidf, lsa, clf):
    """Run the full pipeline for one (possibly new) job description."""
    p = build_pair_features(cands, jd)
    p["tfidf_sim"], p["lsa_sim"] = text_similarity(tfidf, lsa, cands["profile_text"], jd["jd_text"])
    for col in ["tfidf_sim", "lsa_sim"]:
        rng = p[col].max() - p[col].min()
        p[col + "_scaled"] = (p[col] - p[col].min()) / rng if rng > 0 else 0
    p["text_sim_scaled"] = p[["tfidf_sim_scaled", "lsa_sim_scaled"]].mean(axis=1)
    p["rule_score"] = rule_score(p)
    p["fit_label"] = assign_fit_label(p)
    proba = clf["model"].predict_proba(p[clf["features"]])
    classes = list(clf["model"].classes_)
    p["p_high"] = proba[:, classes.index("High")]
    p["ml_expected_fit"] = p["p_high"] + 0.5 * proba[:, classes.index("Medium")]
    p["hybrid_score"] = hybrid_score(p)
    p["recommendation"] = p["hybrid_score"].apply(recommendation)
    p["explanation"] = [explain(r, jd) for _, r in p.iterrows()]
    p = p.merge(cands[["candidate_id", "candidate_name", "primary_role", "primary_domain"]], on="candidate_id")
    p["rank"] = p["hybrid_score"].rank(ascending=False, method="first").astype(int)
    return p.sort_values("rank")


scored, cands, jds = load_data()
tfidf, lsa, clf = load_models()

# ---------------------------------------------------------------
# Sidebar - pick a job and filters
# ---------------------------------------------------------------
st.sidebar.markdown("## 🧭 TalentBridge")
st.sidebar.caption("Resume Screening & Role Matching")
jd_label = st.sidebar.selectbox("Job description", [f"{r.jd_id} · {r.job_title}" for r in jds.itertuples()])
jd_id = jd_label.split(" · ")[0]
jd = jds.set_index("jd_id").loc[jd_id]
jd_full = jds[jds["jd_id"] == jd_id].iloc[0]

recs = st.sidebar.multiselect("Recommendation", ["Shortlist", "Review", "Reject"], default=["Shortlist", "Review"])
yr_min, yr_max = st.sidebar.slider("Years of experience", 1, 20, (1, 20))
domains = st.sidebar.multiselect("Candidate domain", sorted(scored["primary_domain"].unique()))
top_n = st.sidebar.slider("Show top N", 10, 200, 50, step=10)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Must-have:** {', '.join(to_list(jd['mandatory_skills']))}")
st.sidebar.markdown(f"**Nice-to-have:** {', '.join(to_list(jd['optional_skills']))}")
st.sidebar.markdown(f"**Experience:** {jd['min_years']}–{jd['max_years']} yrs · {jd['seniority']}")

job = scored[scored["jd_id"] == jd_id]
view = job[job["recommendation"].isin(recs) & job["years_experience"].between(yr_min, yr_max)]
if domains:
    view = view[view["primary_domain"].isin(domains)]
view = view.sort_values("rank").head(top_n)

# ---------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------
st.title(f"{jd['job_title']}")
st.caption(jd["jd_text"])

k1, k2, k3, k4, k5 = st.columns(5)
kpi(k1, f"{len(job):,}", "candidates scored", COLORS["ink"])
kpi(k2, f"{(job['recommendation'] == 'Shortlist').sum():,}", "shortlisted", COLORS["teal"])
kpi(k3, f"{(job['recommendation'] == 'Review').sum():,}", "to review", COLORS["mustard"])
manual = (job["domain_fit"] > 0).sum()
engine = job["recommendation"].isin(["Shortlist", "Review"]).sum()
kpi(k4, f"{(1 - engine / manual):.0%}" if manual else "–", "less reading vs domain filter", COLORS["coral"])
kpi(k5, f"{job.nsmallest(20, 'rank')['hybrid_score'].mean():.2f}", "avg score of top 20", COLORS["slate"])
st.write("")

tab1, tab2, tab3, tab4 = st.tabs(["📋 Ranked shortlist", "👤 Candidate profile", "📊 Job insights", "✨ Score a new job"])

# ---------------------------------------------------------------
# Tab 1 - ranked shortlist
# ---------------------------------------------------------------
with tab1:
    table = view[["rank", "candidate_id", "primary_role", "years_experience", "hybrid_score",
                  "recommendation", "explanation"]].rename(columns={
        "rank": "Rank", "candidate_id": "Candidate", "primary_role": "Role", "years_experience": "Years",
        "hybrid_score": "Fit score", "recommendation": "Action", "explanation": "Why"})
    st.dataframe(table, hide_index=True, use_container_width=True, height=520,
                 column_config={"Fit score": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                                "Why": st.column_config.TextColumn(width="large")})
    st.download_button("⬇️ Download this shortlist (CSV)", table.to_csv(index=False).encode(),
                       file_name=f"shortlist_{jd_id}.csv", mime="text/csv")

# ---------------------------------------------------------------
# Tab 2 - candidate profile
# ---------------------------------------------------------------
with tab2:
    if view.empty:
        st.info("No candidates match the filters.")
    else:
        cid = st.selectbox("Candidate", view["candidate_id"] + " · " + view["primary_role"])
        r = job[job["candidate_id"] == cid.split(" · ")[0]].iloc[0]
        c1, c2 = st.columns([1, 1.3])
        with c1:
            st.markdown(f"### {r['candidate_name']}")
            st.markdown(f"**{r['primary_role']}** · {r['primary_domain']} · {r['years_experience']} yrs  \n"
                        f"{r['highest_education']} in {r['education_field']}")
            st.markdown(f"**Rank #{r['rank']}** · fit score **{r['hybrid_score']:.2f}** · "
                        f"<span style='color:{REC_COLORS[r['recommendation']]};font-weight:700'>{r['recommendation']}</span>",
                        unsafe_allow_html=True)
            st.markdown("**Must-have matched** " + tags(r["mandatory_matched"], COLORS["teal"]), unsafe_allow_html=True)
            st.markdown("**Must-have missing** " + tags(r["mandatory_missing"], COLORS["coral"]), unsafe_allow_html=True)
            st.markdown("**Bonus skills** " + tags(r["optional_matched"], COLORS["mustard"]), unsafe_allow_html=True)
            st.markdown("**Raw skills on resume:** " + r["technical_skills_raw"])
            st.info(r["explanation"])
        with c2:
            parts = pd.DataFrame({"part": [k.replace("_", " ") for k in RULE_WEIGHTS],
                                  "earned": [r[k] * w for k, w in RULE_WEIGHTS.items()],
                                  "max": list(RULE_WEIGHTS.values())})
            fig = go.Figure()
            fig.add_bar(y=parts["part"], x=parts["max"], orientation="h", name="max possible",
                        marker_color="#E9DFD2")
            fig.add_bar(y=parts["part"], x=parts["earned"], orientation="h", name="earned", marker_color=COLORS["teal"])
            fig.update_layout(barmode="overlay", title="Score breakdown (rule score parts)", height=400,
                              yaxis=dict(autorange="reversed"), plot_bgcolor="white",
                              legend=dict(orientation="h", y=-0.15), margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Rule score", f"{r['rule_score']:.2f}")
            m2.metric("ML P(High fit)", f"{r['p_high']:.2f}")
            m3.metric("Semantic match", f"{r['lsa_sim']:.2f}")

# ---------------------------------------------------------------
# Tab 3 - job insights
# ---------------------------------------------------------------
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(job, x="hybrid_score", color="recommendation", nbins=50,
                           color_discrete_map=REC_COLORS, title="Fit score distribution")
        fig.update_layout(plot_bgcolor="white", bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        gaps = job[job["recommendation"] == "Review"].explode("mandatory_missing")["mandatory_missing"].value_counts()
        if len(gaps):
            fig = px.bar(x=gaps.values, y=gaps.index, orientation="h", title="Must-have skill missing in the Review pool",
                         color_discrete_sequence=[COLORS["coral"]], labels={"x": "candidates", "y": ""})
            fig.update_layout(plot_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"If **{gaps.index[0]}** were trainable (moved to nice-to-have), up to "
                       f"{gaps.iloc[0]} more candidates could be considered.")
        else:
            st.info("No Review-band candidates for this job.")
    c3, c4 = st.columns(2)
    with c3:
        dom = job[job["recommendation"] != "Reject"]["primary_domain"].value_counts()
        fig = px.pie(values=dom.values, names=dom.index, hole=0.55, title="Domains in shortlist + review",
                     color_discrete_sequence=[COLORS["teal"], COLORS["mustard"], COLORS["ink"], COLORS["coral"]])
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        tier = (job.groupby("institution_tier")["recommendation"].apply(lambda s: (s == "Shortlist").mean())
                   .reset_index(name="shortlist_rate"))
        fig = px.bar(tier, x="institution_tier", y="shortlist_rate", title="Fairness check: shortlist rate by institution tier",
                     color_discrete_sequence=[COLORS["ink"]], labels={"institution_tier": "", "shortlist_rate": "shortlist rate"})
        fig.update_layout(plot_bgcolor="white", yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Institution tier is not used in scoring - rates should be similar.")

# ---------------------------------------------------------------
# Tab 4 - score a brand new job description live
# ---------------------------------------------------------------
with tab4:
    st.markdown("Build a job description and rank all 5,000 candidates against it.")
    c1, c2 = st.columns(2)
    with c1:
        title = st.text_input("Job title", "Machine Learning Engineer")
        domain = st.selectbox("Target domain", sorted(cands["primary_domain"].unique()), index=0)
        related = st.multiselect("Related domains (half credit)", sorted(cands["primary_domain"].unique()), default=["IT"])
        roles = st.multiselect("Target roles", sorted(cands["primary_role"].unique()), default=["ML Engineer", "Data Scientist"])
        mand = st.multiselect("Must-have skills", sorted(CANONICAL_SKILLS), default=["Python", "TensorFlow"])
        opt = st.multiselect("Nice-to-have skills", sorted(CANONICAL_SKILLS), default=["Docker", "SQL"])
    with c2:
        tools = st.multiselect("Preferred tools", CANONICAL_TOOLS, default=["AWS"])
        yrs = st.slider("Experience range (years)", 0, 20, (3, 8))
        seniority = st.selectbox("Seniority", ["Junior", "Mid", "Senior"], index=1)
        flags = st.multiselect("Required experience areas", FLAG_OPTIONS, default=["ml_experience_flag"])
        edu = st.multiselect("Preferred education fields", sorted(cands["education_field"].unique()),
                             default=["Computer Science", "Data Science"])
        text = st.text_area("Job description text", "Build and deploy machine learning models in Python and TensorFlow, "
                            "package them with Docker and work with product teams.")
    if st.button("Rank candidates", type="primary"):
        if not mand:
            st.warning("Pick at least one must-have skill.")
        else:
            new_jd = pd.Series({"jd_id": "CUSTOM", "job_title": title, "target_domain": domain,
                                "related_domains": "|".join(related), "target_roles": "|".join(roles),
                                "mandatory_skills": "|".join(mand), "optional_skills": "|".join(opt),
                                "preferred_tools": "|".join(tools), "min_years": yrs[0], "max_years": yrs[1],
                                "seniority": seniority, "required_flags": "|".join(flags),
                                "preferred_education_fields": "|".join(edu), "jd_text": text})
            with st.spinner("Scoring 5,000 candidates..."):
                res = score_pairs_live(cands, new_jd, tfidf, lsa, clf)
            a, b, c = st.columns(3)
            a.metric("Shortlist", int((res["recommendation"] == "Shortlist").sum()))
            b.metric("Review", int((res["recommendation"] == "Review").sum()))
            c.metric("Reject", int((res["recommendation"] == "Reject").sum()))
            st.dataframe(res.head(50)[["rank", "candidate_id", "primary_role", "years_experience", "hybrid_score",
                                       "recommendation", "explanation"]],
                         hide_index=True, use_container_width=True,
                         column_config={"hybrid_score": st.column_config.ProgressColumn(
                             "Fit score", min_value=0, max_value=1, format="%.2f")})
