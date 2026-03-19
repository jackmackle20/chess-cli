import subprocess
import sys
from typing import Optional

import typer

from chess_cli.output import print_output, print_error, console, err_console

app = typer.Typer(help="Update chess-cli to the latest version")

REPO_URL = "https://github.com/jackmackle20/chess-cli.git"


def _get_current_version() -> str:
    from chess_cli import __version__
    return __version__


def _get_latest_version() -> Optional[str]:
    """Check GitHub for the latest release tag."""
    try:
        import httpx
        resp = httpx.get(
            "https://api.github.com/repos/jackmackle20/chess-cli/tags",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        resp.raise_for_status()
        tags = resp.json()
        if tags:
            # Tags like "v0.2.0" or "0.2.0"
            return tags[0]["name"].lstrip("v")
    except Exception:
        pass
    return None


@app.callback(invoke_without_command=True)
def update(
    check: bool = typer.Option(False, "--check", help="Only check for updates, don't install"),
    json_: bool = typer.Option(False, "--json"),
):
    """Update chess-cli to the latest version from GitHub."""
    current = _get_current_version()

    if check:
        latest = _get_latest_version()
        if latest and latest != current:
            data = {"current": current, "latest": latest, "update_available": True}
            def rich_fn(d, c):
                c.print(f"Update available: [dim]{d['current']}[/dim] → [green]{d['latest']}[/green]")
                c.print(f"  Run [bold]chess update[/bold] to install")
            print_output(data, json_mode=json_, rich_fn=rich_fn)
        else:
            data = {"current": current, "latest": latest or current, "update_available": False}
            def rich_fn(d, c):
                c.print(f"[green]✓[/green] chess-cli [bold]{d['current']}[/bold] is up to date")
            print_output(data, json_mode=json_, rich_fn=rich_fn)
        return

    # Do the update
    if not json_:
        console.print(f"[dim]Current version: {current}[/dim]")
        console.print(f"[dim]Updating from {REPO_URL}...[/dim]")

    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "chess-cli"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # uv tool upgrade may not work if installed from local path
            # Fall back to reinstall
            if not json_:
                err_console.print("[dim]Falling back to reinstall...[/dim]")

            result = subprocess.run(
                ["uv", "tool", "install", "--force", "--from",
                 f"git+{REPO_URL}", "chess-cli"],
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            print_error(
                f"Update failed: {result.stderr.strip()}",
                json_,
            )
            return

        new_version = _get_current_version()
        data = {"previous": current, "current": new_version, "success": True}

        def rich_fn(d, c):
            if d["previous"] != d["current"]:
                c.print(f"[green]✓[/green] Updated: {d['previous']} → [bold]{d['current']}[/bold]")
            else:
                c.print(f"[green]✓[/green] Reinstalled [bold]{d['current']}[/bold]")

            # Remind to reinstall skill if it was updated
            c.print(f"  [dim]Run `chess install-skill` to update the Claude Code skill[/dim]")

        print_output(data, json_mode=json_, rich_fn=rich_fn)

    except FileNotFoundError:
        print_error(
            "uv not found. Install it: https://docs.astral.sh/uv/",
            json_,
        )
