"""
features.py
-----------
Feature engineering for the resume screening project.

There are two kinds of features:
  1. Candidate features  - describe the candidate on their own
                           (skills, seniority, leadership exposure, resume quality ...)
  2. Candidate x Job     - describe how well ONE candidate fits ONE job description
     ("pair") features     (mandatory skill match %, experience fit, domain fit ...)
"""

import re

import numpy as np
import pandas as pd

from src.cleaning import SKILL_TO_FAMILY, clean_text

# ---------------------------------------------------------------
# Business mappings used by several features
# ---------------------------------------------------------------
# which skill families are "expected" for each domain
DOMAIN_SKILL_FAMILIES = {
    "IT": ["Software & Cloud"],
    "Data Science": ["Data & ML", "Software & Cloud"],   # data people also use Python / SQL
    "HR": ["HR"],
    "Legal": ["Legal"],
    "Engineering": ["Mechanical"],
    "Management": ["Management"],
}

# simple order for education level
EDUCATION_RANK = {"Not Specified": 0, "Bachelors": 1, "Masters": 2, "LLM": 2, "MBA": 2}

# groups of flags that describe the same kind of exposure
FLAG_GROUPS = {
    "leadership_score": ["management_experience_flag", "people_management_flag",
                         "mentoring_experience_flag", "delivery_lead_experience_flag"],
    "delivery_score": ["project_management_experience_flag", "agile_scrum_experience_flag",
                       "delivery_lead_experience_flag", "offshore_onsite_model_experience_flag",
                       "multi_vendor_coordination_flag"],
    "client_score": ["client_facing_experience_flag", "stakeholder_management_experience_flag"],
    "governance_score": ["compliance_experience_flag", "process_compliance_experience_flag",
                         "documentation_heavy_role_flag"],
}


def to_list(value, sep="|"):
    """Turn a 'a|b|c' string from the JD file (or a python list) into a clean list."""
    if isinstance(value, list):
        return value
    if pd.isna(value) or str(value).strip() == "":
        return []
    return [v.strip() for v in str(value).split(sep) if v.strip()]


# ---------------------------------------------------------------
# 1. Candidate level features
# ---------------------------------------------------------------
def experience_bucket(years):
    """Group years of experience into 4 easy-to-read buckets."""
    if years <= 2:
        return "Entry (0-2)"
    if years <= 5:
        return "Mid (3-5)"
    if years <= 10:
        return "Senior (6-10)"
    return "Expert (11+)"


def skill_domain_alignment(skills, domain):
    """Share of a candidate's skills that belong to the families expected for their domain."""
    if not skills:
        return 0.0
    expected = DOMAIN_SKILL_FAMILIES.get(domain, [])
    hits = sum(SKILL_TO_FAMILY.get(s) in expected for s in skills)
    return hits / len(skills)


def build_candidate_features(df):
    """
    Add candidate level engineered features to the cleaned dataframe.
    Expects the columns 'skills_clean' and 'tools_clean' (python lists).
    """
    out = df.copy()

    # --- skills -------------------------------------------------
    out["n_skills"] = out["skills_clean"].apply(len)
    out["n_tools"] = out["tools_clean"].apply(len)
    out["cloud_tool_count"] = out["tools_clean"].apply(lambda t: sum(x in ["AWS", "Azure", "GCP"] for x in t))
    out["main_skill_family"] = out["skills_clean"].apply(
        lambda s: pd.Series([SKILL_TO_FAMILY.get(x, "Other") for x in s]).mode().iloc[0] if s else "Other")
    out["skill_domain_alignment"] = out.apply(
        lambda r: skill_domain_alignment(r["skills_clean"], r["primary_domain"]), axis=1)

    # --- experience & seniority --------------------------------
    out["experience_bucket"] = out["years_experience"].apply(experience_bucket)
    out["education_rank"] = out["highest_education"].map(EDUCATION_RANK).fillna(0)

    # --- exposure scores (average of related yes/no flags) -----
    for score_name, cols in FLAG_GROUPS.items():
        out[score_name] = out[cols].mean(axis=1).round(3)

    # --- achievements & projects --------------------------------
    # pull the % number out of sentences like "increased productivity by 26%"
    out["achievement_pct"] = out["key_achievements"].str.extract(r"(\d+)\s*%")[0].astype(float).fillna(0)
    # did the candidate LEAD the project or just work on it?
    out["project_lead_flag"] = out["project_summary"].str.lower().str.startswith("led").astype(int)

    # --- resume quality ----------------------------------------
    # keyword density above 0.85 looks like "keyword stuffing" for an ATS
    out["keyword_stuffing_flag"] = (out["keyword_density_score"] > 0.85).astype(int)
    length_norm = (out["resume_length_words"] - out["resume_length_words"].min()) / \
                  (out["resume_length_words"].max() - out["resume_length_words"].min())
    out["resume_quality_score"] = (0.6 * out["profile_completeness_score"]
                                   + 0.2 * length_norm
                                   + 0.2 * (1 - out["keyword_stuffing_flag"])
                                   - 0.1 * out["education_missing_flag"]).clip(0, 1).round(3)

    # --- one combined text field for NLP ------------------------
    out["profile_text"] = (
        out["primary_role"] + ". " + out["primary_domain"] + ". "
        + "skills: " + out["skills_clean"].apply(", ".join) + ". "
        + "tools: " + out["tools_clean"].apply(", ".join) + ". "
        + out["soft_skills_raw"].fillna("") + ". "
        + out["experience_summary"] + " " + out["project_summary"] + " " + out["key_achievements"]
    ).apply(clean_text)
    # numbers ("43%", "10 years") say nothing about WHAT the person does, so they are
    # removed from the NLP text (years are already used separately in experience_fit)
    out["profile_text"] = out["profile_text"].str.replace(r"\d+\+?%?", " ", regex=True) \
                                             .str.replace(r"\s+", " ", regex=True).str.strip()
    return out


