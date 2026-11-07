"""
T20 International Cricket Analytics - Streamlit dashboard.

Run from the project folder with:
    streamlit run dashboard/app.py

The page is split into five tabs:
    Overview  - headline numbers and how T20 batting has evolved
    Batting   - run-scorer leaderboard and batter archetypes
    Bowling   - wicket-taker leaderboard and economy analysis
    Teams     - team win rates and what wins matches
    Player    - an in-depth profile of any single player
"""

import pandas as pd
import streamlit as st

import analysis
import charts
from data_loader import (CAREER_STATS_FILE, data_files_exist,
                         load_career_stats, load_match_stats)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="T20I Cricket Analytics",
    page_icon="🏏",
    layout="wide",
)

# Small CSS tweaks: tighter top padding and a coloured accent on the
# headline metric cards.
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    [data-testid="stMetric"] {
        background: #1a1a19;
        border-left: 3px solid #3987e5;
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .insight {
        background: #1a1a19;
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
        margin: 0.25rem 0 1rem 0;
        color: #c3c2b7;
    }
    .insight b { color: #f0efec; }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_chart(fig):
    """Display a Plotly figure at the full width of its column."""
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False})


def insight(text):
    """Show a highlighted one-line finding beneath a chart."""
    st.markdown(f'<div class="insight">💡 {text}</div>',
                unsafe_allow_html=True)


