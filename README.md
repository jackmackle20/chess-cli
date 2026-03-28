# chess-cli

A CLI tool for fetching, caching, and analyzing your [chess.com](https://www.chess.com) games. Local SQLite database for speed and offline use. Optional Stockfish integration for move-by-move analysis.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install globally (available in any shell)
git clone https://github.com/jackmackle/chess-cli.git
uv tool install ./chess-cli
```

Or for development:

```bash
cd chess-cli
uv venv && source .venv/bin/activate
uv pip install -e .
```

Stockfish is **automatically downloaded** on first use — no manual install needed. If you prefer to manage it yourself, `brew install stockfish` or `sudo apt install stockfish` also works.

## Usage

```bash
# Fetch your games from chess.com
chess sync

# Browse games
chess games list
chess games list --result loss --time-control blitz --limit 10
chess games show GAME_ID --moves

# Add notes to games
chess games note GAME_ID "missed the knight fork on move 14"
chess games notes                        # list all noted games
chess games notes --search "knight"      # search notes

# Stats and openings
chess stats
chess stats --time-control rapid
chess openings --color white --sort winrate

# Stockfish analysis (auto-downloads stockfish on first use)
chess analyze GAME_ID
chess analyze GAME_ID --depth 22 --force

# Interactive game review in the browser
chess review GAME_ID

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
| `chess games note ID "text"` | Add a timestamped note to a game |
| `chess games notes` | List all games with notes (supports `--search`) |
| `chess stats` | Win/loss/draw stats with time control breakdown |
| `chess openings` | Opening repertoire stats (ECO codes, win rates) |
| `chess analyze ID` | Stockfish move-by-move analysis |
| `chess review ID` | Interactive browser-based game review |
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

## Claude Code Skill

chess-cli ships with a skill that lets Claude Code act as your chess coach.

```bash
chess install-skill
```

Then in Claude Code:

```
/chess sync my games and tell me what I'm bad at
/chess analyze my last 5 losses
/chess what openings should I stop playing as white?
```

The skill teaches the agent how to use every command, pipe results, and give coaching advice.

## License

MIT
