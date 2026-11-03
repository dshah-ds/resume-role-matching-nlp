"""
plot_style.py
-------------
Small helper that applies the project colours to every matplotlib chart,
so the notebooks, report and slides all share one look.
"""

import matplotlib.pyplot as plt
import seaborn as sns

from src.config import COLORS, PALETTE, FIGURES


def set_style():
    """Apply the project theme to matplotlib / seaborn."""
    sns.set_theme(style="whitegrid", palette=PALETTE)
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": COLORS["slate"],
        "axes.labelcolor": COLORS["ink"],
        "axes.titlecolor": COLORS["ink"],
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "axes.spines.top": False,      # remove the top border - cleaner look
        "axes.spines.right": False,    # remove the right border
        "grid.color": "#E3E3E3",
        "xtick.color": COLORS["slate"],
        "ytick.color": COLORS["slate"],
        "font.family": "sans-serif",
        "figure.dpi": 110,
    })


def save(fig, name):
    """Save a figure into outputs/figures so it can be reused in the report and deck."""
    path = FIGURES / f"{name}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    return path
