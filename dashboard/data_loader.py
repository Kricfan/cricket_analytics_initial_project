"""
Load the cleaned player datasets produced by ``data/python files/
combined stats.py`` and prepare them for analysis.

Two CSV files are used:
    player_match_stats.csv   - one row per player per match
    player_career_stats.csv  - one row per player (all-time totals)

Both loaders are cached by Streamlit, so the CSVs are read from disk once
per session rather than on every interaction with the dashboard.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

# The combiner script writes its output to <project>/data/output.
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output"
MATCH_STATS_FILE = OUTPUT_DIR / "player_match_stats.csv"
CAREER_STATS_FILE = OUTPUT_DIR / "player_career_stats.csv"

# Friendly labels for the gender values stored in the data.
GENDER_LABELS = {"male": "Men", "female": "Women"}


def data_files_exist():
    """Return True when both combined CSV files are present on disk."""
    return MATCH_STATS_FILE.exists() and CAREER_STATS_FILE.exists()


@st.cache_data(show_spinner="Loading match data...")
def load_match_stats():
    """
    Read the player-per-match file and add helper columns.

    Rows without a team are dropped: they are substitute fielders who
    were not in either playing XI, so they did not officially play.
    """
    matches = pd.read_csv(MATCH_STATS_FILE, dtype={"match_id": str})
    matches = matches.dropna(subset=["team"])

    # Convert text dates into real dates so we can group by year.
    matches["date"] = pd.to_datetime(matches["date"])
    matches["year"] = matches["date"].dt.year
    matches["gender_label"] = matches["gender"].map(GENDER_LABELS)
    return matches


@st.cache_data(show_spinner="Loading career data...")
def load_career_stats():
    """Read the one-row-per-player career file."""
    career = pd.read_csv(CAREER_STATS_FILE)
    career["gender_label"] = career["gender"].map(GENDER_LABELS)
    return career
