import typer

from chess_cli.commands import sync, games, stats, openings, analyze, blunders, review, skill, update
from chess_cli.commands import init as init_cmd
from chess_cli.commands import config_cmd

app = typer.Typer(
    name="chess",
    help="Chess.com game fetcher, cache, and analyzer.",
    no_args_is_help=True,
)

app.add_typer(init_cmd.app, name="init")
app.add_typer(config_cmd.app, name="config")
app.add_typer(sync.app, name="sync")
app.add_typer(games.app, name="games")
app.add_typer(stats.app, name="stats")
app.add_typer(openings.app, name="openings")
app.add_typer(analyze.app, name="analyze")
app.add_typer(blunders.app, name="blunders")
app.add_typer(review.app, name="review")
app.add_typer(skill.app, name="install-skill")
app.add_typer(update.app, name="update")


@app.callback()
def main_callback(ctx: typer.Context):
    """Auto-trigger init on first run (unless already running init or config)."""
    from chess_cli.config import is_initialized
    cmd = ctx.invoked_subcommand
    if cmd not in ("init", "config", None) and not is_initialized():
        from chess_cli.output import err_console
        err_console.print("[yellow]First time? Running setup...[/yellow]\n")
        from chess_cli.commands.init import init
        ctx.invoke(init)
        err_console.print()


if __name__ == "__main__":
    app()
