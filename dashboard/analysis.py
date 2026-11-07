"""
Analysis functions for the cricket dashboard.

Every function here takes a pandas DataFrame and returns a new summary
DataFrame (or a dict of numbers). Nothing in this module draws charts or
touches Streamlit, which keeps the analysis easy to test and reuse.
"""

import numpy as np
import pandas as pd

# Columns that are simple totals when several matches are combined.
SUM_COLUMNS = [
    "runs", "balls_faced", "fours", "sixes", "out", "balls_bowled",
    "runs_conceded", "wickets", "maidens", "catches", "stumpings",
    "run_outs",
]

# A year needs at least this many matches before its trend is shown;
# early years with only a handful of games make the lines too noisy.
MIN_MATCHES_PER_YEAR = 10


def safe_ratio(numerator, denominator, scale=1.0):
    """Divide two Series, returning NaN instead of infinity for zero."""
    denominator = denominator.replace(0, np.nan)
    return (numerator / denominator * scale).round(2)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_matches(matches, genders, year_range, teams=None):
    """
    Keep only the rows matching the sidebar filters.

    genders     list of "Men"/"Women" labels to keep
    year_range  (first_year, last_year), both inclusive
    teams       optional list of team names; empty or None keeps all
    """
    first_year, last_year = year_range
    mask = (
        matches["gender_label"].isin(genders)
        & matches["year"].between(first_year, last_year)
    )
    if teams:
        mask &= matches["team"].isin(teams)
    return matches[mask]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def headline_kpis(matches):
    """Return the big headline numbers shown at the top of the page."""
    return {
        "matches": matches["match_id"].nunique(),
        "players": matches["player_id"].nunique(),
        "runs": int(matches["runs"].sum()),
        "wickets": int(matches["wickets"].sum()),
        "sixes": int(matches["sixes"].sum()),
        "fifties": int((matches["runs"] >= 50).sum()),
    }


