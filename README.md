# roaster-builder

An algorithmic team balancer for recreational sports groups.

This repository contains a small, extensible engine that builds balanced teams from an availability list and historical skill records. It was designed for volleyball initially but is configurable for other sports via a YAML config.

## Architecture

- config/
  - `sports.yaml` — sport definitions (skills, weights, specialist thresholds, team rules).
- `roster_builder/` (package)
  - `config.py` — YAML loader and helpers
  - `models.py` — Player and Team dataclasses
  - `engine.py` — main algorithm: CSV parsing, WPR calculation, seeding, greedy fill, coverage/warnings
  - `cli.py` — small CLI to run the engine against a CSV and config
- `examples/` — sample CSV inputs
- `tests/` — unit tests (pytest)

The engine is synchronous and intentionally lightweight so it can be embedded in a CLI, web service, or a webhook adapter (for WhatsApp/Twilio integration later).

## How to run (development)

1. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

3. Run tests:

```bash
python -m pytest -q
```

4. Run the CLI against the sample CSV:

```bash
python -m roster_builder.cli --skills-csv examples/sample_players.csv
```

This will load the `config/sports.yaml` config, parse `examples/sample_players.csv` and print team assignments and warnings.

## Inputs

- Player skill history CSV (example header): `id,name,date,setter,passer,attack,serve`.
  - When multiple rows exist for the same `id` or `name`, the parser picks the most recent record using the `date` column (ISO `YYYY-MM-DD` preferred). Other common formats are also attempted.
  - If a player's skill cell is empty or non-numeric, the engine marks that player as having `incomplete_skills` and includes a warning.
 - Player skill history CSV (example header): `id,name,date,setter,passer,attack,serve`.
	 - Note: the current CSV parser in `roster_builder.engine` expects the volleyball schema and uses the fixed column names `setter`, `passer`, `attack`, and `serve`. If you add a new sport with different skill names in `config/sports.yaml`, the CSV parser will need to be updated to read those columns (this is listed as an extensibility improvement below).
	 - When multiple rows exist for the same `id` or `name`, the parser picks the most recent record using the `date` column. The parser currently accepts these date formats: `YYYY-MM-DD`, `DD-MM-YYYY`, and `YYYY/MM/DD`.
	 - If a player's skill cell is empty or non-numeric, the engine marks that player as having `incomplete_skills` and includes a warning.
- Simple daily availability list: a plain list of names can be used by a higher-level adapter. The current CLI expects a CSV.
- Config: `config/sports.yaml` defines skills, weights, specialist thresholds, and team rules (e.g., rule to create 3 teams when players &gt; 17).

## Algorithm / logic summary

1. Weighted Power Rating (WPR)
	- Each player gets a WPR computed as: WPR = sum(skill_value * weight) using weights from the sport config.

2. Specialist identification
	- Players whose skill in a role >= the configured threshold are considered specialists for that role.

3. Seeding specialists
	- Specialists are seeded into teams first to ensure role coverage. Seeding is round-robin by role, attempting to spread top specialists across teams. A player will never be assigned twice during seeding and teams respect the configured team size.

4. Greedy fill
	- Remaining players are sorted by WPR (descending) and placed into the current weakest team (lowest total WPR) that still has room. This reduces variance between teams.

5. Coverage & warnings
	- After assignment, each team is checked for specialist coverage per role; missing coverage results in warnings. Players with incomplete skill data also produce warnings.

6. Team sizing special rule
	- Configurable rule: by default teams of size 6 are used for volleyball. Additionally, the config contains a rule used here: if total players &gt; 17, create 3 teams (this is implemented in `engine.build_teams`).

	Implementation note: the engine reads `team_rules` (including `default_team_size`), but the current algorithm computes balanced team sizes by evenly splitting the available players across the chosen number of teams (derived from `players_thresholds`). In other words, `default_team_size` is present in the config but is not enforced by the algorithm today — teams are sized to distribute players evenly across the computed number of teams. If you want strict team sizes (e.g., always 6 per team), the engine will need a small change to respect `default_team_size` or the `team_size` parameter on `build_teams`.

Notes:
- The current algorithm is a fast, greedy approach that performs well for typical recreational group sizes (10–30 players). For exact optimality or strict constraints you can add an ILP/MIP solver (OR-Tools) later.

## Example outputs

- Text summary printed by the CLI (team lists, team scores, role coverage) and a list of warnings.
- The engine can also be adapted to emit CSV attachments containing team assignments and diagnostics for easy sharing.

## Extensibility

- Add new sports: modify `config/sports.yaml` and list the skill names and weights.
- Change thresholds or weights on the fly via the config to tune team-building behavior.
- Add a web layer (FastAPI) and a webhook adapter to accept inputs from WhatsApp/Twilio or other messaging platforms.

Notes about extensibility (current limitations):
- The `config/sports.yaml` file contains a `skills:` list and many tuning fields (for example, `rotation` and `tie_break`), but the engine currently only reads `weights`, `specialist_thresholds`, and `team_rules`. Fields such as `rotation` and `tie_break` are present for future use and are not applied by the algorithm today.
- To add a new sport with different skill names you will either need to update the CSV parser (in `roster_builder.engine`) to read skill column names from the sport config, or provide your CSV using the volleyball schema (`setter`, `passer`, `attack`, `serve`).

If you'd like, I can implement dynamic CSV parsing (use the `skills` list from the sport config) and make `build_teams` respect `default_team_size` — both are small, low-risk improvements that will make the README and engine fully aligned.

## WhatsApp integration (next steps)

To integrate with WhatsApp (MVP):

1. Choose a provider: Twilio Programmable WhatsApp is fastest for an MVP (sandbox available). For production use consider the Meta/WhatsApp Business API or Twilio with a verified number.
2. Build a small web service (FastAPI) with a `/webhook` POST endpoint that:
	- Validates provider signatures
	- Parses incoming messages (text lists or CSV attachments)
	- Calls the engine to generate teams
	- Replies with a short text summary or sends a CSV file back
3. Use ngrok during development to expose the local webhook to the provider sandbox, then move to a hosted HTTPS endpoint.

I can scaffold a Twilio sandbox + FastAPI webhook adapter if you want — the engine is ready to be called from such a service.

## Where to go from here

- Add the webhook adapter (FastAPI + Twilio) and message parsing.
- Improve the player identity resolution (map WhatsApp numbers to player records).
- Add more tests covering rotation constraints and uneven team sizes.
- Optionally add an ILP/MIP mode for exact constrained optimization.

## License

See `LICENSE` in the repository.

