import sqlite3
from pathlib import Path
from typing import Optional

from chess_cli.config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL,
    pgn             TEXT NOT NULL,
    url             TEXT NOT NULL,
    time_control    TEXT,
    time_class      TEXT,
    rules           TEXT,
    rated           INTEGER NOT NULL DEFAULT 1,
    white_username  TEXT NOT NULL,
    white_rating    INTEGER,
    black_username  TEXT NOT NULL,
    black_rating    INTEGER,
    result          TEXT NOT NULL,
    termination     TEXT,
    color           TEXT NOT NULL,
    end_time        INTEGER NOT NULL,
    opening_eco     TEXT,
    opening_name    TEXT,
    opening_ply     INTEGER,
    analyzed        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_games_username   ON games(username);
CREATE INDEX IF NOT EXISTS idx_games_end_time   ON games(end_time);
CREATE INDEX IF NOT EXISTS idx_games_time_class ON games(time_class);
CREATE INDEX IF NOT EXISTS idx_games_result     ON games(result);
CREATE INDEX IF NOT EXISTS idx_games_color      ON games(color);
CREATE INDEX IF NOT EXISTS idx_games_opening    ON games(opening_eco);

CREATE TABLE IF NOT EXISTS moves (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply             INTEGER NOT NULL,
    uci             TEXT NOT NULL,
    san             TEXT NOT NULL,
    eval_before     REAL,
    eval_after      REAL,
    eval_delta      REAL,
    classification  TEXT,
    best_uci        TEXT,
    best_san        TEXT,
    depth           INTEGER
);
CREATE INDEX IF NOT EXISTS idx_moves_game_id        ON moves(game_id);
CREATE INDEX IF NOT EXISTS idx_moves_classification ON moves(classification);

CREATE TABLE IF NOT EXISTS sync_state (
    username        TEXT NOT NULL,
    archive_url     TEXT NOT NULL,
    last_synced     INTEGER,
    game_count      INTEGER,
    PRIMARY KEY (username, archive_url)
);
"""

GAME_COLUMNS = [
    "id", "username", "pgn", "url", "time_control", "time_class", "rules",
    "rated", "white_username", "white_rating", "black_username", "black_rating",
    "result", "termination", "color", "end_time", "opening_eco", "opening_name",
    "opening_ply", "analyzed",
]

MOVE_COLUMNS = [
    "id", "game_id", "ply", "uci", "san", "eval_before", "eval_after",
    "eval_delta", "classification", "best_uci", "best_san", "depth",
]


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_schema(conn: sqlite3.Connection):
    conn.executescript(DDL)
    conn.commit()


def upsert_game(conn: sqlite3.Connection, game: dict):
    placeholders = ", ".join("?" for _ in GAME_COLUMNS)
    cols = ", ".join(GAME_COLUMNS)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in GAME_COLUMNS if c != "id"
    )
    values = [game.get(c) for c in GAME_COLUMNS]
    conn.execute(
        f"INSERT INTO games ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        values,
    )


def get_game(conn: sqlite3.Connection, game_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    return dict(row) if row else None


def list_games(
    conn: sqlite3.Connection,
    username: str,
    *,
    from_date: Optional[int] = None,
    to_date: Optional[int] = None,
    result: Optional[str] = None,
    color: Optional[str] = None,
    time_class: Optional[str] = None,
    opening_eco: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    where = ["username=?"]
    params: list = [username]

    if from_date:
        where.append("end_time>=?")
        params.append(from_date)
    if to_date:
        where.append("end_time<=?")
        params.append(to_date)
    if result:
        where.append("result=?")
        params.append(result)
    if color:
        where.append("color=?")
        params.append(color)
    if time_class:
        where.append("time_class=?")
        params.append(time_class)
    if opening_eco:
        where.append("opening_eco=?")
        params.append(opening_eco)

    sql = (
        f"SELECT * FROM games WHERE {' AND '.join(where)} "
        f"ORDER BY end_time DESC LIMIT ? OFFSET ?"
    )
    params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_moves(conn: sqlite3.Connection, game_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM moves WHERE game_id=? ORDER BY ply", (game_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_moves(conn: sqlite3.Connection, game_id: str, moves: list[dict]):
    conn.execute("DELETE FROM moves WHERE game_id=?", (game_id,))
    cols = [c for c in MOVE_COLUMNS if c != "id"]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    for move in moves:
        values = [move.get(c) for c in cols]
        conn.execute(
            f"INSERT INTO moves ({col_str}) VALUES ({placeholders})", values
        )


def mark_analyzed(conn: sqlite3.Connection, game_id: str):
    conn.execute("UPDATE games SET analyzed=1 WHERE id=?", (game_id,))


def get_sync_state(
    conn: sqlite3.Connection, username: str, archive_url: str
) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM sync_state WHERE username=? AND archive_url=?",
        (username, archive_url),
    ).fetchone()
    return dict(row) if row else None


def upsert_sync_state(
    conn: sqlite3.Connection,
    username: str,
    archive_url: str,
    last_synced: int,
    game_count: int,
):
    conn.execute(
        "INSERT INTO sync_state (username, archive_url, last_synced, game_count) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(username, archive_url) DO UPDATE SET "
        "last_synced=excluded.last_synced, game_count=excluded.game_count",
        (username, archive_url, last_synced, game_count),
    )
