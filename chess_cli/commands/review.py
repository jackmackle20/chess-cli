import io
import json
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

import chess
import chess.pgn
import typer

from chess_cli.db import get_connection, create_schema, get_game, get_moves
from chess_cli.output import print_error, print_output, console

app = typer.Typer(help="Review analyzed games in the browser")

# lichess cburnett piece SVGs (base64 would be truly offline, but these are stable CDN URLs)
PIECE_BASE = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150"
PIECE_URLS = {
    "K": f"{PIECE_BASE}/wk.png", "Q": f"{PIECE_BASE}/wq.png",
    "R": f"{PIECE_BASE}/wr.png", "B": f"{PIECE_BASE}/wb.png",
    "N": f"{PIECE_BASE}/wn.png", "P": f"{PIECE_BASE}/wp.png",
    "k": f"{PIECE_BASE}/bk.png", "q": f"{PIECE_BASE}/bq.png",
    "r": f"{PIECE_BASE}/br.png", "b": f"{PIECE_BASE}/bb.png",
    "n": f"{PIECE_BASE}/bn.png", "p": f"{PIECE_BASE}/bp.png",
}


def _build_positions(pgn_text: str, moves_data: list[dict]) -> list[dict]:
    """Replay PGN and build position data for each ply."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return []

    board = game.board()
    positions = [{
        "fen": board.fen(),
        "ply": 0,
        "san": "",
        "uci": "",
        "eval_after": None,
        "classification": None,
        "best_uci": None,
        "best_san": None,
        "eval_delta": None,
    }]

    moves_by_ply = {m["ply"]: m for m in moves_data}

    for ply, move in enumerate(game.mainline_moves(), start=1):
        san = board.san(move)
        uci = move.uci()
        board.push(move)

        move_data = moves_by_ply.get(ply, {})

        # Convert eval_after from mover's POV to white's POV for display
        is_white_move = (ply % 2 == 1)
        eval_after_raw = move_data.get("eval_after")
        if eval_after_raw is not None:
            eval_white = eval_after_raw if is_white_move else -eval_after_raw
        else:
            eval_white = None

        positions.append({
            "fen": board.fen(),
            "ply": ply,
            "san": san,
            "uci": uci,
            "eval_after": eval_white,
            "eval_delta": move_data.get("eval_delta"),
            "classification": move_data.get("classification"),
            "best_uci": move_data.get("best_uci"),
            "best_san": move_data.get("best_san"),
        })

    return positions


def _generate_html(game_info: dict, positions: list[dict]) -> str:
    positions_json = json.dumps(positions)
    game_info_json = json.dumps(game_info)
    piece_urls_json = json.dumps(PIECE_URLS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Review - {game_info["white"]} vs {game_info["black"]}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
    background: #262421;
    color: #bbb;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    display: flex;
    justify-content: center;
    padding: 24px;
    min-height: 100vh;
}}

.container {{
    display: flex;
    gap: 0;
    align-items: flex-start;
}}

/* Eval bar */
.eval-col {{
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-right: 4px;
}}
.eval-bar {{
    width: 30px;
    height: 560px;
    background: #3d3d3d;
    border-radius: 3px;
    overflow: hidden;
    position: relative;
    border: 1px solid #555;
}}
.eval-fill {{
    position: absolute;
    bottom: 0;
    width: 100%;
    background: #eee;
    transition: height 0.3s ease;
}}
.eval-num {{
    position: absolute;
    width: 100%;
    text-align: center;
    font-size: 10px;
    font-weight: 700;
    z-index: 2;
    pointer-events: none;
    padding: 3px 0;
}}
.eval-num.top {{ top: 0; color: #ddd; }}
.eval-num.bot {{ bottom: 0; color: #444; }}

/* Board area */
.board-area {{
    flex-shrink: 0;
}}
.player-bar {{
    display: flex;
    align-items: center;
    padding: 8px 10px;
    font-size: 14px;
    font-weight: 600;
    background: #302e2c;
    border-radius: 3px;
    height: 36px;
}}
.player-bar.top {{ margin-bottom: 2px; border-radius: 3px 3px 0 0; }}
.player-bar.bot {{ margin-top: 2px; border-radius: 0 0 3px 3px; }}
.player-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}}
.player-dot.white {{ background: #eee; border: 1px solid #999; }}
.player-dot.black {{ background: #333; border: 1px solid #666; }}
.player-rating {{
    color: #777;
    font-weight: 400;
    margin-left: 6px;
}}

.board-wrap {{
    position: relative;
    width: 560px;
    height: 560px;
}}
.board {{
    display: grid;
    grid-template-columns: repeat(8, 70px);
    grid-template-rows: repeat(8, 70px);
    width: 560px;
    height: 560px;
}}
.sq {{
    width: 70px;
    height: 70px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    user-select: none;
}}
.sq img {{
    width: 58px;
    height: 58px;
    pointer-events: none;
    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.25));
}}
.sq-l {{ background: #ebecd0; }}
.sq-d {{ background: #779556; }}
.sq-l.hl {{ background: #f6f669; }}
.sq-d.hl {{ background: #baca2b; }}

.coord {{
    position: absolute;
    font-size: 10px;
    font-weight: 700;
    pointer-events: none;
    opacity: 0.7;
}}
.coord-rank {{ top: 2px; left: 3px; }}
.coord-file {{ bottom: 1px; right: 3px; }}
.sq-l .coord {{ color: #779556; }}
.sq-d .coord {{ color: #ebecd0; }}

.arrow-layer {{
    position: absolute;
    top: 0; left: 0;
    width: 560px;
    height: 560px;
    pointer-events: none;
    z-index: 10;
}}

/* Right panel */
.panel {{
    width: 380px;
    margin-left: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    height: 634px;
}}
.info-box {{
    background: #302e2c;
    padding: 14px 16px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.7;
}}
.info-box .title {{
    font-size: 15px;
    font-weight: 700;
    color: #e0e0e0;
    margin-bottom: 4px;
}}
.info-box .meta {{ color: #888; }}
.info-box .meta span {{ color: #bbb; }}
.info-box a {{ color: #81b64c; text-decoration: none; }}
.info-box a:hover {{ text-decoration: underline; }}

.nav {{
    display: flex;
    gap: 4px;
    justify-content: center;
}}
.nav button {{
    background: #302e2c;
    color: #bbb;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 16px;
    cursor: pointer;
    transition: background 0.15s;
}}
.nav button:hover {{ background: #444; }}
.nav button.on {{ background: #81b64c; color: #fff; }}

.eval-display {{
    text-align: center;
    font-size: 13px;
    color: #999;
    font-family: 'SF Mono', Consolas, monospace;
    min-height: 20px;
}}

.moves-box {{
    background: #302e2c;
    border-radius: 6px;
    overflow-y: auto;
    flex: 1;
}}
.moves-hdr {{
    display: grid;
    grid-template-columns: 28px 1fr 50px 1fr 50px;
    font-size: 10px;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 6px 0 4px;
    border-bottom: 1px solid #3d3b39;
}}
.moves-hdr > div {{ padding: 0 6px; }}
.moves-hdr > div:nth-child(3),
.moves-hdr > div:nth-child(5) {{ text-align: right; }}
.moves {{
    display: grid;
    grid-template-columns: 28px 1fr 50px 1fr 50px;
    font-size: 13px;
    font-family: 'SF Mono', Consolas, 'Liberation Mono', monospace;
    padding: 2px 0;
}}
.mn {{
    color: #666;
    text-align: right;
    padding: 4px 4px 4px 2px;
    user-select: none;
}}
.mv {{
    padding: 4px 6px;
    cursor: pointer;
    border-radius: 3px;
    transition: background 0.1s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.mv:hover {{ background: #3d3b39; }}
.mv.cur {{ background: #4a90d9; color: #fff; }}
.mv.empty {{ cursor: default; }}
.mv.empty:hover {{ background: transparent; }}
.ev {{
    padding: 4px 4px;
    text-align: right;
    font-size: 11px;
    color: #777;
    user-select: none;
    white-space: nowrap;
}}

.c-book {{ color: #999; }}
.c-best {{ color: #96bc4b; }}
.c-good {{ color: #96bc4b; }}
.c-inaccuracy {{ color: #e6a817; }}
.c-mistake {{ color: #e68f17; }}
.c-blunder {{ color: #ca3431; }}

.moves-box::-webkit-scrollbar {{ width: 6px; }}
.moves-box::-webkit-scrollbar-track {{ background: #302e2c; }}
.moves-box::-webkit-scrollbar-thumb {{ background: #555; border-radius: 3px; }}

.cls-badge {{
    display: inline-block;
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    margin-left: 4px;
    font-weight: 600;
    vertical-align: middle;
}}
.badge-blunder {{ background: #ca3431; color: #fff; }}
.badge-mistake {{ background: #e68f17; color: #fff; }}
.badge-inaccuracy {{ background: #e6a817; color: #fff; }}
.badge-best {{ background: #96bc4b; color: #fff; }}
</style>
</head>
<body>
<div class="container">
    <div class="eval-col">
        <div class="eval-bar">
            <div class="eval-num top" id="ev-top"></div>
            <div class="eval-fill" id="ev-fill" style="height:50%"></div>
            <div class="eval-num bot" id="ev-bot"></div>
        </div>
    </div>
    <div class="board-area">
        <div class="player-bar top" id="p-top"></div>
        <div class="board-wrap">
            <div class="board" id="board"></div>
            <svg class="arrow-layer" id="arrows" viewBox="0 0 560 560"></svg>
        </div>
        <div class="player-bar bot" id="p-bot"></div>
    </div>
    <div class="panel">
        <div class="info-box" id="info"></div>
        <div class="nav">
            <button id="b-start" title="Home">&#x23EE;</button>
            <button id="b-prev" title="&larr;">&#x25C0;</button>
            <button id="b-play" title="Space">&#x25B6;</button>
            <button id="b-next" title="&rarr;">&#x25B6;</button>
            <button id="b-end" title="End">&#x23ED;</button>
        </div>
        <div class="eval-display" id="ev-text">Starting position</div>
        <div class="moves-box" id="ml-wrap">
            <div class="moves-hdr">
                <div></div><div>White</div><div>Eval</div><div>Black</div><div>Eval</div>
            </div>
            <div class="moves" id="ml"></div>
        </div>
    </div>
</div>
<script>
const P = {positions_json};
const G = {game_info_json};
const URLS = {piece_urls_json};
const CLS = {{book:'Book',best:'Best',good:'Good',inaccuracy:'Inaccuracy',mistake:'Mistake',blunder:'Blunder'}};

let cur = 0, timer = null;
let flip = G.color === 'black';
const SZ = 70;

function init() {{
    info(); players(); buildBoard(); buildMoves();
    go(0);
    document.addEventListener('keydown', onKey);
    $('b-start').onclick = () => go(0);
    $('b-prev').onclick = () => go(cur-1);
    $('b-next').onclick = () => go(cur+1);
    $('b-end').onclick = () => go(P.length-1);
    $('b-play').onclick = autoPlay;
}}

function $(id) {{ return document.getElementById(id); }}

function info() {{
    const r = G.result==='win' ? (G.color==='white'?'1-0':'0-1') :
              G.result==='loss' ? (G.color==='white'?'0-1':'1-0') : '\\u00BD-\\u00BD';
    let h = `<div class="title">${{G.white}} (${{G.white_rating}}) vs ${{G.black}} (${{G.black_rating}})</div><div class="meta">`;
    h += `Result: <span>${{r}}</span><br>`;
    if (G.opening_name) h += `Opening: <span>${{G.opening_eco||''}} ${{G.opening_name}}</span><br>`;
    if (G.time_class) h += `Time: <span>${{G.time_class}}</span><br>`;
    if (G.url) h += `<a href="${{G.url}}" target="_blank">View on Chess.com</a>`;
    h += '</div>';
    $('info').innerHTML = h;
}}

function players() {{
    const tc = flip?'white':'black', bc = flip?'black':'white';
    const tn = tc==='white'?G.white:G.black, tr = tc==='white'?G.white_rating:G.black_rating;
    const bn = bc==='white'?G.white:G.black, br = bc==='white'?G.white_rating:G.black_rating;
    $('p-top').innerHTML = `<span class="player-dot ${{tc}}"></span>${{tn}}<span class="player-rating">${{tr}}</span>`;
    $('p-bot').innerHTML = `<span class="player-dot ${{bc}}"></span>${{bn}}<span class="player-rating">${{br}}</span>`;
}}

function buildBoard() {{
    const b = $('board'); b.innerHTML = '';
    for (let r=0;r<8;r++) for (let c=0;c<8;c++) {{
        const dr = flip?7-r:r, dc = flip?7-c:c;
        const sq = document.createElement('div');
        sq.className = 'sq ' + ((dr+dc)%2===0?'sq-l':'sq-d');
        sq.dataset.r = dr; sq.dataset.c = dc;
        if (c===0) {{ const s=document.createElement('span'); s.className='coord coord-rank'; s.textContent=String(8-dr); sq.appendChild(s); }}
        if (r===7) {{ const s=document.createElement('span'); s.className='coord coord-file'; s.textContent='abcdefgh'[dc]; sq.appendChild(s); }}
        b.appendChild(sq);
    }}
}}

function fmtEval(v) {{
    if (v==null) return '';
    if (Math.abs(v)>=10000) {{
        const n=Math.round(Math.abs(v)-10000);
        if (n===0) return '#';
        return (v>0?'+':'-')+'M'+n;
    }}
    return (v>=0?'+':'')+(v/100).toFixed(1);
}}

function makeEv(p) {{
    const d = document.createElement('div');
    d.className = 'ev';
    if (p.eval_after!=null) d.textContent = fmtEval(p.eval_after);
    return d;
}}

function buildMoves() {{
    const ml = $('ml'); ml.innerHTML = '';
    for (let i=1;i<P.length;i++) {{
        const p = P[i], w = p.ply%2===1;
        if (w) {{
            const n=document.createElement('div'); n.className='mn'; n.textContent=Math.ceil(p.ply/2)+'.'; ml.appendChild(n);
            const d = document.createElement('div');
            const cc = p.classification ? 'c-'+p.classification : '';
            d.className = 'mv '+cc;
            d.dataset.ply = p.ply;
            d.textContent = p.san;
            if (p.classification && CLS[p.classification]) d.title = CLS[p.classification];
            d.onclick = () => go(p.ply);
            ml.appendChild(d);
            ml.appendChild(makeEv(p));
            if (i===P.length-1) {{
                const e=document.createElement('div'); e.className='mv empty'; ml.appendChild(e);
                const ea=document.createElement('div'); ea.className='ev'; ml.appendChild(ea);
            }}
        }} else {{
            const d = document.createElement('div');
            const cc = p.classification ? 'c-'+p.classification : '';
            d.className = 'mv '+cc;
            d.dataset.ply = p.ply;
            d.textContent = p.san;
            if (p.classification && CLS[p.classification]) d.title = CLS[p.classification];
            d.onclick = () => go(p.ply);
            ml.appendChild(d);
            ml.appendChild(makeEv(p));
        }}
    }}
}}

function go(n) {{
    n = Math.max(0, Math.min(P.length-1, n));
    cur = n; const p = P[n];
    renderPieces(p.fen, n);
    evalBar(p);
    evalText(p);
    hlMove(n);
    arrow(p);
}}

function renderPieces(fen, ply) {{
    const sqs = $('board').children;
    const ranks = fen.split(' ')[0].split('/');
    let from=null, to=null;
    if (ply>0) {{
        const u=P[ply].uci;
        if (u&&u.length>=4) {{ from=uci2rc(u.slice(0,2)); to=uci2rc(u.slice(2,4)); }}
    }}
    const pcs = {{}};
    for (let r=0;r<8;r++) {{ let c=0; for (const ch of ranks[r]) {{ if (ch>='1'&&ch<='8') c+=+ch; else {{ pcs[r+','+c]=ch; c++; }} }} }}
    for (let i=0;i<64;i++) {{
        const sq=sqs[i], r=+sq.dataset.r, c=+sq.dataset.c;
        const light=(r+c)%2===0;
        sq.className='sq '+(light?'sq-l':'sq-d');
        if (from&&r===from[0]&&c===from[1]) sq.classList.add('hl');
        if (to&&r===to[0]&&c===to[1]) sq.classList.add('hl');
        let img=sq.querySelector('img');
        const pc=pcs[r+','+c];
        if (pc) {{
            if (!img) {{ img=document.createElement('img'); sq.appendChild(img); }}
            const url = URLS[pc];
            if (img.src !== url) img.src = url;
        }} else if (img) {{ img.remove(); }}
    }}
}}

function uci2rc(s) {{ return [8-+s[1], s.charCodeAt(0)-97]; }}
function rc2px(r,c) {{ const dc=flip?7-c:c, dr=flip?7-r:r; return [dc*SZ+SZ/2, dr*SZ+SZ/2]; }}

function arrow(p) {{
    const svg=$('arrows'); svg.innerHTML='';
    if (!p.best_uci||p.best_uci.length<4) return;
    if (p.classification!=='mistake'&&p.classification!=='blunder') return;
    const f=uci2rc(p.best_uci.slice(0,2)), t=uci2rc(p.best_uci.slice(2,4));
    const [x1,y1]=rc2px(f[0],f[1]), [x2,y2]=rc2px(t[0],t[1]);
    const col = p.classification==='blunder'?'rgba(202,52,49,0.8)':'rgba(230,143,23,0.8)';
    svg.innerHTML=`<defs><marker id="ah" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="${{col}}"/></marker></defs>`+
        `<line x1="${{x1}}" y1="${{y1}}" x2="${{x2}}" y2="${{y2}}" stroke="${{col}}" stroke-width="10" stroke-linecap="round" marker-end="url(#ah)" opacity="0.9"/>`+
        `<circle cx="${{x1}}" cy="${{y1}}" r="10" fill="${{col}}" opacity="0.5"/>`;
}}

function evalBar(p) {{
    let v = p.eval_after;
    if (v==null&&p.ply===0) v=0;
    if (v==null) for (let i=p.ply-1;i>=0;i--) {{ if (P[i].eval_after!=null) {{ v=P[i].eval_after; break; }} }}
    if (v==null) v=0;
    const isMate=Math.abs(v)>=10000;
    const clamped=isMate?(v>0?1000:-1000):Math.max(-1000,Math.min(1000,v));
    const pct=50+(clamped/1000)*50;
    $('ev-fill').style.height=pct+'%';
    const abs=Math.abs(v), mn=Math.round(abs-10000), disp=abs>=10000?(mn===0?'#':'M'+mn):(abs/100).toFixed(1);
    if (v>=0) {{ $('ev-top').textContent=''; $('ev-bot').textContent=disp; $('ev-bot').style.color='#444'; }}
    else {{ $('ev-top').textContent=disp; $('ev-top').style.color='#ddd'; $('ev-bot').textContent=''; }}
}}

function evalText(p) {{
    const el=$('ev-text');
    if (p.ply===0) {{ el.textContent='Starting position'; return; }}
    let t=p.san;
    if (p.eval_after!=null) {{
        const v=p.eval_after;
        const mn=Math.round(Math.abs(v)-10000);
        t += '  ['+(Math.abs(v)>=10000?(mn===0?'#':(v>0?'+':'-')+'M'+mn):(v>=0?'+':'')+(v/100).toFixed(2))+']';
    }}
    if (p.classification&&CLS[p.classification]) {{
        t += '  '+CLS[p.classification];
    }}
    if (p.best_san&&(p.classification==='mistake'||p.classification==='blunder'||p.classification==='inaccuracy')) {{
        t += '  (best: '+p.best_san+')';
    }}
    el.textContent=t;
}}

function hlMove(ply) {{
    document.querySelectorAll('.mv.cur').forEach(e=>e.classList.remove('cur'));
    if (ply>0) {{ const c=document.querySelector(`.mv[data-ply="${{ply}}"]`); if(c){{ c.classList.add('cur'); c.scrollIntoView({{block:'nearest',behavior:'smooth'}}); }} }}
}}

function autoPlay() {{
    const btn=$('b-play');
    if (timer) {{ clearInterval(timer); timer=null; btn.classList.remove('on'); btn.innerHTML='\\u25B6'; }}
    else {{ if(cur>=P.length-1) go(0); btn.classList.add('on'); btn.innerHTML='\\u23F8'; timer=setInterval(()=>{{ if(cur>=P.length-1){{autoPlay();return;}} go(cur+1); }},800); }}
}}

function onKey(e) {{
    if (e.key==='ArrowLeft') {{ e.preventDefault(); go(cur-1); }}
    else if (e.key==='ArrowRight') {{ e.preventDefault(); go(cur+1); }}
    else if (e.key==='Home') {{ e.preventDefault(); go(0); }}
    else if (e.key==='End') {{ e.preventDefault(); go(P.length-1); }}
    else if (e.key===' ') {{ e.preventDefault(); autoPlay(); }}
}}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


@app.callback(invoke_without_command=True)
def review(
    game_id: str = typer.Argument(..., help="Game ID to review"),
    json_: bool = typer.Option(False, "--json"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    """Open an analyzed game in the browser for interactive review."""
    conn = get_connection(db)
    create_schema(conn)

    game = get_game(conn, game_id)
    if not game:
        print_error(f"Game {game_id!r} not found. Run `chess sync` first.", json_)
        return

    if not game.get("analyzed"):
        print_error(
            f"Game {game_id!r} has not been analyzed. Run `chess analyze {game_id}` first.",
            json_,
        )
        return

    moves = get_moves(conn, game_id)
    positions = _build_positions(game["pgn"], moves)

    if not positions:
        print_error(f"Could not parse PGN for game {game_id!r}.", json_)
        return

    game_info = {
        "id": game["id"],
        "white": game["white_username"],
        "white_rating": game["white_rating"],
        "black": game["black_username"],
        "black_rating": game["black_rating"],
        "result": game["result"],
        "color": game["color"],
        "time_class": game["time_class"],
        "opening_eco": game.get("opening_eco"),
        "opening_name": game.get("opening_name"),
        "url": game["url"],
    }

    html = _generate_html(game_info, positions)

    tmp_dir = Path(tempfile.mkdtemp(prefix="chess-review-"))
    html_path = tmp_dir / f"review-{game_id}.html"
    html_path.write_text(html)

    if json_:
        print_output({"path": str(html_path), "game_id": game_id}, json_mode=True)
    else:
        console.print(f"[dim]Opening review in browser...[/dim]")
        webbrowser.open(f"file://{html_path}")
