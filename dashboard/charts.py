"""
Plotly chart builders for the cricket dashboard.

Each function receives a summary DataFrame from ``analysis.py`` and
returns a ready-to-display Plotly figure. All charts share one dark
theme (defined at the top of this file) so the dashboard looks
consistent.
"""

import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Theme colours
# ---------------------------------------------------------------------------

SURFACE = "#1a1a19"         # chart background (matches Streamlit cards)
TEXT_PRIMARY = "#f0efec"
TEXT_MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
NEUTRAL = "#5c5b57"         # for "everything else" categories

# Fixed colours per entity, so a series keeps its colour on every chart.
BLUE = "#3987e5"
ORANGE = "#d95926"
AQUA = "#199e70"

GENDER_COLOURS = {"Men": BLUE, "Women": ORANGE}
ARCHETYPE_COLOURS = {
    "Elite": AQUA,
    "Anchor": BLUE,
    "Aggressor": ORANGE,
    "Developing": NEUTRAL,
}
YES_NO_COLOURS = {"Yes": BLUE, "No": NEUTRAL}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def style_figure(fig, title=None, height=380):
    """Apply the shared dark theme to any Plotly figure."""
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": TEXT_PRIMARY},
               "x": 0, "xanchor": "left"} if title else None,
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "color": TEXT_MUTED, "size": 12},
        margin={"l": 10, "r": 20, "t": 50 if title else 20, "b": 10},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom",
                "x": 1, "xanchor": "right", "title": None,
                "font": {"color": TEXT_PRIMARY}},
        hoverlabel={"bgcolor": "#0d0d0d", "bordercolor": AXIS,
                    "font": {"family": FONT, "color": TEXT_PRIMARY}},
        bargap=0.25,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False,
                     title_font={"color": TEXT_MUTED})
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False,
                     title_font={"color": TEXT_MUTED})
    return fig


# ---------------------------------------------------------------------------
# Overview charts
# ---------------------------------------------------------------------------

def trend_line(trends, column, title, y_label):
    """Line chart of one yearly trend, with one line per gender."""
    fig = px.line(
        trends, x="year", y=column, color="gender_label",
        color_discrete_map=GENDER_COLOURS, markers=True,
        labels={"year": "Year", column: y_label, "gender_label": "Gender"},
        custom_data=["matches"],
    )
    fig.update_traces(
        line={"width": 2}, marker={"size": 8},
        hovertemplate=(f"<b>%{{x}}</b><br>{y_label}: %{{y}}"
                       "<br>Matches: %{customdata[0]}<extra></extra>"),
    )
    fig.update_layout(hovermode="x unified")
    return style_figure(fig, title)


# ---------------------------------------------------------------------------
# Leaderboard charts
# ---------------------------------------------------------------------------

def leaderboard_bar(data, value, label, title):
    """
    Horizontal bar chart of the top players for one statistic.

    Bars are coloured by gender; the legend is hidden when only one
    gender is on the chart.
    """
    fig = px.bar(
        data, x=value, y="name", color="gender", orientation="h",
        color_discrete_map=GENDER_COLOURS, text=value,
        custom_data=["team", "matches"],
        labels={value: label, "name": "", "gender": "Gender"},
    )
    fig.update_traces(
        marker={"cornerradius": 4}, textposition="outside",
        textfont={"color": TEXT_PRIMARY}, cliponaxis=False,
        hovertemplate=(f"<b>%{{y}}</b> (%{{customdata[0]}})<br>"
                       f"{label}: %{{x}}<br>Matches: %{{customdata[1]}}"
                       "<extra></extra>"),
    )
    # Sort by value so the largest bar sits at the top.
    fig.update_yaxes(categoryorder="total ascending",
                     tickfont={"color": TEXT_PRIMARY})
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_layout(showlegend=data["gender"].nunique() > 1)
    return style_figure(fig, title, height=max(380, 26 * len(data)))


def archetype_scatter(batters, median_avg, median_sr):
    """
    Batting average vs strike rate, coloured by batter archetype.

    Dashed lines mark the medians that split players into the four
    archetypes; bubble size shows total runs.
    """
    fig = px.scatter(
        batters, x="strike_rate", y="average", color="archetype",
        size="runs", size_max=28,
        color_discrete_map=ARCHETYPE_COLOURS,
        category_orders={"archetype": list(ARCHETYPE_COLOURS)},
        custom_data=["name", "team", "runs", "innings"],
        labels={"strike_rate": "Strike rate", "average": "Average",
                "archetype": "Archetype"},
    )
    fig.update_traces(
        marker={"line": {"width": 1, "color": SURFACE}, "opacity": 0.85},
        hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                       "Average: %{y}<br>Strike rate: %{x}<br>"
                       "Runs: %{customdata[2]} in %{customdata[3]} innings"
                       "<extra></extra>"),
    )
    for line_args in ({"x": median_sr}, {"y": median_avg}):
        add_line = fig.add_vline if "x" in line_args else fig.add_hline
        add_line(**line_args, line_dash="dash", line_color=TEXT_MUTED,
                 line_width=1)
    return style_figure(fig, "Batting average vs strike rate", height=480)


