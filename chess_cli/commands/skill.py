import shutil
from importlib import resources
from pathlib import Path
from typing import Optional

import typer

from chess_cli.output import print_output, print_error, console

app = typer.Typer(help="Install the Claude Code chess skill")

SKILL_DEST = Path.home() / ".claude" / "commands" / "chess.md"


@app.callback(invoke_without_command=True)
def install_skill(
    json_: bool = typer.Option(False, "--json"),
):
    """Install the chess skill to ~/.claude/commands/ for use in Claude Code."""
    # Load the skill file from our package data
    try:
        skill_source = resources.files("chess_cli") / "data" / "chess-skill.md"
        content = skill_source.read_text(encoding="utf-8")
    except Exception as e:
        print_error(f"Could not read bundled skill file: {e}", json_)
        return

    # Ensure target directory exists
    SKILL_DEST.parent.mkdir(parents=True, exist_ok=True)

    # Write it
    SKILL_DEST.write_text(content)

    data = {"path": str(SKILL_DEST), "installed": True}

    def rich_fn(d, c):
        c.print(f"[green]✓[/green] Skill installed to [bold]{d['path']}[/bold]")
        c.print(f"\n  Use it in Claude Code:")
        c.print(f"  [dim]/chess analyze my recent losses[/dim]")
        c.print(f"  [dim]/chess what openings should I play as black?[/dim]")

    print_output(data, json_mode=json_, rich_fn=rich_fn)
