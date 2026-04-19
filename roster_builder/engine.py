from __future__ import annotations
from typing import List, Dict, Tuple
from .models import Player, Team
from .config import get_sport_cfg
import csv
from pathlib import Path


def compute_wpr(player: Player, weights: Dict[str, float]) -> float:
    total = 0.0
    for k, w in weights.items():
        v = player.skills.get(k)
        if v is None:
            continue
        total += v * w
    return total


def _parse_date_safe(raw: str | None):
    from datetime import datetime

    if raw is None:
        return None
    raw = raw.strip()
    if raw == "":
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except Exception:
            continue
    return None


def parse_skills_csv(path: str) -> Dict[str, Player]:
    p = Path(path)
    # first, pick the most recent row per player (by id if present, else name)
    latest_rows: Dict[str, Dict] = {}
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = (row.get("id") or row.get("name") or "").strip()
            name = (row.get("name") or pid).strip()
            raw_date = row.get("date")
            date_obj = _parse_date_safe(raw_date)
            key = pid or name
            prev = latest_rows.get(key)
            if prev is None:
                latest_rows[key] = {"row": row, "date": date_obj}
            else:
                prev_date = prev.get("date")
                # if new date is None, keep prev; if prev is None and new exists -> replace
                if date_obj is None and prev_date is None:
                    # keep first encountered
                    continue
                if date_obj is None:
                    continue
                if prev_date is None or date_obj >= prev_date:
                    latest_rows[key] = {"row": row, "date": date_obj}

    players: Dict[str, Player] = {}
    for key, info in latest_rows.items():
        row = info["row"]
        pid = (row.get("id") or row.get("name") or key).strip()
        name = (row.get("name") or pid).strip()
        skills = {}
        incomplete = False
        for skill in ("setter", "passer", "attack", "serve"):
            raw = row.get(skill)
            if raw is None or raw.strip() == "":
                skills[skill] = None
                incomplete = True
            else:
                try:
                    skills[skill] = float(raw)
                except Exception:
                    skills[skill] = None
                    incomplete = True

        players[str(pid)] = Player(id=str(pid), name=name, skills=skills, incomplete_skills=incomplete)

    return players


def parse_availability(path: str) -> List[str]:
    """Parse a simple availability input file or list.

    Supports:
    - CSV/TSV with header containing 'name' or 'id'
    - plain text one name per line
    - a single comma-separated line
    Returns list of strings (names or ids)
    """
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    # try CSV
    try:
        with p.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and ("name" in reader.fieldnames or "id" in reader.fieldnames):
                items = []
                for row in reader:
                    val = (row.get("name") or row.get("id") or "").strip()
                    if val:
                        items.append(val)
                return items
    except Exception:
        pass

    # fallback: lines or comma-separated
    if "\n" in text:
        return [line.strip() for line in text.splitlines() if line.strip()]
    if "," in text:
        return [s.strip() for s in text.split(",") if s.strip()]
    return [text]


def assemble_players_from_history_and_availability(skills_csv: str, availability_path: str) -> List[Player]:
    """Construct today's player list by matching availability entries to history.

    If a name/id in availability is not found in the history CSV, a placeholder Player
    with incomplete skills is created.
    """
    history = parse_skills_csv(skills_csv)
    available = parse_availability(availability_path)
    players: List[Player] = []
    for entry in available:
        key = entry.strip()
        p = history.get(key)
        if p is None:
            # try matching by name (case-insensitive)
            for h in history.values():
                if h.name.lower() == key.lower():
                    p = h
                    break
        if p is None:
            # placeholder with unknown skills
            players.append(Player(id=None, name=key, skills={k: None for k in ("setter", "passer", "attack", "serve")}, incomplete_skills=True))
        else:
            players.append(p)
    return players


def build_teams(
    players: List[Player],
    sport_cfg: Dict,
    team_size: int | None = None,
) -> Tuple[List[Team], List[str]]:
    warnings: List[str] = []
    weights = sport_cfg.get("weights", {})
    thresholds = sport_cfg.get("specialist_thresholds", {})
    rules = sport_cfg.get("team_rules", {})

    num_players = len(players)
    # rule: if players > threshold -> change num_teams
    num_teams = 2
    for th in rules.get("players_thresholds", []):
        if num_players > int(th.get("players", 0)):
            num_teams = int(th.get("teams_when_exceeded", 2))

    if team_size is None:
        team_size = rules.get("default_team_size", 6)

    # Compute balanced target sizes so we assign all players.
    base = num_players // num_teams if num_teams > 0 else num_players
    remainder = num_players % num_teams if num_teams > 0 else 0
    target_sizes = [base + (1 if i < remainder else 0) for i in range(num_teams)]

    # Create initial empty teams
    teams = [Team(id=i) for i in range(num_teams)]

    # compute WPRs and identify specialists. Also compute reliability-adjusted scores.
    player_scores = []
    specialists = {role: [] for role in thresholds.keys()}
    for p in players:
        wpr = compute_wpr(p, weights)
        total_skills = max(len(weights), 1)
        known = sum(1 for k in weights.keys() if p.skills.get(k) is not None)
        reliability = known / total_skills
        effective = wpr * reliability
        player_scores.append((p, wpr, effective))
        for role, th in thresholds.items():
            val = p.skills.get(role)
            if val is not None and val >= float(th):
                specialists[role].append((p, wpr))
        if p.incomplete_skills:
            warnings.append(f"player '{p.name}' has missing skill values")

    # Seed specialists round-robin per role, but ensure each player is assigned once
    assigned_ids = set()
    for role, s_list in specialists.items():
        s_list_sorted = sorted(s_list, key=lambda x: x[1], reverse=True)
        for idx, (p, score) in enumerate(s_list_sorted):
            pid = p.id or p.name
            if pid in assigned_ids:
                continue
            # try to place this specialist starting at a rotating offset to spread them
            start = idx % len(teams)
            placed = False
            for offset in range(len(teams)):
                team_idx = (start + offset) % len(teams)
                if len(teams[team_idx].players) < target_sizes[team_idx]:
                    teams[team_idx].players.append(p)
                    assigned_ids.add(pid)
                    placed = True
                    break
            if not placed:
                # no room in any team during seeding, skip
                continue

    # Remaining players: sort by WPR desc and fill weakest team
    assigned = {p.id or p.name for t in teams for p in t.players}
    remaining = [(p, raw, eff) for (p, raw, eff) in player_scores if (p.id or p.name) not in assigned]
    # sort by effective score (prefer reliable players)
    remaining_sorted = sorted(remaining, key=lambda x: x[2], reverse=True)

    def team_total(t: Team) -> float:
        return sum(compute_wpr(p, weights) for p in t.players)

    for p, raw, eff in remaining_sorted:
        teams_sorted_idx = sorted(range(len(teams)), key=lambda i: (team_total(teams[i]), len(teams[i].players)))
        placed = False
        for idx in teams_sorted_idx:
            if len(teams[idx].players) < target_sizes[idx]:
                teams[idx].players.append(p)
                placed = True
                break
        if not placed:
            warnings.append(f"player '{p.name}' could not be assigned (unexpected)")

    # finalize team scores and coverage
    for t in teams:
        t.total_score = team_total(t)
        coverage = {}
        for role in thresholds.keys():
            coverage[role] = any((p.skills.get(role) or 0) >= float(thresholds[role]) for p in t.players)
        t.role_coverage = coverage
        for role, covered in coverage.items():
            if not covered:
                warnings.append(f"team {t.id} missing specialist for role '{role}'")

    return teams, warnings
