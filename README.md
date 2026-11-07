# cricket_analytics_initial_project
My first data analytics project about cricket

Ball-by-ball data from every men's and women's T20 international is combined
into per-player statistics, then explored in an interactive Streamlit
dashboard.

## What's inside

| Path | Purpose |
|---|---|
| `data/python files/combined stats.py` | Combines the match JSON files into player stats (`data/output/`) |
| `dashboard/data_loader.py` | Loads the combined CSV files |
| `dashboard/analysis.py` | All the analysis (pandas) |
| `dashboard/charts.py` | Plotly chart builders |
| `dashboard/app.py` | The Streamlit dashboard |

The dashboard has five tabs: **Overview** (how T20 batting has changed),
**Batting** (leaderboard and batter types), **Bowling**, **Teams** (win
rates and what wins matches) and **Player** (a profile of any player).

## Setup

1. Install the packages (Python 3.10+):

   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt
   ```

2. Download the T20 international JSON files from
   [cricsheet.org](https://cricsheet.org/downloads/) and unzip them into
   `data/t20_jsons/`. (They aren't in the repository because they're
   about 470 MB.)

3. Build the combined player stats:

   ```bash
   python "data/python files/combined stats.py"
   ```

4. Start the dashboard:

   ```bash
   .venv/Scripts/streamlit run dashboard/app.py
   ```

On macOS or Linux, use `.venv/bin/` instead of `.venv/Scripts/`.

Data: [Cricsheet](https://cricsheet.org/), licensed under ODC-BY.
