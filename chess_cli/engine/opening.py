import csv
import io
from functools import lru_cache
from importlib import resources
from typing import Optional

import chess
import chess.pgn


def _fen_key(fen: str) -> str:
    """Strip FEN to pieces + side-to-move for fuzzy matching."""
    parts = fen.split()
    return " ".join(parts[:2])


@lru_cache(maxsize=1)
def _load_eco_table() -> dict[str, tuple[str, str]]:
    """Load eco.tsv and return dict: fen_key -> (eco_code, name).

    The TSV has columns: eco, name, pgn
    We replay each PGN to get the final FEN.
    """
    table: dict[str, tuple[str, str]] = {}

    pkg = resources.files("chess_cli") / "data" / "eco.tsv"
    content = pkg.read_text(encoding="utf-8")

    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        eco = row.get("eco", "").strip()
        name = row.get("name", "").strip()
        pgn_text = row.get("pgn", "").strip()
        if not eco or not pgn_text:
            continue

        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                continue
            board = game.board()
            for move in game.mainline_moves():
                board.push(move)
            key = _fen_key(board.fen())
            table[key] = (eco, name)
        except Exception:
            continue

    return table


def detect_opening(pgn_text: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Detect opening from a PGN string.

    Returns (eco_code, name, ply_count) — the last position that matched the ECO table.
    """
    table = _load_eco_table()
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return None, None, None

        board = game.board()
        last_eco: Optional[str] = None
        last_name: Optional[str] = None
        last_ply: Optional[int] = None

        for ply, move in enumerate(game.mainline_moves(), start=1):
            board.push(move)
            key = _fen_key(board.fen())
            if key in table:
                last_eco, last_name = table[key]
                last_ply = ply

            # Stop looking after move 40 (ply 80) for performance
            if ply > 80:
                break

        return last_eco, last_name, last_ply
    except Exception:
        return None, None, None
