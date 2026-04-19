from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Player:
    id: Optional[str]
    name: str
    skills: Dict[str, Optional[float]] = field(default_factory=dict)
    incomplete_skills: bool = False


@dataclass
class Team:
    id: int
    players: list[Player] = field(default_factory=list)
    total_score: float = 0.0
    role_coverage: Dict[str, bool] = field(default_factory=dict)
