import json
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".chess-cli"
DB_PATH = APP_DIR / "chess.db"
CONFIG_PATH = APP_DIR / "config.json"
STOCKFISH_PATH = "stockfish"
DEFAULT_DEPTH = 18

# Eval delta thresholds (centipawns, mover POV)
THRESHOLD_GOOD = 20
THRESHOLD_INACCURACY = 50
THRESHOLD_MISTAKE = 150
# > THRESHOLD_MISTAKE = blunder

BOOK_PLY = 16  # first N half-moves classified as "book" if in opening table

ASCII_ART = """
  ♚  ♛  ♜  ♝  ♞  ♟
 ┌──────────────────┐
 │    chess-cli     │
 └──────────────────┘
  ♙  ♘  ♗  ♖  ♕  ♔
"""


def _ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_app_dir()
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    _ensure_app_dir()
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def get_default_username() -> Optional[str]:
    return load_config().get("default_username")


def set_default_username(username: str):
    cfg = load_config()
    cfg["default_username"] = username
    save_config(cfg)


def is_initialized() -> bool:
    return CONFIG_PATH.exists() and get_default_username() is not None


def resolve_username(username: Optional[str], json_mode: bool = False) -> str:
    """Resolve username from argument or default config. Exits on failure."""
    if username:
        return username
    default = get_default_username()
    if default:
        return default
    from chess_cli.output import print_error
    print_error("No username provided and no default set. Run `chess init` first.", json_mode)
    raise SystemExit(1)  # print_error already exits, but just in case
