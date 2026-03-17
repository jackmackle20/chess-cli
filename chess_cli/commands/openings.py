from typing import Optional

import typer
from rich.table import Table

from chess_cli.config import resolve_username
from chess_cli.db import get_connection, create_schema
from chess_cli.output import print_output, print_error

app = typer.Typer(help="Opening statistics")


@app.callback(invoke_without_command=True)
def openings(
    username: Optional[str] = typer.Argument(None, help="chess.com username (default: configured user)"),
    color: Optional[str] = typer.Option(None, "--color", help="white|black"),
    time_control: Optional[str] = typer.Option(None, "--time-control"),
    min_games: int = typer.Option(3, "--min-games", help="Minimum games threshold"),
    sort: str = typer.Option("games", "--sort", help="Sort by: winrate|games"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    username = resolve_username(username, json_)
    conn = get_connection(db)
    create_schema(conn)

    if color and color not in ("white", "black"):
        print_error(f"Invalid --color: {color!r}", json_)

    where = ["username=?", "opening_eco IS NOT NULL"]
    params: list = [username]

    if color:
        where.append("color=?")
        params.append(color)
    if time_control:
        where.append("time_class=?")
        params.append(time_control)

    sql_where = " AND ".join(where)

    rows = conn.execute(
        f"SELECT opening_eco, opening_name, color, "
        f"COUNT(*) as games, "
        f"SUM(result='win') as wins, "
        f"SUM(result='loss') as losses, "
        f"SUM(result='draw') as draws "
        f"FROM games WHERE {sql_where} "
        f"GROUP BY opening_eco, color "
        f"HAVING games >= ? "
        f"ORDER BY games DESC",
        params + [min_games],
    ).fetchall()

    summaries = []
    for r in rows:
        g = r["games"]
        w = r["wins"] or 0
        winrate = round(w / g * 100, 1) if g else 0.0
        summaries.append({
            "eco": r["opening_eco"],
            "name": r["opening_name"] or "",
            "color": r["color"],
            "games": g,
            "wins": w,
            "losses": r["losses"] or 0,
            "draws": r["draws"] or 0,
            "winrate": winrate,
        })

    # Sort
    if sort == "winrate":
        summaries.sort(key=lambda x: x["winrate"], reverse=True)
    else:
        summaries.sort(key=lambda x: x["games"], reverse=True)

    def rich_fn(data, c):
        if not data:
            c.print("[yellow]No opening data found.[/yellow]")
            return
        table = Table(title=f"Openings for {username}")
        table.add_column("ECO", no_wrap=True)
        table.add_column("Name", max_width=35)
        table.add_column("Color")
        table.add_column("Games", justify="right")
        table.add_column("W", justify="right", style="green")
        table.add_column("L", justify="right", style="red")
        table.add_column("D", justify="right", style="yellow")
        table.add_column("Win%", justify="right")
        for s in data:
            table.add_row(
                s["eco"], s["name"], s["color"],
                str(s["games"]), str(s["wins"]), str(s["losses"]), str(s["draws"]),
                f"{s['winrate']}%",
            )
        c.print(table)

    print_output(summaries, json_mode=json_, rich_fn=rich_fn)
