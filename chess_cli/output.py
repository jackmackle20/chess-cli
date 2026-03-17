import json
import sys
from rich.console import Console

console = Console()
err_console = Console(stderr=True)


def print_output(data, *, json_mode: bool, rich_fn=None):
    if json_mode:
        print(json.dumps(data, separators=(",", ":")))
    elif rich_fn:
        rich_fn(data, console)
    else:
        console.print(data)


def print_error(msg: str, json_mode: bool = False):
    if json_mode:
        print(json.dumps({"error": msg}, separators=(",", ":")), file=sys.stderr)
    else:
        err_console.print(f"[red]Error:[/red] {msg}")
    raise SystemExit(1)
