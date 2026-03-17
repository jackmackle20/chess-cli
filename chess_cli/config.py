import json
import platform
import shutil
import stat
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".chess-cli"
DB_PATH = APP_DIR / "chess.db"
CONFIG_PATH = APP_DIR / "config.json"
BIN_DIR = APP_DIR / "bin"
STOCKFISH_PATH = "stockfish"
DEFAULT_DEPTH = 18

# Stockfish download URLs (official releases)
_SF_VERSION = "stockfish-17.1"
_SF_BASE = f"https://github.com/official-stockfish/Stockfish/releases/download/{_SF_VERSION}"
_SF_DOWNLOADS = {
    ("Darwin", "arm64"): f"{_SF_BASE}/stockfish-macos-m1-apple-silicon.tar",
    ("Darwin", "x86_64"): f"{_SF_BASE}/stockfish-macos-x86-64-sse41-popcnt.tar",
    ("Linux", "x86_64"): f"{_SF_BASE}/stockfish-ubuntu-x86-64.tar",
    ("Linux", "aarch64"): f"{_SF_BASE}/stockfish-ubuntu-x86-64.tar",
}

# Eval delta thresholds (centipawns, mover POV)
THRESHOLD_GOOD = 20
THRESHOLD_INACCURACY = 50
THRESHOLD_MISTAKE = 150
# > THRESHOLD_MISTAKE = blunder

BOOK_PLY = 16  # first N half-moves classified as "book" if in opening table

ASCII_ART = """
  ♚  ♛  ♜  ♝  ♞  ♟
 ┌──────────────────┐
 │    chess-cli     │
 └──────────────────┘
  ♙  ♘  ♗  ♖  ♕  ♔
"""


def _ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def get_stockfish_path(user_path: Optional[str] = None) -> Optional[str]:
    """Find or download the Stockfish binary.

    Priority:
    1. Explicit user_path (--stockfish flag)
    2. System PATH (brew install stockfish, etc.)
    3. Our managed copy in ~/.chess-cli/bin/
    4. Auto-download if not found
    """
    # 1. User-specified path
    if user_path:
        return user_path

    # 2. System PATH
    system = shutil.which("stockfish")
    if system:
        return system

    # 3. Managed copy
    managed = BIN_DIR / "stockfish"
    if managed.exists():
        return str(managed)

    # 4. Auto-download
    return _download_stockfish()


def _download_stockfish() -> Optional[str]:
    """Download Stockfish binary for the current platform."""
    os_name = platform.system()
    arch = platform.machine()

    key = (os_name, arch)
    url = _SF_DOWNLOADS.get(key)
    if not url:
        return None

    try:
        import httpx
        from chess_cli.output import err_console

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        target = BIN_DIR / "stockfish"

        err_console.print(f"[dim]Stockfish not found. Downloading {_SF_VERSION}...[/dim]")

        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            resp.raise_for_status()
            archive_path = BIN_DIR / "stockfish-download.tar"
            with open(archive_path, "wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)

        # Extract — find the stockfish binary inside the archive
        with tarfile.open(archive_path, "r:*") as tar:
            for member in tar.getmembers():
                basename = Path(member.name).name
                if basename == "stockfish" and member.isfile():
                    # Extract just this file
                    fileobj = tar.extractfile(member)
                    if fileobj:
                        with open(target, "wb") as out:
                            out.write(fileobj.read())
                        break
            else:
                # No exact match — look for any executable-looking file
                for member in tar.getmembers():
                    if "stockfish" in member.name.lower() and member.isfile() and not member.name.endswith((".md", ".txt", ".png")):
                        fileobj = tar.extractfile(member)
                        if fileobj:
                            with open(target, "wb") as out:
                                out.write(fileobj.read())
                            break

        # Clean up archive
        archive_path.unlink(missing_ok=True)

        if not target.exists():
            err_console.print("[yellow]Warning:[/yellow] Could not find stockfish binary in archive.")
            return None

        # Make executable
        target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        err_console.print(f"[green]✓[/green] Stockfish installed to {target}")
        return str(target)

    except Exception as e:
        from chess_cli.output import err_console
        err_console.print(f"[yellow]Warning:[/yellow] Failed to download Stockfish: {e}")
        return None


def load_config() -> dict:
    _ensure_app_dir()
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    _ensure_app_dir()
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def get_default_username() -> Optional[str]:
    return load_config().get("default_username")


def set_default_username(username: str):
    cfg = load_config()
    cfg["default_username"] = username
    save_config(cfg)


def is_initialized() -> bool:
    return CONFIG_PATH.exists() and get_default_username() is not None


def resolve_username(username: Optional[str], json_mode: bool = False) -> str:
    """Resolve username from argument or default config. Exits on failure."""
    if username:
        return username
    default = get_default_username()
    if default:
        return default
    from chess_cli.output import print_error
    print_error("No username provided and no default set. Run `chess init` first.", json_mode)
    raise SystemExit(1)  # print_error already exits, but just in case
