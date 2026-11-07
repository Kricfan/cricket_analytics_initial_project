"""
This file combines all data of cricket players in T20 internationals.

Reads every Cricsheet match file in ../t20_jsons and builds one clean,
structured record per player (career batting, bowling and fielding).

Outputs (written to ../output):
    players_combined.json    - one nested, readable record per player
    player_career_stats.csv  - the same data flattened, one row per player
    player_match_stats.csv   - one row per player per match (for analysis)

Uses only the Python standard library. Run with:
    python "combined stats.py"
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = DATA_DIR / "t20_jsons"
OUTPUT_DIR = DATA_DIR / "output"

# Dismissals that are not credited to the bowler.
NOT_BOWLER_WICKETS = {
    "run out", "retired hurt", "retired out", "retired not out",
    "obstructing the field", "timed out", "handled the ball",
}
# Dismissals that leave the batter "not out".
NOT_OUT_KINDS = {"retired hurt", "retired not out"}


def new_match_line():
    """Blank stats for one player in one match."""
    return {
        "batted": False, "runs": 0, "balls_faced": 0, "fours": 0, "sixes": 0,
        "dots_faced": 0, "out": False, "dismissal": "",
        "balls_bowled": 0, "runs_conceded": 0, "wickets": 0, "maidens": 0,
        "dots_bowled": 0, "wides": 0, "no_balls": 0,
        "catches": 0, "stumpings": 0, "run_outs": 0,
    }


def process_match(path):
    """Return (match_info, {player_id: match_line}, {player_id: name})."""
    with open(path, encoding="utf-8") as f:
        match = json.load(f)

    info = match["info"]
    registry = info.get("registry", {}).get("people", {})
    bpo = info.get("balls_per_over", 6)

    def pid(name):
        return registry.get(name, name)

    lines = defaultdict(new_match_line)
    names, teams = {}, {}
    for team, players in info.get("players", {}).items():
        for name in players:
            names[pid(name)] = name
            teams[pid(name)] = team
            lines[pid(name)]  # every listed player played the match

    for innings in match.get("innings", []):
        if innings.get("super_over"):
            continue  # super overs don't count toward official stats

        for over in innings.get("overs", []):
            over_bowlers, over_legal, over_conceded = set(), 0, 0

            for ball in over.get("deliveries", []):
                batter, bowler = pid(ball["batter"]), pid(ball["bowler"])
                runs, extras = ball["runs"], ball.get("extras", {})
                is_wide, is_noball = "wides" in extras, "noballs" in extras
                legal = not is_wide and not is_noball

                lines[batter]["batted"] = True
                lines[pid(ball["non_striker"])]["batted"] = True

                # Batting
                bat = lines[batter]
                bat["runs"] += runs["batter"]
                if not is_wide:
                    bat["balls_faced"] += 1
                    if runs["batter"] == 0:
                        bat["dots_faced"] += 1
                if not ball["runs"].get("non_boundary"):
                    if runs["batter"] == 4:
                        bat["fours"] += 1
                    elif runs["batter"] == 6:
                        bat["sixes"] += 1

                # Bowling (byes, leg byes and penalties aren't charged to
                # the bowler)
                bowl = lines[bowler]
                conceded = (runs["batter"] + extras.get("wides", 0)
                            + extras.get("noballs", 0))
                bowl["runs_conceded"] += conceded
                bowl["wides"] += extras.get("wides", 0)
                bowl["no_balls"] += extras.get("noballs", 0)
                if legal:
                    bowl["balls_bowled"] += 1
                    over_legal += 1
                    if conceded == 0:
                        bowl["dots_bowled"] += 1
                over_bowlers.add(bowler)
                over_conceded += conceded

                # Wickets and fielding
                for wicket in ball.get("wickets", []):
                    kind = wicket["kind"]
                    out = lines[pid(wicket["player_out"])]
                    out["batted"] = True
                    out["dismissal"] = kind
                    if kind not in NOT_OUT_KINDS:
                        out["out"] = True
                    if kind not in NOT_BOWLER_WICKETS:
                        bowl["wickets"] += 1
                    if kind == "caught and bowled":
                        bowl["catches"] += 1
                    for fielder in wicket.get("fielders", []):
                        if "name" not in fielder:
                            continue
                        field = lines[pid(fielder["name"])]
                        if kind == "caught":
                            field["catches"] += 1
                        elif kind == "stumped":
                            field["stumpings"] += 1
                        elif kind == "run out":
                            field["run_outs"] += 1

            maiden = (len(over_bowlers) == 1 and over_legal >= bpo
                      and over_conceded == 0)
            if maiden:
                lines[over_bowlers.pop()]["maidens"] += 1

    outcome = info.get("outcome", {})
    match_info = {
        "match_id": path.stem,
        "date": info.get("dates", [""])[0],
        "season": str(info.get("season", "")),
        "gender": info.get("gender", ""),
        "venue": info.get("venue", ""),
        "city": info.get("city", ""),
        "event": info.get("event", {}).get("name", ""),
        "teams": info.get("teams", []),
        "winner": outcome.get("winner", ""),
        "result": outcome.get("result", ""),
        "player_of_match": [pid(n) for n in info.get("player_of_match", [])],
        "player_teams": teams,
    }
    return match_info, dict(lines), names


def safe_div(a, b, digits=2):
    return round(a / b, digits) if b else None


def overs_from_balls(balls, bpo=6):
    return f"{balls // bpo}.{balls % bpo}"


def build_players():
    files = sorted(JSON_DIR.glob("*.json"))
    print(f"Reading {len(files)} match files from {JSON_DIR} ...")

    players = {}
    match_rows = []

    for i, path in enumerate(files, 1):
        try:
            match, lines, names = process_match(path)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Skipping {path.name}: {e}")
            continue

        for player_id, line in lines.items():
            name = names.get(player_id, player_id)
            team = match["player_teams"].get(player_id, "")
            p = players.setdefault(player_id, {
                "player_id": player_id, "name": name,
                "gender": match["gender"],
                "teams": set(), "match_dates": [], "matches": 0, "won": 0,
                "player_of_match": 0, "innings_batted": 0, "not_outs": 0,
                "highest": (0, False), "fifties": 0, "hundreds": 0, "ducks": 0,
                "innings_bowled": 0, "best_bowling": (0, 0), "three_wkts": 0,
                "five_wkts": 0, "totals": defaultdict(int),
            })
            if team:
                p["teams"].add(team)
                p["matches"] += 1
                p["match_dates"].append(match["date"])
                p["won"] += match["winner"] == team
            p["player_of_match"] += player_id in match["player_of_match"]

            for key in ("runs", "balls_faced", "fours", "sixes", "dots_faced",
                        "balls_bowled", "runs_conceded", "wickets", "maidens",
                        "dots_bowled", "wides", "no_balls", "catches",
                        "stumpings", "run_outs"):
                p["totals"][key] += line[key]
            p["totals"]["dismissals"] += line["out"]

            if line["batted"]:
                p["innings_batted"] += 1
                p["not_outs"] += not line["out"]
                score = (line["runs"], not line["out"])
                if score > p["highest"]:
                    p["highest"] = score
                if line["runs"] >= 100:
                    p["hundreds"] += 1
                elif line["runs"] >= 50:
                    p["fifties"] += 1
                if line["runs"] == 0 and line["out"]:
                    p["ducks"] += 1

            if line["balls_bowled"] or line["runs_conceded"]:
                p["innings_bowled"] += 1
                figs = (line["wickets"], -line["runs_conceded"])
                if p["innings_bowled"] == 1 or figs > p["best_bowling"]:
                    p["best_bowling"] = figs
                if line["wickets"] >= 5:
                    p["five_wkts"] += 1
                elif line["wickets"] >= 3:
                    p["three_wkts"] += 1

            match_rows.append({
                "match_id": match["match_id"], "date": match["date"],
                "season": match["season"], "gender": match["gender"],
                "event": match["event"], "venue": match["venue"],
                "player_id": player_id, "player_name": name, "team": team,
                "opponent": next((t for t in match["teams"] if t != team), ""),
                "team_won": match["winner"] == team,
                "player_of_match": player_id in match["player_of_match"],
                **line,
            })

        if i % 500 == 0:
            print(f"  processed {i} files")

    return players, match_rows


def format_player(p):
    """Turn raw totals into the clean, readable per-player template."""
    t = p["totals"]
    dates = sorted(d for d in p["match_dates"] if d)
    high_runs, high_not_out = p["highest"]
    highest = f"{high_runs}{'*' if high_not_out else ''}"
    best_w, best_r = p["best_bowling"]
    best = f"{best_w}/{-best_r}"

    return {
        "player_id": p["player_id"],
        "name": p["name"],
        "gender": p["gender"],
        "teams": sorted(p["teams"]),
        "career_span": {
            "first_match": dates[0] if dates else None,
            "last_match": dates[-1] if dates else None,
        },
        "matches": p["matches"],
        "matches_won": p["won"],
        "player_of_match_awards": p["player_of_match"],
        "batting": {
            "innings": p["innings_batted"],
            "not_outs": p["not_outs"],
            "runs": t["runs"],
            "balls_faced": t["balls_faced"],
            "highest_score": highest if p["innings_batted"] else None,
            "average": safe_div(t["runs"], t["dismissals"]),
            "strike_rate": safe_div(t["runs"] * 100, t["balls_faced"]),
            "hundreds": p["hundreds"],
            "fifties": p["fifties"],
            "ducks": p["ducks"],
            "fours": t["fours"],
            "sixes": t["sixes"],
            "dot_ball_pct": safe_div(t["dots_faced"] * 100, t["balls_faced"]),
        },
        "bowling": {
            "innings": p["innings_bowled"],
            "balls": t["balls_bowled"],
            "overs": overs_from_balls(t["balls_bowled"]),
            "maidens": t["maidens"],
            "runs_conceded": t["runs_conceded"],
            "wickets": t["wickets"],
            "best_figures": best if p["innings_bowled"] else None,
            "average": safe_div(t["runs_conceded"], t["wickets"]),
            "economy": safe_div(t["runs_conceded"] * 6, t["balls_bowled"]),
            "strike_rate": safe_div(t["balls_bowled"], t["wickets"]),
            "three_wicket_hauls": p["three_wkts"],
            "five_wicket_hauls": p["five_wkts"],
            "dot_balls": t["dots_bowled"],
            "wides": t["wides"],
            "no_balls": t["no_balls"],
        },
        "fielding": {
            "catches": t["catches"],
            "stumpings": t["stumpings"],
            "run_outs": t["run_outs"],
        },
    }


def flatten(record):
    """Nested player record -> single CSV row (batting_runs, ...)."""
    row = {}
    for key, value in record.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                row[f"{key}_{sub_key}"] = sub_value
        elif isinstance(value, list):
            row[key] = "; ".join(value)
        else:
            row[key] = value
    return row


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    players, match_rows = build_players()

    # Drop non-players (e.g. officials never appear in deliveries or squads)
    records = [format_player(p) for p in players.values() if p["matches"]]
    records.sort(key=lambda r: (-r["batting"]["runs"], r["name"]))

    OUTPUT_DIR.mkdir(exist_ok=True)

    json_path = OUTPUT_DIR / "players_combined.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"total_players": len(records), "players": records}, f,
                  indent=2, ensure_ascii=False)

    write_csv(OUTPUT_DIR / "player_career_stats.csv",
              [flatten(r) for r in records])

    match_rows.sort(key=lambda r: (r["date"], r["match_id"], r["team"],
                                   r["player_name"]))
    write_csv(OUTPUT_DIR / "player_match_stats.csv", match_rows)

    print(f"\nDone: {len(records)} players, "
          f"{len(match_rows)} player-match rows")
    print(f"Output written to {OUTPUT_DIR}")
    print("\nTop 5 run scorers:")
    for r in records[:5]:
        b = r["batting"]
        teams = ", ".join(r["teams"])
        print(f"  {r['name']:<20} {teams:<15} {b['runs']:>5} runs  "
              f"avg {b['average']}  SR {b['strike_rate']}")


if __name__ == "__main__":
    main()
