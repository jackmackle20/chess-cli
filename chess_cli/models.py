from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class Game:
    id: str
    username: str
    pgn: str
    url: str
    time_control: Optional[str]
    time_class: Optional[str]
    rules: Optional[str]
    rated: int
    white_username: str
    white_rating: Optional[int]
    black_username: str
    black_rating: Optional[int]
    result: str
    termination: Optional[str]
    color: str
    end_time: int
    opening_eco: Optional[str]
    opening_name: Optional[str]
    opening_ply: Optional[int]
    analyzed: int
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("pgn", None)
        return d


@dataclass
class Move:
    id: Optional[int]
    game_id: str
    ply: int
    uci: str
    san: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    eval_delta: Optional[float]
    classification: Optional[str]
    best_uci: Optional[str]
    best_san: Optional[str]
    depth: Optional[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OpeningSummary:
    eco: str
    name: str
    color: str
    games: int
    wins: int
    losses: int
    draws: int
    winrate: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BlunderPattern:
    move_san: str
    move_uci: str
    count: int
    avg_eval_loss: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlayerStats:
    username: str
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    time_class_breakdown: dict = field(default_factory=dict)
    avg_opponent_rating: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)
