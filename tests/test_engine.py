from roster_builder.engine import parse_skills_csv, build_teams, parse_availability, assemble_players_from_history_and_availability
from roster_builder.config import load_sports_config, get_sport_cfg
from pathlib import Path


CFG_PATH = "config/sports.yaml"


def test_happy_path(tmp_path):
    cfg = load_sports_config(CFG_PATH)
    sport = get_sport_cfg(cfg, "volleyball")
    players = list(parse_skills_csv("examples/sample_players.csv").values())
    teams, warnings = build_teams(players, sport)
    # with 19 players and threshold rule >17, expect 3 teams
    assert len(teams) == 3
    total_assigned = sum(len(t.players) for t in teams)
    assert total_assigned <= len(players)


def test_incomplete_skills_flag(tmp_path):
    # create a temporary CSV with missing skills
    p = tmp_path / "tmp.csv"
    p.write_text("id,name,date,setter,passer,attack,serve\n1,NoSkills,2026-04-02,,,,\n")
    players = list(parse_skills_csv(str(p)).values())
    assert players[0].incomplete_skills is True


def test_parse_availability(tmp_path):
    p = tmp_path / "avail.txt"
    p.write_text("Alice,Bob,Charlie\n")
    items = parse_availability(str(p))
    assert items == ["Alice", "Bob", "Charlie"]


def test_assemble_players_and_assignment(tmp_path):
    cfg = load_sports_config(CFG_PATH)
    sport = get_sport_cfg(cfg, "volleyball")
    # use the sample availability file we added
    players = assemble_players_from_history_and_availability("examples/sample_players.csv", "examples/sample_availability.txt")
    # we expect 19 available players
    assert len(players) == 19
    teams, warnings = build_teams(players, sport)
    # should create 3 teams and assign everyone
    assert len(teams) == 3
    total_assigned = sum(len(t.players) for t in teams)
    assert total_assigned == 19


def test_date_selection(tmp_path):
    # ensure parse_skills_csv picks the latest record by date
    p = tmp_path / "hist.csv"
    p.write_text("id,name,date,setter,passer,attack,serve\n1,Alice,2026-01-01,5,5,5,5\n1,Alice,2026-04-01,8,8,8,8\n")
    players = parse_skills_csv(str(p))
    assert players["1"].skills["setter"] == 8.0
