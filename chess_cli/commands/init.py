from typing import Optional

import typer
from rich.prompt import Prompt

from chess_cli.config import (
    ASCII_ART, is_initialized, set_default_username, get_default_username,
)
from chess_cli.db import get_connection, create_schema
from chess_cli.output import console, print_output

app = typer.Typer(help="Initialize chess-cli")


@app.callback(invoke_without_command=True)
def init(
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    if not json_:
        console.print(ASCII_ART, style="bold")

    existing = get_default_username()
    if existing and not json_:
        console.print(f"Current default username: [bold]{existing}[/bold]\n")

    if json_:
        # non-interactive, just report status
        print_output({
            "initialized": is_initialized(),
            "default_username": existing,
        }, json_mode=True)
        return

    username = Prompt.ask(
        "Enter your chess.com username",
        default=existing or "",
        console=console,
    ).strip()

    if not username:
        console.print("[yellow]No username provided, skipping.[/yellow]")
        return

    set_default_username(username)

    # Ensure DB schema exists
    conn = get_connection(db)
    create_schema(conn)

    console.print(f"\n[green]✓[/green] Default username set to [bold]{username}[/bold]")
    console.print(f"\nGet started:")
    console.print(f"  [dim]chess sync[/dim]            Fetch your games")
    console.print(f"  [dim]chess games list[/dim]      Browse games")
    console.print(f"  [dim]chess stats[/dim]           View your stats")
    console.print(f"  [dim]chess openings[/dim]        Opening repertoire")
