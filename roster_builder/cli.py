from __future__ import annotations
import argparse
from .config import load_sports_config, get_sport_cfg
from .engine import parse_skills_csv, build_teams, assemble_players_from_history_and_availability


def main(argv=None):
    p = argparse.ArgumentParser(prog="roster-builder")
    p.add_argument("--config", default="config/sports.yaml")
    p.add_argument("--sport", default="volleyball")
    p.add_argument("--skills-csv", required=True)
    p.add_argument("--availability", required=False, help="Path to today's availability (CSV/text) - if provided, only those players will be considered")
    args = p.parse_args(argv)

    cfg = load_sports_config(args.config)
    sport = get_sport_cfg(cfg, args.sport)

    if args.availability:
        players = assemble_players_from_history_and_availability(args.skills_csv, args.availability)
    else:
        players_map = parse_skills_csv(args.skills_csv)
        players = list(players_map.values())

    teams, warnings = build_teams(players, sport)

    for t in teams:
        print(f"Team {t.id}:")
        for pl in t.players:
            print(f"  - {pl.name} (incomplete={pl.incomplete_skills})")
        print(f"  total_score={t.total_score:.2f}")
        print(f"  coverage={t.role_coverage}")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(" - ", w)


if __name__ == "__main__":
    main()
