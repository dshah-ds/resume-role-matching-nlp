"""
cleaning.py
-----------
Functions used to clean the parsed resume data.

The biggest problem in the raw data is that skills are typed in many
different (and misspelt) ways, e.g. "Pyhton", "Kubrenetes", "Powe rBI".
A plain keyword search would miss these candidates, so here every skill
is mapped back to one standard ("canonical") name.
"""

import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

# ---------------------------------------------------------------
# 1. Master skill dictionary
# ---------------------------------------------------------------
# These are the correctly spelt skills that appear most often in the data
# (each one shows up 100+ times). They are grouped by "skill family" so the
# family can later be used to check if a candidate's skills match a domain.
SKILL_FAMILIES = {
    "Software & Cloud": ["Python", "Java", "SQL", "Git", "Docker", "Linux", "Kubernetes", "AWS"],
    "Data & ML": ["Machine Learning", "NLP", "TensorFlow", "Pandas", "Power BI"],
    "HR": ["HRMS", "Recruitment", "HR Analytics", "Employee Engagement", "Payroll"],
    "Legal": ["Contract Drafting", "Legal Research", "Due Diligence", "Compliance"],
    "Mechanical": ["CAD", "SolidWorks", "Manufacturing", "Quality Control"],
    "Management": ["Risk Management", "Stakeholder Management", "Strategy", "Agile"],
}

# flat list of every canonical skill
CANONICAL_SKILLS = [skill for skills in SKILL_FAMILIES.values() for skill in skills]

# reverse lookup: skill -> family
SKILL_TO_FAMILY = {skill: fam for fam, skills in SKILL_FAMILIES.items() for skill in skills}

# the tools column only has 6 values and they are all spelt correctly
CANONICAL_TOOLS = ["AWS", "Azure", "GCP", "Jira", "Confluence", "ServiceNow"]

# a few common short forms people write on resumes
ALIASES = {
    "ml": "Machine Learning",
    "powerbi": "Power BI",
    "k8s": "Kubernetes",
    "tf": "TensorFlow",
    "hris": "HRMS",
}

# minimum fuzzy similarity (0-100) needed to accept a correction.
# 75 was picked after testing: it catches swapped letters like "Jaav" -> "Java"
# (score 75) but does not force random words onto a skill.
FUZZY_THRESHOLD = 75


def _key(text):
    """Lower-case and remove spaces/punctuation, so 'Powe rBI' and 'Power BI' look the same."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


# lookup table: squashed key -> canonical name (e.g. "powerbi" -> "Power BI")
_CANON_KEYS = {_key(s): s for s in CANONICAL_SKILLS}
_CANON_KEYS.update(ALIASES)


def normalize_skill(token):
    """
    Map one raw skill token to its canonical name.

    Returns a tuple (canonical_name, method) where method tells us HOW it was fixed:
      'exact'  - already correct
      'spacing'- only spaces / case were wrong (e.g. 'MachineL earning')
      'fuzzy'  - a typo fixed with fuzzy matching (e.g. 'Pyhton')
      'unknown'- could not be matched, kept as it is
    """
    token = str(token).strip()
    if token == "":
        return None, "empty"

    # exact match first (cheapest check)
    if token in CANONICAL_SKILLS:
        return token, "exact"

    key = _key(token)

    # same letters, different spacing / case
    if key in _CANON_KEYS:
        return _CANON_KEYS[key], "spacing"

    # fuzzy match against the squashed keys - this handles swapped / missing letters
    best = process.extractOne(key, list(_CANON_KEYS.keys()), scorer=fuzz.ratio)
    if best is not None and best[1] >= FUZZY_THRESHOLD:
        return _CANON_KEYS[best[0]], "fuzzy"

    return token, "unknown"


def split_skills(text):
    """Split a raw comma separated skill string into a list of trimmed tokens."""
    if pd.isna(text):
        return []
    return [t.strip() for t in re.split(r"[,;|]", str(text)) if t.strip()]


def clean_skill_list(text):
    """
    Turn a raw skill string into a sorted list of unique canonical skills.
    Duplicates created by the correction (e.g. 'Python' and 'Pyhton') are removed.
    """
    cleaned = []
    for token in split_skills(text):
        canon, _ = normalize_skill(token)
        if canon and canon not in cleaned:
            cleaned.append(canon)
    return sorted(cleaned)


def clean_tool_list(text):
    """Tools are already spelt correctly - only split, trim and remove duplicates."""
    tools = []
    for token in split_skills(text):
        if token not in tools:
            tools.append(token)
    return sorted(tools)


def build_skill_correction_table(series):
    """
    Build a table of every distinct raw token and what it was mapped to.
    Useful to *show* the corrections in the notebook and to audit them.
    """
    rows = []
    counts = pd.Series([t for text in series for t in split_skills(text)]).value_counts()
    for token, n in counts.items():
        canon, method = normalize_skill(token)
        rows.append({"raw_token": token, "canonical_skill": canon, "method": method, "occurrences": n})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# 2. Education fixes
# ---------------------------------------------------------------
def fix_education(df):
    """
    Clean the two education columns.

    - LLM is a Master of Laws degree. In the raw data many candidates hold an
      'LLM' in Computer Science, Statistics, etc. - which is not possible.
      Those rows are re-labelled as a general 'Masters' degree and flagged.
    - Missing values are filled with 'Not Specified' (not guessed), and a
      flag column remembers that the value was missing.
    """
    df = df.copy()

    # remember which rows were missing BEFORE filling them
    df["education_missing_flag"] = (df["highest_education"].isna() | df["education_field"].isna()).astype(int)

    # LLM with a non-law field -> logically inconsistent
    bad_llm = (df["highest_education"] == "LLM") & (df["education_field"].notna()) & (df["education_field"] != "Law")
    df["education_corrected_flag"] = bad_llm.astype(int)
    df.loc[bad_llm, "highest_education"] = "Masters"

    df["highest_education"] = df["highest_education"].fillna("Not Specified")
    df["education_field"] = df["education_field"].fillna("Not Specified")
    return df


# ---------------------------------------------------------------
# 3. Text clean-up
# ---------------------------------------------------------------
def clean_text(text):
    """Basic text normalisation for the free-text fields: lower case, strip extra spaces."""
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def role_from_filename(filename):
    """
    Try to read the job role written inside the resume file name.
    Example: 'resume_2736_Senior_Software_Engineer.pdf' -> 'seniorsoftwareengineer'.
    Generic names like 'profile_12.pdf' return None.
    """
    name = re.sub(r"\.pdf$", "", str(filename), flags=re.I)
    name = re.sub(r"\d+", "", name)
    name = re.sub(r"^(resume_+|profile_*)", "", name, flags=re.I)
    name = re.sub(r"_?candidate_?$", "", name, flags=re.I)
    key = _key(name)
    return key or None


def seniority_from_role(role):
    """Read the seniority level from the job title."""
    role = str(role).lower()
    if "junior" in role or "executive" in role or "associate" in role or "coordinator" in role:
        return "Junior"
    if "senior" in role or "manager" in role or "consultant" in role:
        return "Senior"
    return "Mid"


def load_cleaned(path):
    """
    Read the cleaned CSV saved by notebook 01 and turn the 'a|b|c' text
    columns back into python lists.
    """
    df = pd.read_csv(path)
    for col in ["skills_clean", "tools_clean", "soft_skills_clean"]:
        if col in df.columns:
            df[col] = df[col].fillna("").apply(lambda s: [x for x in str(s).split("|") if x])
    return df
