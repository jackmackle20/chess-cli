import io
import time
from datetime import datetime, timezone
from typing import Optional

import chess.pgn

from chess_cli.api import ChessComClient
from chess_cli.db import upsert_game, get_sync_state, upsert_sync_state
from chess_cli.engine.opening import detect_opening
from chess_cli.output import err_console


def _parse_result(game: dict, username: str) -> tuple[str, str]:
    """Return (result, color) from the local player's POV."""
    white = game.get("white", {})
    black = game.get("black", {})

    white_user = white.get("username", "").lower()
    username_lower = username.lower()

    if white_user == username_lower:
        color = "white"
        result_str = white.get("result", "")
    else:
        color = "black"
        result_str = black.get("result", "")

    # chess.com result values: "win", "checkmated", "resigned", "timeout",
    # "stalemate", "insufficient", "50move", "timevsinsufficient", "repetition",
    # "agreed", "bughousepartnerlose"
    if result_str == "win":
        result = "win"
    elif result_str in ("stalemate", "insufficient", "50move", "timevsinsufficient",
                        "repetition", "agreed"):
        result = "draw"
    else:
        result = "loss"

    return result, color


def _extract_game_id(url: str) -> str:
    """Extract UUID from chess.com game URL."""
    return url.rstrip("/").split("/")[-1]


def _parse_pgn_game(pgn_text: str) -> Optional[chess.pgn.Game]:
    try:
        return chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return None


def sync_user(
    username: str,
    conn,
    since: Optional[str] = None,
    full: bool = False,
    json_mode: bool = False,
) -> dict:
    """Fetch and cache games for a chess.com user.

    Args:
        username: chess.com username
        conn: SQLite connection
        since: Optional YYYY-MM filter
        full: If True, re-sync all archives
        json_mode: Suppress rich output

    Returns:
        {"synced": N, "skipped": N, "total": N}
    """
    synced = 0
    skipped = 0
    errors = 0

    with ChessComClient() as client:
        try:
            archives = client.get_archives(username)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch archives for {username}: {e}") from e

        # Filter by since date
        if since:
            archives = [a for a in archives if _archive_month(a) >= since]

        total_archives = len(archives)

        for i, archive_url in enumerate(archives):
            if not json_mode:
                err_console.print(
                    f"[dim]Syncing archive {i+1}/{total_archives}: {archive_url}[/dim]"
                )

            # Check sync state
            state = get_sync_state(conn, username, archive_url)
            archive_month = _archive_month(archive_url)
            current_month = datetime.now(timezone.utc).strftime("%Y/%m")

            # Skip if already synced and not full, unless it's the current month
            if not full and state and archive_month != current_month:
                skipped += 1
                continue

            try:
                games = client.get_games(archive_url)
            except Exception as e:
                if not json_mode:
                    err_console.print(f"[yellow]Warning:[/yellow] Failed to fetch {archive_url}: {e}")
                errors += 1
                continue

            new_count = 0
            for game_data in games:
                try:
                    game_record = _process_game(game_data, username)
                    if game_record:
                        upsert_game(conn, game_record)
                        new_count += 1
                except Exception as e:
                    if not json_mode:
                        err_console.print(f"[yellow]Warning:[/yellow] Failed to process game: {e}")
                    continue

            conn.commit()
            synced += new_count

            upsert_sync_state(
                conn,
                username,
                archive_url,
                int(time.time()),
                len(games),
            )
            conn.commit()

    return {"synced": synced, "skipped": skipped, "total": synced + skipped, "errors": errors}


def _archive_month(archive_url: str) -> str:
    """Extract YYYY/MM from archive URL like .../games/2024/01"""
    parts = archive_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return ""


def _process_game(game_data: dict, username: str) -> Optional[dict]:
    """Convert chess.com API game dict to our DB row dict."""
    url = game_data.get("url", "")
    if not url:
        return None

    game_id = _extract_game_id(url)
    pgn_text = game_data.get("pgn", "")
    if not pgn_text:
        return None

    result, color = _parse_result(game_data, username)

    white = game_data.get("white", {})
    black = game_data.get("black", {})

    # Detect opening
    eco, opening_name, opening_ply = detect_opening(pgn_text)

    # Get termination from PGN headers
    termination = None
    parsed = _parse_pgn_game(pgn_text)
    if parsed:
        termination = parsed.headers.get("Termination")

    return {
        "id": game_id,
        "username": username,
        "pgn": pgn_text,
        "url": url,
        "time_control": game_data.get("time_control"),
        "time_class": game_data.get("time_class"),
        "rules": game_data.get("rules"),
        "rated": 1 if game_data.get("rated", False) else 0,
        "white_username": white.get("username", ""),
        "white_rating": white.get("rating"),
        "black_username": black.get("username", ""),
        "black_rating": black.get("rating"),
        "result": result,
        "termination": termination,
        "color": color,
        "end_time": game_data.get("end_time", 0),
        "opening_eco": eco,
        "opening_name": opening_name,
        "opening_ply": opening_ply,
        "analyzed": 0,
    }