# ---------------------------------------------------------------
# 2. Candidate x Job (pair) features
# ---------------------------------------------------------------
def experience_fit(years, min_y, max_y):
    """
    1.0 when the years are inside the JD range.
    Below the minimum we lose 0.25 per missing year (being under-experienced is a real gap).
    Above the maximum we lose 0.05 per extra year, never below 0.6 (over-qualified is a smaller risk).
    """
    if min_y <= years <= max_y:
        return 1.0
    if years < min_y:
        return max(0.0, 1 - 0.25 * (min_y - years))
    return max(0.6, 1 - 0.05 * (years - max_y))


def seniority_fit(cand_level, jd_level):
    """Exact seniority match = 1, one level apart = 0.5, two levels apart = 0."""
    order = {"Junior": 0, "Mid": 1, "Senior": 2}
    gap = abs(order[cand_level] - order[jd_level])
    return {0: 1.0, 1: 0.5}.get(gap, 0.0)


def build_pair_features(cand, jd):
    """
    Score every candidate against ONE job description.
    Returns a dataframe with one row per candidate.
    """
    mand = to_list(jd["mandatory_skills"])
    opt = to_list(jd["optional_skills"])
    tools = to_list(jd["preferred_tools"])
    flags = to_list(jd["required_flags"])
    roles = to_list(jd["target_roles"])
    related = to_list(jd["related_domains"])
    edu = to_list(jd["preferred_education_fields"])

    # skills + tools together (AWS can appear in either column)
    all_skills = (cand["skills_clean"] + cand["tools_clean"]).apply(set)

    p = pd.DataFrame({"candidate_id": cand["candidate_id"], "jd_id": jd["jd_id"]})

    # --- skills ---------------------------------------------------
    p["mandatory_matched"] = all_skills.apply(lambda s: [m for m in mand if m in s])
    p["mandatory_missing"] = all_skills.apply(lambda s: [m for m in mand if m not in s])
    p["optional_matched"] = all_skills.apply(lambda s: [o for o in opt if o in s])
    p["mandatory_match"] = p["mandatory_matched"].apply(len) / max(len(mand), 1)
    p["optional_match"] = p["optional_matched"].apply(len) / max(len(opt), 1)
    p["all_mandatory_flag"] = (p["mandatory_match"] == 1).astype(int)
    p["tool_match"] = cand["tools_clean"].apply(lambda t: len(set(t) & set(tools)) / max(len(tools), 1))

    # --- experience & seniority ----------------------------------
    p["years_experience"] = cand["years_experience"].values
    p["years_gap"] = cand["years_experience"].apply(
        lambda y: 0 if jd["min_years"] <= y <= jd["max_years"] else (y - jd["min_years"] if y < jd["min_years"] else y - jd["max_years"]))
    p["experience_fit"] = cand["years_experience"].apply(lambda y: experience_fit(y, jd["min_years"], jd["max_years"]))
    p["seniority_fit"] = cand["seniority_level"].apply(lambda s: seniority_fit(s, jd["seniority"]))

    # --- domain & role -------------------------------------------
    p["domain_fit"] = cand["primary_domain"].apply(
        lambda d: 1.0 if d == jd["target_domain"] else (0.5 if d in related else 0.0))
    p["role_fit"] = cand.apply(
        lambda r: 1.0 if r["primary_role"] in roles else (0.4 if r["primary_domain"] == jd["target_domain"] else 0.0), axis=1)

    # --- behaviour flags required by the JD ----------------------
    p["flag_fit"] = cand[flags].mean(axis=1) if flags else 1.0

    # --- education -----------------------------------------------
    # unknown education gets a neutral 0.5 - we do not punish missing data too hard
    p["education_fit"] = cand["education_field"].apply(
        lambda f: 0.5 if f == "Not Specified" else (1.0 if f in edu else 0.2))

    # --- candidate quality / exposure carried over ----------------
    for col in ["resume_quality_score", "leadership_score", "delivery_score", "client_score",
                "governance_score", "skill_domain_alignment", "achievement_pct", "project_lead_flag",
                "education_rank", "n_tools"]:
        p[col] = cand[col].values
    return p
