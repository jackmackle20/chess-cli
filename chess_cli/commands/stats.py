from datetime import datetime, timezone
from typing import Optional

import typer
from rich.table import Table

from chess_cli.config import resolve_username
from chess_cli.db import get_connection, create_schema
from chess_cli.output import print_output, print_error

app = typer.Typer(help="Show player statistics")


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
def stats(
    username: Optional[str] = typer.Argument(None, help="chess.com username (default: configured user)"),
    time_control: Optional[str] = typer.Option(None, "--time-control"),
    from_date: Optional[str] = typer.Option(None, "--from"),
    to_date: Optional[str] = typer.Option(None, "--to"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    username = resolve_username(username, json_)
    conn = get_connection(db)
    create_schema(conn)

    where = ["username=?"]
    params: list = [username]

    if time_control:
        where.append("time_class=?")
        params.append(time_control)
    if from_date:
        ts = _date_to_ts(from_date)
        if ts:
            where.append("end_time>=?")
            params.append(ts)
    if to_date:
        ts = _date_to_ts(to_date, end_of_day=True)
        if ts:
            where.append("end_time<=?")
            params.append(ts)

    sql_where = " AND ".join(where)

    # Overall counts
    row = conn.execute(
        f"SELECT COUNT(*) as total, "
        f"SUM(result='win') as wins, "
        f"SUM(result='loss') as losses, "
        f"SUM(result='draw') as draws "
        f"FROM games WHERE {sql_where}",
        params,
    ).fetchone()

    if not row or row["total"] == 0:
        print_error(f"No games found for {username!r}. Run `chess sync {username}` first.", json_)
        return

    total = row["total"]
    wins = row["wins"] or 0
    losses = row["losses"] or 0
    draws = row["draws"] or 0
    win_rate = round(wins / total * 100, 1) if total else 0.0

    # Per time-class breakdown
    tc_rows = conn.execute(
        f"SELECT time_class, COUNT(*) as games, "
        f"SUM(result='win') as wins, SUM(result='loss') as losses, SUM(result='draw') as draws "
        f"FROM games WHERE {sql_where} GROUP BY time_class",
        params,
    ).fetchall()

    time_class_breakdown = {}
    for r in tc_rows:
        tc = r["time_class"] or "unknown"
        tc_total = r["games"]
        tc_wins = r["wins"] or 0
        time_class_breakdown[tc] = {
            "games": tc_total,
            "wins": tc_wins,
            "losses": r["losses"] or 0,
            "draws": r["draws"] or 0,
            "win_rate": round(tc_wins / tc_total * 100, 1) if tc_total else 0.0,
        }

    # Average opponent rating
    avg_row = conn.execute(
        f"SELECT AVG(CASE WHEN color='white' THEN black_rating ELSE white_rating END) as avg_opp "
        f"FROM games WHERE {sql_where}",
        params,
    ).fetchone()
    avg_opp = round(avg_row["avg_opp"], 0) if avg_row and avg_row["avg_opp"] else None

    data = {
        "username": username,
        "total_games": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "avg_opponent_rating": avg_opp,
        "time_class_breakdown": time_class_breakdown,
    }

    def rich_fn(d, c):
        c.print(f"\n[bold]Stats for {d['username']}[/bold]")
        c.print(f"  Total games : {d['total_games']}")
        c.print(f"  Wins        : [green]{d['wins']}[/green]")
        c.print(f"  Losses      : [red]{d['losses']}[/red]")
        c.print(f"  Draws       : [yellow]{d['draws']}[/yellow]")
        c.print(f"  Win rate    : {d['win_rate']}%")
        if d.get("avg_opponent_rating"):
            c.print(f"  Avg opp ELO : {int(d['avg_opponent_rating'])}")

        if d["time_class_breakdown"]:
            c.print("")
            table = Table(title="By Time Control")
            table.add_column("TC")
            table.add_column("Games", justify="right")
            table.add_column("W", justify="right", style="green")
            table.add_column("L", justify="right", style="red")
            table.add_column("D", justify="right", style="yellow")
            table.add_column("Win%", justify="right")
            for tc, v in sorted(d["time_class_breakdown"].items()):
                table.add_row(tc, str(v["games"]), str(v["wins"]), str(v["losses"]),
                              str(v["draws"]), f"{v['win_rate']}%")
            c.print(table)

    print_output(data, json_mode=json_, rich_fn=rich_fn)
