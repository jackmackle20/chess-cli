# chess-cli

A CLI tool for fetching, caching, and analyzing your [chess.com](https://www.chess.com) games. Local SQLite database for speed and offline use. Optional Stockfish integration for move-by-move analysis.

```
    ♚ ♛ ♜ ♝ ♞ ♟
   ┌─────────────┐
   │  chess-cli   │
   └─────────────┘
    ♙ ♘ ♗ ♖ ♕ ♔
```

## Install

Requires Python 3.11+.

```bash
# Clone and install
git clone https://github.com/jackmackle/chess-cli.git
cd chess-cli
uv venv && source .venv/bin/activate
uv pip install -e .

# First run — sets your default username
chess init
```

For move analysis, install [Stockfish](https://stockfishchess.org/):

```bash
brew install stockfish        # macOS
sudo apt install stockfish    # Linux
```

## Usage

```bash
# Fetch your games from chess.com
chess sync

# Browse games
chess games list
chess games list --result loss --time-control blitz --limit 10
chess games show GAME_ID --moves

# Stats and openings
chess stats
chess stats --time-control rapid
chess openings --color white --sort winrate

# Stockfish analysis (requires stockfish)
chess analyze GAME_ID
chess analyze GAME_ID --depth 22 --force

# Find recurring blunders across analyzed games
chess blunders
chess blunders --time-control blitz --min-count 3
```

All commands support `--json` for structured output (errors go to stderr), making it easy to pipe into other tools:

```bash
chess games list --result loss --json | chess analyze --json
```

## Commands

| Command | Description |
|---|---|
| `chess init` | First-time setup — set your default chess.com username |
| `chess config show` | View current configuration |
| `chess config set-user NAME` | Change default username |
| `chess sync` | Fetch games from chess.com (incremental by default) |
| `chess games list` | List cached games with filters |
| `chess games show ID` | Show game details, PGN, or analyzed moves |
| `chess stats` | Win/loss/draw stats with time control breakdown |
| `chess openings` | Opening repertoire stats (ECO codes, win rates) |
| `chess analyze ID` | Stockfish move-by-move analysis |
| `chess blunders` | Find recurring blunder patterns |

Every command that takes a username argument will fall back to your configured default if omitted. You can always pass a username explicitly to look at another player's games.

## Global Options

- `--json` — JSON output to stdout (all commands)
- `--db PATH` — custom SQLite database path (default: `~/.chess-cli/chess.db`)
- `--stockfish PATH` — custom Stockfish binary path

## How It Works

- **Sync** pulls game archives from the [chess.com public API](https://www.chess.com/news/view/published-data-api), parses PGN with [python-chess](https://python-chess.readthedocs.io/), detects openings against the [lichess ECO dataset](https://github.com/lichess-org/chess-openings) (~3,600 positions), and caches everything in a local SQLite database.
- **Analysis** runs each move through Stockfish and classifies it as book, best, good, inaccuracy, mistake, or blunder based on centipawn loss.
- Subsequent syncs are incremental — only the current month is re-fetched unless you pass `--full`.

## License

MIT