def yearly_trends(matches):
    """
    Summarise how T20 batting has changed year by year, per gender.

    Returns one row per (year, gender) with:
        strike_rate      runs scored per 100 balls faced
        boundary_pct     share of batting runs that came from 4s and 6s
        sixes_per_match  average number of sixes hit in a match
        runs_per_innings average team batting runs per innings
    """
    grouped = matches.groupby(["year", "gender_label"]).agg(
        matches=("match_id", "nunique"),
        runs=("runs", "sum"),
        balls=("balls_faced", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
    ).reset_index()

    boundary_runs = grouped["fours"] * 4 + grouped["sixes"] * 6
    grouped["strike_rate"] = safe_ratio(grouped["runs"], grouped["balls"],
                                        100)
    grouped["boundary_pct"] = safe_ratio(boundary_runs, grouped["runs"], 100)
    grouped["sixes_per_match"] = safe_ratio(grouped["sixes"],
                                            grouped["matches"])
    # Each match has two batting innings, one per team.
    grouped["runs_per_innings"] = safe_ratio(grouped["runs"],
                                             grouped["matches"] * 2)

    return grouped[grouped["matches"] >= MIN_MATCHES_PER_YEAR]


def trend_change(trends, column, gender):
    """
    Compare a trend's first and last shown year for one gender.

    Returns (first_year, first_value, last_year, last_value), or None
    when there are fewer than two years to compare.
    """
    rows = trends[trends["gender_label"] == gender].sort_values("year")
    if len(rows) < 2:
        return None
    first, last = rows.iloc[0], rows.iloc[-1]
    return (int(first["year"]), first[column],
            int(last["year"]), last[column])


# ---------------------------------------------------------------------------
# Player leaderboards
# ---------------------------------------------------------------------------

def aggregate_players(matches):
    """
    Combine match rows into one row per player for the filtered period.

    This is recalculated from the match-level file (rather than read from
    the career file) so the leaderboards respect the year/team filters.
    """
    totals = matches.groupby("player_id")[SUM_COLUMNS].sum()

    # Count innings, milestones and matches separately.
    totals["matches"] = matches.groupby("player_id")["match_id"].nunique()
    totals["innings"] = matches.groupby("player_id")["batted"].sum()
    totals["fifties"] = (
        matches["runs"].between(50, 99).groupby(matches["player_id"]).sum()
    )
    totals["hundreds"] = (
        (matches["runs"] >= 100).groupby(matches["player_id"]).sum()
    )
    totals["highest"] = matches.groupby("player_id")["runs"].max()

    # Name, gender and team(s) come from the player's match rows.
    info = matches.groupby("player_id").agg(
        name=("player_name", "first"),
        gender=("gender_label", "first"),
        team=("team", lambda t: ", ".join(sorted(t.unique()))),
    )
    players = info.join(totals).reset_index()

    # Batting rate statistics.
    players["average"] = safe_ratio(players["runs"], players["out"])
    players["strike_rate"] = safe_ratio(players["runs"],
                                        players["balls_faced"], 100)

    # Bowling rate statistics (lower is better for all three).
    players["economy"] = safe_ratio(players["runs_conceded"],
                                    players["balls_bowled"], 6)
    players["bowling_average"] = safe_ratio(players["runs_conceded"],
                                            players["wickets"])
    players["bowling_strike_rate"] = safe_ratio(players["balls_bowled"],
                                                players["wickets"])
    return players


def batting_leaderboard(players, min_innings, top_n=20):
    """Top run scorers who batted in at least ``min_innings`` innings."""
    qualified = players[players["innings"] >= min_innings]
    return qualified.nlargest(top_n, "runs")


def bowling_leaderboard(players, min_overs, top_n=20):
    """Top wicket takers who bowled at least ``min_overs`` overs."""
    qualified = players[players["balls_bowled"] >= min_overs * 6]
    return qualified.nlargest(top_n, ["wickets", "balls_bowled"])


def batter_archetypes(players, min_innings):
    """
    Label each qualified batter by comparing them with the median player.

        Elite      above-median average AND strike rate
        Anchor     above-median average, below-median strike rate
        Aggressor  below-median average, above-median strike rate
        Developing below the median on both

    Returns (labelled DataFrame, median average, median strike rate).
    """
    qualified = players[
        (players["innings"] >= min_innings) & players["average"].notna()
    ].copy()
    if qualified.empty:
        return qualified, np.nan, np.nan

    median_avg = qualified["average"].median()
    median_sr = qualified["strike_rate"].median()

    high_avg = qualified["average"] >= median_avg
    high_sr = qualified["strike_rate"] >= median_sr
    qualified["archetype"] = np.select(
        [high_avg & high_sr, high_avg, high_sr],
        ["Elite", "Anchor", "Aggressor"],
        default="Developing",
    )
    return qualified, median_avg, median_sr


# ---------------------------------------------------------------------------
# Team analysis
# ---------------------------------------------------------------------------

def team_innings(matches):
    """
    Collapse player rows into one row per team per match.

    Each row records the team's result plus its best individual batting
    and bowling performances in that match.
    """
    per_team = matches.groupby(["match_id", "team"]).agg(
        gender=("gender_label", "first"),
        won=("team_won", "max"),
        top_score=("runs", "max"),
        best_wickets=("wickets", "max"),
    ).reset_index()

    # Drop no-results and ties: matches where neither side won.
    decided = per_team.groupby("match_id")["won"].transform("max")
    return per_team[decided.astype(bool)]


def team_records(matches, min_matches=20):
    """Matches played, wins and win percentage for each team."""
    per_team = team_innings(matches)
    records = per_team.groupby(["team", "gender"]).agg(
        matches=("match_id", "nunique"),
        wins=("won", "sum"),
    ).reset_index()
    records["win_pct"] = safe_ratio(records["wins"], records["matches"], 100)
    records = records[records["matches"] >= min_matches]
    return records.sort_values("win_pct", ascending=False)


def match_winning_factors(matches):
    """
    How often does a team win when one player has a big game?

    Compares a team's win percentage with and without:
        - a batter scoring 50 or more
        - a bowler taking 3 or more wickets
    """
    per_team = team_innings(matches)
    factors = {
        "A batter scores 50+": per_team["top_score"] >= 50,
        "A bowler takes 3+ wickets": per_team["best_wickets"] >= 3,
    }

    rows = []
    for factor, happened in factors.items():
        for label, subset in (("Yes", per_team[happened]),
                              ("No", per_team[~happened])):
            rows.append({
                "factor": factor,
                "happened": label,
                "team_innings": len(subset),
                "win_pct": round(subset["won"].mean() * 100, 1)
                if len(subset) else np.nan,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Single player analysis
# ---------------------------------------------------------------------------

def player_innings(matches, player_id, window=10):
    """
    The player's batting innings in date order, with running totals.

    Adds ``cumulative_runs`` and ``rolling_avg`` (mean runs over the last
    ``window`` innings) to show how their form has changed over time.
    """
    innings = matches[
        (matches["player_id"] == player_id) & matches["batted"]
    ].sort_values("date").copy()

    innings["innings_number"] = range(1, len(innings) + 1)
    innings["cumulative_runs"] = innings["runs"].cumsum()
    innings["rolling_avg"] = (
        innings["runs"].rolling(window, min_periods=1).mean().round(1)
    )
    return innings


def player_by_opponent(matches, player_id):
    """Batting and bowling totals for one player split by opponent."""
    rows = matches[matches["player_id"] == player_id]
    by_opp = rows.groupby("opponent").agg(
        matches=("match_id", "nunique"),
        runs=("runs", "sum"),
        balls=("balls_faced", "sum"),
        outs=("out", "sum"),
        wickets=("wickets", "sum"),
        balls_bowled=("balls_bowled", "sum"),
        runs_conceded=("runs_conceded", "sum"),
    ).reset_index()

    by_opp["average"] = safe_ratio(by_opp["runs"], by_opp["outs"])
    by_opp["strike_rate"] = safe_ratio(by_opp["runs"], by_opp["balls"], 100)
    by_opp["economy"] = safe_ratio(by_opp["runs_conceded"],
                                   by_opp["balls_bowled"], 6)
    return by_opp.sort_values("matches", ascending=False)


def player_dismissals(matches, player_id):
    """Count how the player has been dismissed."""
    rows = matches[(matches["player_id"] == player_id) & matches["out"]]
    counts = rows["dismissal"].value_counts().reset_index()
    counts.columns = ["dismissal", "count"]
    return counts


def player_win_impact(matches, player_id, runs_cutoff=30, wickets_cutoff=2):
    """
    Team win percentage depending on how well the player performed.

    Returns a dict of win percentages (or None where there were no
    matches in that group), for:
        - innings where they scored ``runs_cutoff``+ vs fewer
        - matches where they took ``wickets_cutoff``+ wickets vs fewer
    """
    rows = matches[matches["player_id"] == player_id]

    def win_pct(subset):
        if subset.empty:
            return None
        return round(subset["team_won"].mean() * 100, 1)

    batted = rows[rows["batted"]]
    bowled = rows[rows["balls_bowled"] > 0]
    return {
        "overall": win_pct(rows),
        "big_score": win_pct(batted[batted["runs"] >= runs_cutoff]),
        "small_score": win_pct(batted[batted["runs"] < runs_cutoff]),
        "big_haul": win_pct(bowled[bowled["wickets"] >= wickets_cutoff]),
        "small_haul": win_pct(bowled[bowled["wickets"] < wickets_cutoff]),
    }
