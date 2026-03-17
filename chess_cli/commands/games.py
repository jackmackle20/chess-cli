from datetime import datetime, timezone
from typing import Optional

import typer
from rich.table import Table

from chess_cli.config import resolve_username
from chess_cli.db import get_connection, create_schema, get_game, get_moves, list_games
from chess_cli.output import print_output, print_error, console

app = typer.Typer(help="List and show games")


def _date_to_ts(date_str: str, end_of_day: bool = False) -> Optional[int]:
    """Convert YYYY-MM-DD to Unix timestamp."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


@app.command("list")
def games_list(
    username: Optional[str] = typer.Argument(None, help="chess.com username (default: configured user)"),
    from_date: Optional[str] = typer.Option(None, "--from", help="From date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="To date YYYY-MM-DD"),
    result: Optional[str] = typer.Option(None, "--result", help="win|loss|draw"),
    color: Optional[str] = typer.Option(None, "--color", help="white|black"),
    time_control: Optional[str] = typer.Option(None, "--time-control", help="blitz|rapid|bullet|daily"),
    opening: Optional[str] = typer.Option(None, "--opening", help="ECO code filter"),
    limit: int = typer.Option(20, "--limit", help="Number of results"),
    offset: int = typer.Option(0, "--offset", help="Offset"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    username = resolve_username(username, json_)
    conn = get_connection(db)
    create_schema(conn)

    # Validate filters
    if result and result not in ("win", "loss", "draw"):
        print_error(f"Invalid --result: {result!r}. Must be win, loss, or draw.", json_)
    if color and color not in ("white", "black"):
        print_error(f"Invalid --color: {color!r}. Must be white or black.", json_)

    from_ts = _date_to_ts(from_date) if from_date else None
    to_ts = _date_to_ts(to_date, end_of_day=True) if to_date else None

    games = list_games(
        conn,
        username,
        from_date=from_ts,
        to_date=to_ts,
        result=result,
        color=color,
        time_class=time_control,
        opening_eco=opening,
        limit=limit,
        offset=offset,
    )

    # Remove raw PGN from output
    output_games = []
    for g in games:
        g.pop("pgn", None)
        output_games.append(g)

    def rich_fn(data, c):
        if not data:
            c.print("[yellow]No games found.[/yellow]")
            return
        table = Table(title=f"Games for {username}", show_lines=False)
        table.add_column("ID", style="dim", no_wrap=True, max_width=12)
        table.add_column("Date", no_wrap=True)
        table.add_column("Color")
        table.add_column("Opponent", no_wrap=True)
        table.add_column("Result")
        table.add_column("TC")
        table.add_column("Opening", max_width=30)

        for g in data:
            ts = g.get("end_time", 0)
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "?"
            color_str = g.get("color", "")
            if color_str == "white":
                opponent = g.get("black_username", "?")
            else:
                opponent = g.get("white_username", "?")
            res = g.get("result", "")
            res_color = {"win": "green", "loss": "red", "draw": "yellow"}.get(res, "white")
            table.add_row(
                str(g.get("id", ""))[:12],
                date_str,
                color_str,
                opponent,
                f"[{res_color}]{res}[/{res_color}]",
                g.get("time_class", "?"),
                g.get("opening_name", "") or "",
            )
        c.print(table)

    print_output(output_games, json_mode=json_, rich_fn=rich_fn)


@app.command("show")
def games_show(
    game_id: str = typer.Argument(..., help="Game ID"),
    pgn: bool = typer.Option(False, "--pgn", help="Include PGN text"),
    moves: bool = typer.Option(False, "--moves", help="Include move list"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    conn = get_connection(db)
    create_schema(conn)

    game = get_game(conn, game_id)
    if not game:
        print_error(f"Game {game_id!r} not found in local cache. Run `chess sync` first.", json_)
        return

    if not pgn:
        game.pop("pgn", None)

    if moves:
        game["moves"] = get_moves(conn, game_id)

    def rich_fn(data, c):
        if "moves" in data:
            move_list = data.pop("moves")
        else:
            move_list = None

        for k, v in data.items():
            if k == "pgn":
                continue
            c.print(f"[bold]{k}:[/bold] {v}")

        if pgn and "pgn" in data:
            c.print("\n[bold]PGN:[/bold]")
            c.print(data["pgn"])

        if move_list:
            c.print("\n[bold]Moves:[/bold]")
            move_table = Table(show_header=True)
            move_table.add_column("Ply")
            move_table.add_column("SAN")
            move_table.add_column("Eval")
            move_table.add_column("Class")
            for m in move_list:
                cls = m.get("classification") or ""
                cls_color = {
                    "blunder": "red", "mistake": "orange3",
                    "inaccuracy": "yellow", "good": "green",
                    "best": "bright_green", "book": "dim",
                }.get(cls, "white")
                move_table.add_row(
                    str(m.get("ply", "")),
                    m.get("san", ""),
                    f"{m.get('eval_after', ''):.1f}" if m.get("eval_after") is not None else "",
                    f"[{cls_color}]{cls}[/{cls_color}]",
                )
            c.print(move_table)

    print_output(game, json_mode=json_, rich_fn=rich_fn)
