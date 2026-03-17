from typing import Optional

import typer

from chess_cli.config import get_default_username, set_default_username, load_config
from chess_cli.output import print_output, console

app = typer.Typer(help="View or update configuration")


@app.command("show")
def config_show(
    json_: bool = typer.Option(False, "--json"),
):
    cfg = load_config()

    def rich_fn(data, c):
        c.print("[bold]chess-cli config[/bold]\n")
        for k, v in data.items():
            c.print(f"  {k}: [bold]{v}[/bold]")

    print_output(cfg, json_mode=json_, rich_fn=rich_fn)


@app.command("set-user")
def config_set_user(
    username: str = typer.Argument(..., help="chess.com username to set as default"),
    json_: bool = typer.Option(False, "--json"),
):
    set_default_username(username)
    data = {"default_username": username}

    def rich_fn(data, c):
        c.print(f"[green]✓[/green] Default username set to [bold]{data['default_username']}[/bold]")

    print_output(data, json_mode=json_, rich_fn=rich_fn)
