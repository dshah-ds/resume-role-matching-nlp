"""
config.py
---------
One place for all file paths, colours and fonts used across the project.
Keeping these here means the notebooks, the dashboard and the report
all point at the same files and look the same.
"""

from pathlib import Path

# ---------------------------------------------------------------
# Folder layout
# ---------------------------------------------------------------
# ROOT is the project folder (one level up from this src/ folder)
ROOT = Path(__file__).resolve().parents[1]

RAW_DATA = ROOT / "Dataset" / "parsed_resumes.csv"        # original data given to us
JD_FILE = ROOT / "data" / "job_descriptions.csv"          # job descriptions written for this project
OUTPUTS = ROOT / "outputs"                                # all generated csv files
FIGURES = OUTPUTS / "figures"                             # all saved charts
MODELS = ROOT / "models"                                  # pickled models

CLEANED_FILE = OUTPUTS / "cleaned_resumes.csv"            # output of notebook 01
CANDIDATE_FEATURES_FILE = OUTPUTS / "candidate_features.csv"  # output of notebook 03
PAIR_FEATURES_FILE = OUTPUTS / "candidate_jd_pairs.csv"   # one row per candidate x job
SCORED_FILE = OUTPUTS / "scored_pairs.csv"                # output of notebook 04
SHORTLIST_FILE = OUTPUTS / "ranked_shortlists.csv"        # output of notebook 05

# make sure the output folders exist before anything tries to save into them
for folder in [OUTPUTS, FIGURES, MODELS]:
    folder.mkdir(parents=True, exist_ok=True)

# fixed random seed so every run gives the same numbers
RANDOM_STATE = 42

# ---------------------------------------------------------------
# Visual identity ("TalentBridge" theme)
# ---------------------------------------------------------------
# A deep ink blue + teal + coral palette with a warm sand background.
COLORS = {
    "ink": "#1B2A41",      # dark navy - titles and main text
    "teal": "#0F7B6C",     # primary accent - "good fit"
    "coral": "#E4572E",    # warning accent - "low fit" / gaps
    "mustard": "#F2B134",  # highlight - "medium fit"
    "sand": "#F6EFE6",     # soft background
    "slate": "#5B6C7D",    # secondary text / gridlines
    "mint": "#A8D5BA",     # light teal for fills
}

# order used for the three fit classes in every chart
FIT_COLORS = {"High": COLORS["teal"], "Medium": COLORS["mustard"], "Low": COLORS["coral"]}

# a categorical palette for charts with many groups
PALETTE = [COLORS["teal"], COLORS["coral"], COLORS["mustard"], COLORS["ink"],
           COLORS["mint"], COLORS["slate"], "#B56576", "#6D597A"]

# fonts used in the report and the slide deck
HEADING_FONT = "Georgia"
BODY_FONT = "Trebuchet MS"