def compact(number):
    """Shorten large numbers so they fit a metric card (1331673 -> 1.33M)."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    return f"{number:,}"


def fmt(value, suffix=""):
    """Format a number for display, showing a dash for missing values."""
    if value is None or pd.isna(value):
        return "–"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value:,}{suffix}"


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

if not data_files_exist():
    st.error(
        f"Combined data not found in `{CAREER_STATS_FILE.parent}`.\n\n"
        "Run `python \"data/python files/combined stats.py\"` first to "
        "build it from the match JSON files."
    )
    st.stop()

all_matches = load_match_stats()
career = load_career_stats()

# ---------------------------------------------------------------------------
# Sidebar filters - these apply to every tab
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("🏏 Filters")

    genders = st.multiselect("Gender", ["Men", "Women"],
                             default=["Men", "Women"])

    min_year = int(all_matches["year"].min())
    max_year = int(all_matches["year"].max())
    year_range = st.slider("Seasons", min_year, max_year,
                           (min_year, max_year))

    all_teams = sorted(all_matches["team"].unique())
    teams = st.multiselect("Teams (leave empty for all)", all_teams)

    st.caption(
        "Data: ball-by-ball T20 internationals from Cricsheet, combined "
        "into per-player stats."
    )

if not genders:
    st.warning("Pick at least one gender in the sidebar.")
    st.stop()

matches = analysis.filter_matches(all_matches, genders, year_range, teams)
if matches.empty:
    st.warning("No matches fit these filters - try widening them.")
    st.stop()

# Player totals for the filtered period, shared by several tabs.
players = analysis.aggregate_players(matches)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("T20 International Cricket Analytics")
st.caption(
    f"{', '.join(genders)} · {year_range[0]}–{year_range[1]}"
    + (f" · {', '.join(teams)}" if teams else " · all teams")
)

tab_overview, tab_bat, tab_bowl, tab_teams, tab_player = st.tabs(
    ["📈 Overview", "🏏 Batting", "🎯 Bowling", "🌍 Teams", "👤 Player"]
)

# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------

with tab_overview:
    kpis = analysis.headline_kpis(matches)
    cols = st.columns(6)
    cols[0].metric("Matches", f"{kpis['matches']:,}")
    cols[1].metric("Players", f"{kpis['players']:,}")
    cols[2].metric("Runs", compact(kpis["runs"]))
    cols[3].metric("Wickets", f"{kpis['wickets']:,}")
    cols[4].metric("Sixes", f"{kpis['sixes']:,}")
    cols[5].metric("50+ scores", f"{kpis['fifties']:,}")

    st.subheader("How has T20 batting evolved?")
    st.caption(
        "From 2019 every ICC member was given full T20I status, so many "
        "more matches involve smaller nations. That pulls the averages "
        "down - filter to a few teams in the sidebar for a like-for-like "
        "comparison."
    )
    trends = analysis.yearly_trends(matches)

    if trends.empty:
        st.info("Not enough matches per year to show trends.")
    else:
        left, right = st.columns(2)
        with left:
            show_chart(charts.trend_line(
                trends, "strike_rate", "Batting strike rate by year",
                "Strike rate"))
        with right:
            show_chart(charts.trend_line(
                trends, "boundary_pct", "Share of runs from boundaries",
                "Boundary %"))

        left, right = st.columns(2)
        with left:
            show_chart(charts.trend_line(
                trends, "runs_per_innings",
                "Average team runs per innings", "Runs"))
        with right:
            show_chart(charts.trend_line(
                trends, "sixes_per_match", "Sixes hit per match", "Sixes"))

        # Turn the strike-rate trend into a plain-English finding.
        for gender in genders:
            change = analysis.trend_change(trends, "strike_rate", gender)
            if change:
                first_year, first_sr, last_year, last_sr = change
                pct = (last_sr - first_sr) / first_sr * 100
                direction = "faster" if pct >= 0 else "slower"
                insight(
                    f"<b>{gender}:</b> batters scored at a strike rate of "
                    f"<b>{first_sr:.1f}</b> in {first_year} and "
                    f"<b>{last_sr:.1f}</b> in {last_year} - "
                    f"{abs(pct):.0f}% {direction}."
                )

# ---------------------------------------------------------------------------
# Tab 2: Batting
# ---------------------------------------------------------------------------

with tab_bat:
    min_innings = st.slider("Minimum innings to qualify", 5, 100, 20,
                            key="bat_min")

    top_batters = analysis.batting_leaderboard(players, min_innings)
    show_chart(charts.leaderboard_bar(top_batters, "runs", "Runs",
                                      "Most runs"))

    st.subheader("What kind of batter are they?")
    st.caption(
        "Each qualified batter is compared with the median player. The "
        "dashed lines split them into four archetypes: **Elite** (high "
        "average & strike rate), **Anchor** (reliable but slower), "
        "**Aggressor** (fast but less consistent) and **Developing**."
    )
    batters, median_avg, median_sr = analysis.batter_archetypes(
        players, min_innings)

    if batters.empty:
        st.info("No batters qualify - lower the minimum innings.")
    else:
        show_chart(charts.archetype_scatter(batters, median_avg, median_sr))

        elite = batters[batters["archetype"] == "Elite"]
        insight(
            f"The median qualified batter averages <b>{median_avg:.1f}</b> "
            f"at a strike rate of <b>{median_sr:.1f}</b>. "
            f"<b>{len(elite)}</b> of {len(batters)} batters beat both - "
            "the top run scorer among them is "
            f"<b>{elite.nlargest(1, 'runs')['name'].iloc[0]}</b>."
            if not elite.empty else
            "No batter beats the median on both average and strike rate."
        )

        st.dataframe(
            top_batters[["name", "team", "matches", "innings", "runs",
                         "highest", "average", "strike_rate", "fifties",
                         "hundreds", "fours", "sixes"]],
            hide_index=True, width="stretch",
            column_config={
                "name": "Player", "team": "Team",
                "strike_rate": st.column_config.NumberColumn(
                    "Strike rate", format="%.1f"),
                "average": st.column_config.NumberColumn(
                    "Average", format="%.1f"),
                "highest": "HS", "fifties": "50s", "hundreds": "100s",
                "fours": "4s", "sixes": "6s",
            },
        )

# ---------------------------------------------------------------------------
# Tab 3: Bowling
# ---------------------------------------------------------------------------

with tab_bowl:
    min_overs = st.slider("Minimum overs to qualify", 10, 300, 50,
                          key="bowl_min")

    top_bowlers = analysis.bowling_leaderboard(players, min_overs)
    show_chart(charts.leaderboard_bar(top_bowlers, "wickets", "Wickets",
                                      "Most wickets"))

    qualified = players[
        (players["balls_bowled"] >= min_overs * 6) & (players["wickets"] > 0)
    ]
    if qualified.empty:
        st.info("No bowlers qualify - lower the minimum overs.")
    else:
        show_chart(charts.bowler_scatter(qualified))

        best_econ = qualified.nsmallest(1, "economy").iloc[0]
        best_sr = qualified.nsmallest(1, "bowling_strike_rate").iloc[0]
        insight(
            f"Most economical: <b>{best_econ['name']}</b> "
            f"({best_econ['economy']:.2f} runs per over). "
            f"Quickest wicket-taker: <b>{best_sr['name']}</b> "
            f"(a wicket every {best_sr['bowling_strike_rate']:.1f} balls)."
        )

        st.dataframe(
            top_bowlers[["name", "team", "matches", "wickets", "economy",
                         "bowling_average", "bowling_strike_rate",
                         "maidens"]],
            hide_index=True, width="stretch",
            column_config={
                "name": "Player", "team": "Team",
                "economy": st.column_config.NumberColumn(
                    "Economy", format="%.2f"),
                "bowling_average": st.column_config.NumberColumn(
                    "Average", format="%.1f"),
                "bowling_strike_rate": st.column_config.NumberColumn(
                    "Balls / wkt", format="%.1f"),
            },
        )

# ---------------------------------------------------------------------------
# Tab 4: Teams
# ---------------------------------------------------------------------------

with tab_teams:
    # Team results ignore the team filter so win rates compare everyone.
    period = analysis.filter_matches(all_matches, genders, year_range)

    # A minimum stops teams with only a few games topping the table.
    min_team_matches = st.slider("Minimum decided matches", 10, 200, 50,
                                 key="team_min")
    records = analysis.team_records(period, min_team_matches)

    left, right = st.columns(2)
    with left:
        if records.empty:
            st.info(f"No team has {min_team_matches}+ decided matches in "
                    "this period.")
        else:
            show_chart(charts.team_win_bar(records))
    with right:
        factors = analysis.match_winning_factors(period)
        show_chart(charts.winning_factors_bar(factors))

        fifty = factors[factors["factor"] == "A batter scores 50+"]
        yes_pct = fifty.loc[fifty["happened"] == "Yes", "win_pct"].iloc[0]
        no_pct = fifty.loc[fifty["happened"] == "No", "win_pct"].iloc[0]
        insight(
            f"Teams with a half-centurion win <b>{yes_pct:.0f}%</b> of "
            f"the time, compared with <b>{no_pct:.0f}%</b> when nobody "
            "reaches 50."
        )

    if not records.empty:
        st.dataframe(
            records, hide_index=True, width="stretch",
            column_config={
                "team": "Team", "gender": "Gender",
                "matches": "Decided matches", "wins": "Wins",
                "win_pct": st.column_config.ProgressColumn(
                    "Win %", format="%.1f%%", min_value=0, max_value=100),
            },
        )

# ---------------------------------------------------------------------------
# Tab 5: Player explorer
# ---------------------------------------------------------------------------

with tab_player:
    # List players by runs so the best-known names appear first.
    options = players.sort_values("runs", ascending=False)
    labels = dict(zip(options["player_id"],
                      options["name"] + " (" + options["team"] + ")"))
    player_id = st.selectbox("Choose a player", list(labels),
                             format_func=labels.get)

    profile = career[career["player_id"] == player_id].iloc[0]
    st.subheader(f"{profile['name']}  ·  {profile['teams']}")
    st.caption(
        f"All-time T20I career: {profile['career_span_first_match']} to "
        f"{profile['career_span_last_match']} · "
        f"{profile['player_of_match_awards']} player-of-the-match awards"
    )

    # Career cards always show the full career, whatever the filters.
    cols = st.columns(6)
    cols[0].metric("Matches", fmt(profile["matches"]))
    cols[1].metric("Runs", fmt(profile["batting_runs"]))
    cols[2].metric("Bat average", fmt(profile["batting_average"]))
    cols[3].metric("Strike rate", fmt(profile["batting_strike_rate"]))
    cols[4].metric("Wickets", fmt(profile["bowling_wickets"]))
    cols[5].metric("Economy", fmt(profile["bowling_economy"]))

    st.caption("Charts below use the sidebar filters.")
    innings = analysis.player_innings(matches, player_id)

    if innings.empty:
        st.info("This player did not bat in the filtered matches.")
    else:
        left, right = st.columns(2)
        with left:
            show_chart(charts.player_form_chart(innings))
        with right:
            show_chart(charts.cumulative_runs_chart(innings))

    # How much does this player's performance swing the result?
    impact = analysis.player_win_impact(matches, player_id)
    st.subheader("Impact on team results")
    cols = st.columns(3)
    cols[0].metric("Team win % (all matches)", fmt(impact["overall"], "%"))
    if impact["big_score"] is not None and impact["small_score"] is not None:
        cols[1].metric(
            "Win % when they score 30+", fmt(impact["big_score"], "%"),
            delta=f"{impact['big_score'] - impact['small_score']:+.1f} pts "
                  "vs under 30",
        )
    if impact["big_haul"] is not None and impact["small_haul"] is not None:
        cols[2].metric(
            "Win % when they take 2+ wickets", fmt(impact["big_haul"], "%"),
            delta=f"{impact['big_haul'] - impact['small_haul']:+.1f} pts "
                  "vs fewer",
        )

    by_opponent = analysis.player_by_opponent(matches, player_id)
    dismissals = analysis.player_dismissals(matches, player_id)

    left, right = st.columns(2)
    gender = profile["gender_label"]
    with left:
        if by_opponent["runs"].sum() > 0:
            show_chart(charts.opponent_bar(
                by_opponent, "runs", "Runs", "Runs against each opponent",
                gender))
        elif by_opponent["wickets"].sum() > 0:
            show_chart(charts.opponent_bar(
                by_opponent, "wickets", "Wickets",
                "Wickets against each opponent", gender))
    with right:
        if not dismissals.empty:
            show_chart(charts.dismissal_bar(dismissals))

    with st.expander("Full record by opponent"):
        st.dataframe(
            by_opponent, hide_index=True, width="stretch",
            column_config={
                "opponent": "Opponent", "balls": "Balls faced",
                "outs": "Dismissals", "balls_bowled": "Balls bowled",
                "runs_conceded": "Runs conceded",
            },
        )
