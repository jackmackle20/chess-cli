import json
import sys
from typing import Optional

import typer

from chess_cli.config import DEFAULT_DEPTH
from chess_cli.db import get_connection, create_schema, get_game, get_moves
from chess_cli.engine.stockfish import get_engine, analyze_game
from chess_cli.output import print_output, print_error

app = typer.Typer(help="Analyze games with Stockfish")

CLASSIFICATIONS = ("best", "good", "book", "inaccuracy", "mistake", "blunder")


def _build_result(game_id: str, moves: list[dict], cached: bool = False) -> dict:
    result = {"game_id": game_id, "move_count": len(moves)}
    for cls in CLASSIFICATIONS:
        result[cls] = sum(1 for m in moves if m.get("classification") == cls)
    if cached:
        result["cached"] = True
    return result


def _get_game_ids(game_id: Optional[str]) -> list[str]:
    if game_id:
        return [game_id]
    if not sys.stdin.isatty():
        try:
            data = json.load(sys.stdin)
            if isinstance(data, list):
                return [g["id"] for g in data if "id" in g]
        except Exception:
            pass
    return []


@app.callback(invoke_without_command=True)
def analyze(
    game_id: Optional[str] = typer.Argument(None, help="Game ID to analyze"),
    depth: int = typer.Option(DEFAULT_DEPTH, "--depth", help="Stockfish search depth"),
    force: bool = typer.Option(False, "--force", help="Re-analyze even if already analyzed"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
    stockfish: Optional[str] = typer.Option(None, "--stockfish"),
):
    conn = get_connection(db)
    create_schema(conn)

    game_ids = _get_game_ids(game_id)
    if not game_ids:
        print_error("Provide a GAME_ID or pipe JSON from `chess games list --json`", json_)
        return

    engine = get_engine(stockfish, depth)
    if engine is None:
        print_error(
            "Stockfish not found and auto-download failed. Install manually: brew install stockfish (macOS) or apt install stockfish (Linux)",
            json_,
        )
        return

    results = []
    for gid in game_ids:
        game = get_game(conn, gid)
        if not game:
            print_error(f"Game {gid!r} not found. Run `chess sync` first.", json_)
            continue

        if game.get("analyzed") and not force:
            cached_moves = get_moves(conn, gid)
            results.append(_build_result(gid, cached_moves, cached=True))
            continue

        try:
            moves = analyze_game(gid, conn, engine, depth=depth, json_mode=json_)
            results.append(_build_result(gid, moves))
        except Exception as e:
            print_error(f"Analysis failed for {gid}: {e}", json_)

    def rich_fn(data, c):
        for r in data:
            if r.get("cached"):
                c.print(f"[dim]Already analyzed (use --force to re-analyze)[/dim]")
            gid_short = r['game_id'][:12]
            pos = f"[bright_green]{r['best']} best[/bright_green], [green]{r['good']} good[/green], [dim]{r['book']} book[/dim]"
            neg = f"[yellow]{r['inaccuracy']} inaccuracies[/yellow], [orange3]{r['mistake']} mistakes[/orange3], [red]{r['blunder']} blunders[/red]"
            c.print(f"[green]✓[/green] {gid_short}: {pos} | {neg}")

    print_output(results, json_mode=json_, rich_fn=rich_fn)
