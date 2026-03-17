import json
import sys
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.table import Table

from chess_cli.config import resolve_username
from chess_cli.db import get_connection, create_schema
from chess_cli.output import print_output, print_error

app = typer.Typer(help="Show blunder patterns")


def _date_to_ts(date_str: str, end_of_day: bool = False) -> Optional[int]:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


@app.callback(invoke_without_command=True)
def blunders(
    username: Optional[str] = typer.Argument(None, help="chess.com username (default: configured user)"),
    time_control: Optional[str] = typer.Option(None, "--time-control"),
    from_date: Optional[str] = typer.Option(None, "--from"),
    to_date: Optional[str] = typer.Option(None, "--to"),
    min_count: int = typer.Option(2, "--min-count", help="Minimum blunder occurrences"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    username = resolve_username(username, json_)
    conn = get_connection(db)
    create_schema(conn)

    game_where = ["g.username=?", "g.analyzed=1"]
    game_params: list = [username]

    if time_control:
        game_where.append("g.time_class=?")
        game_params.append(time_control)
    if from_date:
        ts = _date_to_ts(from_date)
        if ts:
            game_where.append("g.end_time>=?")
            game_params.append(ts)
    if to_date:
        ts = _date_to_ts(to_date, end_of_day=True)
        if ts:
            game_where.append("g.end_time<=?")
            game_params.append(ts)

    g_where_sql = " AND ".join(game_where)

    rows = conn.execute(
        f"SELECT m.san, m.uci, COUNT(*) as cnt, AVG(m.eval_delta) as avg_loss "
        f"FROM moves m "
        f"JOIN games g ON g.id = m.game_id "
        f"WHERE {g_where_sql} AND m.classification='blunder' "
        f"GROUP BY m.san "
        f"HAVING cnt >= ? "
        f"ORDER BY cnt DESC, avg_loss ASC",
        game_params + [min_count],
    ).fetchall()

    patterns = []
    for r in rows:
        avg_loss = r["avg_loss"]
        patterns.append({
            "move_san": r["san"],
            "move_uci": r["uci"],
            "count": r["cnt"],
            "avg_eval_loss": round(abs(avg_loss), 1) if avg_loss is not None else None,
        })

    def rich_fn(data, c):
        if not data:
            c.print("[yellow]No blunder patterns found.[/yellow]")
            c.print("[dim]Tip: run `chess analyze` on your games first.[/dim]")
            return
        table = Table(title=f"Blunder Patterns for {username}")
        table.add_column("Move (SAN)", no_wrap=True)
        table.add_column("Count", justify="right")
        table.add_column("Avg Loss (cp)", justify="right")
        for p in data:
            table.add_row(
                p["move_san"],
                str(p["count"]),
                str(p["avg_eval_loss"]) if p["avg_eval_loss"] is not None else "?",
            )
        c.print(table)

    print_output(patterns, json_mode=json_, rich_fn=rich_fn)