def bowler_scatter(bowlers):
    """Economy vs bowling strike rate - bottom-left is best."""
    fig = px.scatter(
        bowlers, x="bowling_strike_rate", y="economy", color="gender",
        size="wickets", size_max=28, color_discrete_map=GENDER_COLOURS,
        custom_data=["name", "team", "wickets", "bowling_average"],
        labels={"bowling_strike_rate": "Balls per wicket",
                "economy": "Economy (runs per over)", "gender": "Gender"},
    )
    fig.update_traces(
        marker={"line": {"width": 1, "color": SURFACE}, "opacity": 0.85},
        hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                       "Wickets: %{customdata[2]}<br>"
                       "Economy: %{y}<br>Balls per wicket: %{x}<br>"
                       "Average: %{customdata[3]}<extra></extra>"),
    )
    return style_figure(fig, "Economy vs strike rate (bottom-left is best)",
                        height=480)


# ---------------------------------------------------------------------------
# Team charts
# ---------------------------------------------------------------------------

def team_win_bar(records, top_n=15):
    """Win percentage of the most successful teams."""
    data = records.head(top_n).sort_values("win_pct")
    labels = data["team"] + " (" + data["gender"] + ")"
    colours = data["gender"].map(GENDER_COLOURS)
    fig = go.Figure(go.Bar(
        x=data["win_pct"], y=labels, orientation="h",
        marker={"color": colours, "cornerradius": 4},
        text=data["win_pct"].map("{:.0f}%".format), textposition="outside",
        textfont={"color": TEXT_PRIMARY},
        customdata=data[["wins", "matches"]],
        hovertemplate=("<b>%{y}</b><br>Win rate: %{x}%<br>"
                       "%{customdata[0]} wins from %{customdata[1]} matches"
                       "<extra></extra>"),
    ))
    fig.update_xaxes(title="Win %", range=[0, 100], showgrid=False,
                     showticklabels=False)
    fig.update_yaxes(tickfont={"color": TEXT_PRIMARY})
    return style_figure(fig, "Highest win rates (decided matches)",
                        height=max(380, 28 * len(data)))


def winning_factors_bar(factors):
    """Grouped bars: team win % with vs without a standout performance."""
    fig = px.bar(
        factors, x="factor", y="win_pct", color="happened",
        barmode="group", color_discrete_map=YES_NO_COLOURS,
        text=factors["win_pct"].map("{:.0f}%".format),
        custom_data=["team_innings"],
        labels={"factor": "", "win_pct": "Team win %",
                "happened": "Happened?"},
    )
    fig.update_traces(
        marker={"cornerradius": 4}, textposition="outside",
        textfont={"color": TEXT_PRIMARY},
        hovertemplate=("Win rate: %{y}%<br>From %{customdata[0]:,} "
                       "team innings<extra></extra>"),
    )
    fig.update_yaxes(range=[0, 100])
    fig.update_xaxes(tickfont={"color": TEXT_PRIMARY, "size": 13})
    return style_figure(fig, "Does one standout performance win matches?")


# ---------------------------------------------------------------------------
# Player charts
# ---------------------------------------------------------------------------

def player_form_chart(innings, window=10):
    """Runs in each innings (bars) with a rolling-average form line."""
    fig = go.Figure()
    fig.add_bar(
        x=innings["innings_number"], y=innings["runs"], name="Runs",
        marker={"color": NEUTRAL, "cornerradius": 2},
        customdata=innings[["opponent", "date"]],
        hovertemplate=("Innings %{x} vs %{customdata[0]}<br>"
                       "%{customdata[1]|%d %b %Y}<br>Runs: %{y}"
                       "<extra></extra>"),
    )
    fig.add_scatter(
        x=innings["innings_number"], y=innings["rolling_avg"],
        name=f"{window}-innings average", mode="lines",
        line={"color": BLUE, "width": 2},
        hovertemplate="Form (avg): %{y}<extra></extra>",
    )
    fig.update_xaxes(title="Innings number")
    fig.update_yaxes(title="Runs")
    return style_figure(fig, "Innings-by-innings form")


def cumulative_runs_chart(innings):
    """Career runs adding up over time."""
    fig = px.area(innings, x="date", y="cumulative_runs",
                  labels={"date": "", "cumulative_runs": "Career runs"})
    fig.update_traces(
        line={"color": BLUE, "width": 2},
        fillcolor="rgba(57, 135, 229, 0.18)",
        hovertemplate="%{x|%d %b %Y}<br>Career runs: %{y:,}<extra></extra>",
    )
    return style_figure(fig, "Career runs over time")


def dismissal_bar(dismissals):
    """How the player gets out, most common first."""
    data = dismissals.sort_values("count")
    fig = go.Figure(go.Bar(
        x=data["count"], y=data["dismissal"].str.capitalize(),
        orientation="h", marker={"color": ORANGE, "cornerradius": 4},
        text=data["count"], textposition="outside",
        textfont={"color": TEXT_PRIMARY},
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_yaxes(tickfont={"color": TEXT_PRIMARY})
    return style_figure(fig, "How they get out")


def opponent_bar(by_opponent, value, label, title, gender):
    """One statistic for the player against each opponent."""
    data = by_opponent[by_opponent[value] > 0].nlargest(12, value)
    # Reuse the leaderboard layout, with opponents in place of players.
    return leaderboard_bar(
        data.assign(name=data["opponent"], team=data["opponent"],
                    gender=gender),
        value, label, title,
    )
