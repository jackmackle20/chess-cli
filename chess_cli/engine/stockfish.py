import io
import sys
from typing import Optional

import chess
import chess.pgn

from chess_cli.config import DEFAULT_DEPTH, THRESHOLD_GOOD, THRESHOLD_INACCURACY, THRESHOLD_MISTAKE


def get_engine(path: Optional[str] = None, depth: int = DEFAULT_DEPTH):
    """Return a Stockfish instance or None if not available.

    Searches system PATH, managed install, and auto-downloads if needed.
    """
    from chess_cli.config import get_stockfish_path

    engine_path = get_stockfish_path(path)
    if not engine_path:
        return None

    try:
        from stockfish import Stockfish
        sf = Stockfish(path=engine_path, depth=depth)
        return sf
    except Exception:
        return None


def _cp_to_float(info) -> Optional[float]:
    """Convert stockfish eval dict to centipawns float.

    The stockfish package returns {"type": "cp"|"mate", "value": int}.
    Value is always from the side-to-move's perspective.
    """
    if info is None:
        return None
    eval_type = info.get("type")
    value = info.get("value")
    if value is None:
        return None
    if eval_type == "mate":
        return 10000.0 if value > 0 else -10000.0
    return float(value)


def _classify(delta_cp: float, is_best: bool) -> str:
    """Classify a move given the eval delta and whether it matched the engine's top choice."""
    loss = -delta_cp  # positive loss = bad move
    if is_best:
        return "best"
    elif loss <= THRESHOLD_GOOD:
        return "good"
    elif loss <= THRESHOLD_INACCURACY:
        return "inaccuracy"
    elif loss <= THRESHOLD_MISTAKE:
        return "mistake"
    else:
        return "blunder"


def analyze_game(
    game_id: str,
    conn,
    engine,
    depth: int = DEFAULT_DEPTH,
    json_mode: bool = False,
) -> list[dict]:
    """Analyze all moves of a game. Returns list of move dicts."""
    from chess_cli.db import get_game, upsert_moves, mark_analyzed

    game_row = get_game(conn, game_id)
    if not game_row:
        raise ValueError(f"Game {game_id} not found in database")

    pgn_text = game_row["pgn"]
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError(f"Could not parse PGN for game {game_id}")

    # Moves up to opening_ply are "book" — these were detected at sync time
    opening_ply = game_row.get("opening_ply") or 0

    board = game.board()
    moves_list = list(game.mainline_moves())
    results: list[dict] = []

    # Set up progress display
    if not json_mode:
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
            progress_ctx = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=__import__("chess_cli.output", fromlist=["err_console"]).err_console,
            )
        except Exception:
            progress_ctx = None
    else:
        progress_ctx = None

    def do_analysis():
        nonlocal board
        board = game.board()

        engine.set_depth(depth)

        for ply, move in enumerate(moves_list, start=1):
            san = board.san(move)
            uci = move.uci()

            # Eval before move
            engine.set_fen_position(board.fen())
            eval_info_before = engine.get_evaluation()
            cp_before = _cp_to_float(eval_info_before)

            # Best move before
            best_uci_str = engine.get_best_move()
            best_san_str = None
            if best_uci_str:
                try:
                    best_move_obj = chess.Move.from_uci(best_uci_str)
                    best_san_str = board.san(best_move_obj)
                except Exception:
                    pass

            # Make move
            board.push(move)

            # Eval after move (from same side's POV = negate)
            engine.set_fen_position(board.fen())
            eval_info_after = engine.get_evaluation()
            cp_after_raw = _cp_to_float(eval_info_after)

            # Stockfish evals are always from side-to-move's POV.
            # cp_before = from mover's POV (it was their turn).
            # cp_after_raw = from opponent's POV (now it's their turn).
            # Negate to get mover's POV after the move.
            cp_after = -cp_after_raw if cp_after_raw is not None else None

            # Delta: positive = position improved for mover, negative = blundered
            if cp_before is not None and cp_after is not None:
                delta = cp_after - cp_before
            else:
                delta = None

            # Classification
            is_best = best_uci_str is not None and uci == best_uci_str
            if ply <= opening_ply:
                classification = "book"
            elif delta is not None:
                classification = _classify(delta, is_best)
            else:
                classification = None

            results.append({
                "game_id": game_id,
                "ply": ply,
                "uci": uci,
                "san": san,
                "eval_before": cp_before,
                "eval_after": cp_after,
                "eval_delta": delta,
                "classification": classification,
                "best_uci": best_uci_str,
                "best_san": best_san_str,
                "depth": depth,
            })

            if task_id is not None and progress_ctx is not None:
                progress_ctx.update(task_id, advance=1)

        return results

    task_id = None
    if progress_ctx is not None:
        with progress_ctx:
            task_id = progress_ctx.add_task(
                f"Analyzing {game_id[:8]}…", total=len(moves_list)
            )
            do_analysis()
    else:
        do_analysis()

    upsert_moves(conn, game_id, results)
    mark_analyzed(conn, game_id)
    conn.commit()

    return results
