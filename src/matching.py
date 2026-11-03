"""
matching.py
-----------
The scoring logic of the screening engine:

  1. NLP similarity      - TF-IDF and LSA (topic) cosine similarity between a
                           candidate's profile text and the job description text.
  2. Rule based score    - a weighted score built from the pair features, the
                           way a recruiter would think about fit.
  3. Fit label           - High / Medium / Low, created from business rules
                           (needed because the data has no "hired" column).
  4. Hybrid score        - rule score + ML probability + text similarity.
  5. Explanations        - a plain-English reason for every score.
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import RANDOM_STATE

# ---------------------------------------------------------------
# 1. NLP similarity
# ---------------------------------------------------------------
def fit_text_models(candidate_texts, jd_texts, n_topics=50):
    """
    Fit a TF-IDF vectoriser on all candidate + JD texts, then reduce it with
    LSA (TruncatedSVD) so related words (e.g. 'docker' and 'kubernetes') end up
    close to each other in a smaller "topic" space.
    """
    corpus = list(candidate_texts) + list(jd_texts)
    tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    tfidf.fit(corpus)
    lsa = TruncatedSVD(n_components=n_topics, random_state=RANDOM_STATE)
    lsa.fit(tfidf.transform(corpus))
    return tfidf, lsa


def text_similarity(tfidf, lsa, candidate_texts, jd_text):
    """Return (tfidf_cosine, lsa_cosine) arrays for every candidate against one JD text."""
    cand_vec = tfidf.transform(candidate_texts)
    jd_vec = tfidf.transform([jd_text])
    tfidf_sim = cosine_similarity(cand_vec, jd_vec).ravel()
    lsa_sim = cosine_similarity(lsa.transform(cand_vec), lsa.transform(jd_vec)).ravel()
    return tfidf_sim, lsa_sim


# ---------------------------------------------------------------
# 2. Rule based score
# ---------------------------------------------------------------
# Weights are a judgement call, not learned: must-have skills first, then
# experience, then domain/role background. They add up to 1.0. Notebook 04
# checks how much the ranking moves when each weight shifts by up to 30%.
RULE_WEIGHTS = {
    "mandatory_match": 0.30,
    "experience_fit": 0.15,
    "domain_fit": 0.10,
    "role_fit": 0.10,
    "flag_fit": 0.10,
    "optional_match": 0.10,
    "education_fit": 0.05,
    "tool_match": 0.05,
    "resume_quality_score": 0.05,
}


def rule_score(pairs, weights=RULE_WEIGHTS):
    """Weighted sum of the pair features -> a score between 0 and 1."""
    score = sum(pairs[col] * w for col, w in weights.items())
    return score.clip(0, 1)


# ---------------------------------------------------------------
# 3. Fit label (target variable for the ML models)
# ---------------------------------------------------------------
def assign_fit_label(pairs):
    """
    Business rules used to create the High / Medium / Low target:

    High   - rule score >= 0.75 AND at least 2/3 of mandatory skills AND
             experience inside (or very close to) the required range.
    Low    - rule score < 0.50 OR less than 1/3 of mandatory skills OR
             a completely unrelated domain.
    Medium - everything in between (worth a recruiter's look).
    """
    high = (pairs["rule_score"] >= 0.75) & (pairs["mandatory_match"] >= 0.66) & (pairs["experience_fit"] >= 0.75)
    low = (pairs["rule_score"] < 0.50) | (pairs["mandatory_match"] < 0.34) | (pairs["domain_fit"] == 0)
    label = np.where(high, "High", np.where(low, "Low", "Medium"))
    return pd.Series(label, index=pairs.index)


# ---------------------------------------------------------------
# 4. Hybrid score & recommendation bands
# ---------------------------------------------------------------
# Chosen in notebook 04 (section 7). Text similarity is NOT added directly: the resume summaries are
# templated, and every bit of direct weight pushed off-profile candidates up. It still feeds the ML
# model as an input feature and is shown to recruiters as a separate "semantic match" signal.
HYBRID_WEIGHTS = {"rule_score": 0.70, "ml_expected_fit": 0.30}


def hybrid_score(pairs, weights=HYBRID_WEIGHTS):
    """Blend the transparent rule score with the ML expected fit (text similarity reaches it only through the ML features)."""
    return sum(pairs[col] * w for col, w in weights.items()).clip(0, 1)


def recommendation(score, shortlist_cut=0.72, review_cut=0.55):
    """Turn the final score into an action for the recruiter."""
    if score >= shortlist_cut:
        return "Shortlist"
    if score >= review_cut:
        return "Review"
    return "Reject"


# ---------------------------------------------------------------
# 5. Explanations
# ---------------------------------------------------------------
def explain(row, jd):
    """Build a short plain-English explanation for one candidate-job pair."""
    parts = []

    n_mand = len(row["mandatory_matched"]) + len(row["mandatory_missing"])
    parts.append(f"{len(row['mandatory_matched'])}/{n_mand} must-have skills")
    if row["mandatory_missing"]:
        parts.append("missing: " + ", ".join(row["mandatory_missing"]))
    if row["optional_matched"]:
        parts.append("bonus skills: " + ", ".join(row["optional_matched"]))

    yrs = row["years_experience"]
    if row["experience_fit"] == 1:
        parts.append(f"{yrs} yrs fits {jd['min_years']}-{jd['max_years']} yr range")
    elif yrs < jd["min_years"]:
        parts.append(f"{yrs} yrs is below the {jd['min_years']} yr minimum")
    else:
        parts.append(f"{yrs} yrs is above the range (may be over-qualified)")

    if row["domain_fit"] == 1:
        parts.append("same domain")
    elif row["domain_fit"] == 0.5:
        parts.append("related domain")
    else:
        parts.append("different domain")

    if row["flag_fit"] >= 0.99:
        parts.append("has all required experience areas")
    elif row["flag_fit"] <= 0.34:
        parts.append("lacks most required experience areas")

    return "; ".join(parts)
