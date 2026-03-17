from typing import Optional

import typer

from chess_cli.cache import sync_user
from chess_cli.config import resolve_username
from chess_cli.db import get_connection, create_schema
from chess_cli.output import print_output, print_error, console

app = typer.Typer(help="Sync games from chess.com")


@app.callback(invoke_without_command=True)
def sync(
    username: Optional[str] = typer.Argument(None, help="chess.com username (default: configured user)"),
    since: Optional[str] = typer.Option(None, "--since", help="Sync from YYYY-MM onwards"),
    full: bool = typer.Option(False, "--full", help="Re-sync all archives"),
    json_: bool = typer.Option(False, "--json", help="Output as JSON"),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite DB"),
    stockfish: Optional[str] = typer.Option(None, "--stockfish", help="Path to Stockfish binary"),
):
    username = resolve_username(username, json_)
    conn = get_connection(db)
    create_schema(conn)

    # Validate since format
    if since:
        try:
            parts = since.split("-")
            assert len(parts) == 2
            int(parts[0]); int(parts[1])
            since_filter = f"{parts[0]}/{parts[1]}"
        except Exception:
            print_error(f"Invalid --since format: {since!r} (expected YYYY-MM)", json_)
            return
    else:
        since_filter = None

    try:
        result = sync_user(username, conn, since=since_filter, full=full, json_mode=json_)
    except RuntimeError as e:
        print_error(str(e), json_)
        return

    data = {
        "username": username,
        "synced": result["synced"],
        "skipped": result["skipped"],
        "errors": result.get("errors", 0),
    }

    def rich_fn(d, c):
        c.print(f"[green]✓[/green] Synced [bold]{d['synced']}[/bold] games for [bold]{d['username']}[/bold]")
        if d["skipped"]:
            c.print(f"  Skipped {d['skipped']} already-synced archives")
        if d["errors"]:
            c.print(f"  [yellow]{d['errors']} archive(s) failed[/yellow]")

    print_output(data, json_mode=json_, rich_fn=rich_fn)
