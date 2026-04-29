import streamlit as st
import requests
import time
import math
import pandas as pd
from datetime import datetime
from itertools import product as iproduct

# ─────────────────────────────────────────
#  CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Odds Monitor + Poisson",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
#  ESTILOS
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Barlow', sans-serif; background-color: #0d1117; color: #e6edf3; }
.main { background-color: #0d1117; }
section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }

/* ── Cards ── */
.metric-card {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
}
.metric-card.alert { border-color: #f85149; box-shadow: 0 0 12px rgba(248,81,73,.3); }
.metric-card.up    { border-color: #3fb950; box-shadow: 0 0 12px rgba(63,185,80,.25); }
.match-title { font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }
.odd-value   { font-family: 'Share Tech Mono', monospace; font-size: 22px; font-weight: 700; }
.odd-prev    { font-family: 'Share Tech Mono', monospace; font-size: 13px; color: #8b949e; }
.tick-badge  { display:inline-block; padding:2px 10px; border-radius:20px;
               font-size:13px; font-weight:700; font-family:'Share Tech Mono',monospace; }
.tick-down { background:rgba(248,81,73,.15); color:#f85149; }
.tick-up   { background:rgba(63,185,80,.15);  color:#3fb950; }
.tick-flat { background:rgba(139,148,158,.1); color:#8b949e; }

/* ── Alert log ── */
.alert-log { background:#161b22; border:1px solid #30363d; border-radius:10px;
             padding:12px 16px; font-family:'Share Tech Mono',monospace; font-size:13px;
             max-height:320px; overflow-y:auto; }
.alert-row { padding:5px 0; border-bottom:1px solid #21262d; }
.alert-row:last-child { border-bottom:none; }

/* ── Header ── */
.header-bar { background:linear-gradient(90deg,#161b22 0%,#1c2128 100%);
              border:1px solid #30363d; border-radius:12px;
              padding:16px 24px; margin-bottom:24px; }
.req-counter { font-family:'Share Tech Mono',monospace; font-size:12px; color:#8b949e; }
.status-dot  { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-green { background:#3fb950; box-shadow:0 0 6px #3fb950; }
.dot-red   { background:#f85149; }

/* ── Poisson matrix ── */
.poisson-wrap { background:#161b22; border:1px solid #30363d; border-radius:12px;
                padding:16px; margin-top:8px; overflow-x:auto; }
.poisson-wrap table { border-collapse:collapse; width:100%; font-family:'Share Tech Mono',monospace; font-size:12px; }
.poisson-wrap th { background:#21262d; color:#8b949e; padding:6px 8px; text-align:center; border:1px solid #30363d; }
.poisson-wrap td { padding:5px 7px; text-align:center; border:1px solid #21262d; font-size:11px; }
.cell-hot  { color:#f85149; font-weight:700; }
.cell-warm { color:#e3b341; }
.cell-cool { color:#58a6ff; }
.cell-cold { color:#8b949e; }

/* ── CS table ── */
.cs-wrap { background:#161b22; border:1px solid #30363d; border-radius:12px;
           padding:16px; max-height:520px; overflow-y:auto; }
.cs-wrap table { border-collapse:collapse; width:100%; font-family:'Share Tech Mono',monospace; font-size:12px; }
.cs-wrap th { background:#21262d; color:#8b949e; padding:6px 10px; text-align:center;
              border:1px solid #30363d; position:sticky; top:0; z-index:1; }
.cs-wrap td { padding:5px 10px; text-align:center; border:1px solid #21262d; }
.cs-home { color:#3fb950; } .cs-draw { color:#e3b341; } .cs-away { color:#f85149; }
.cs-odd  { color:#e6edf3; font-weight:600; }
.section-title { font-size:14px; font-weight:700; color:#8b949e;
                 text-transform:uppercase; letter-spacing:.08em; margin:16px 0 8px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
#  TICK TABLE
# ─────────────────────────────────────────
@st.cache_resource
def build_tick_table():
    ticks = []
    steps = [(1.01,2.00,.01),(2.00,3.00,.02),(3.00,4.00,.05),(4.00,6.00,.10),
             (6.00,10.00,.20),(10.00,20.00,.50),(20.00,30.00,1.),(30.00,50.00,2.),
             (50.00,100.00,5.),(100.00,1000.00,10.)]
    for s,e,st_ in steps:
        v=s
        while v<=e+1e-9:
            ticks.append(round(v,2)); v=round(v+st_,2)
    return sorted(set(ticks))

TICK_TABLE = build_tick_table()

def tick_diff(old,new):
    def idx(o): return min(range(len(TICK_TABLE)), key=lambda i:abs(TICK_TABLE[i]-o))
    return idx(new)-idx(old)


# ─────────────────────────────────────────
#  POISSON
# ─────────────────────────────────────────
def poisson_prob(lam: float, k: int) -> float:
    return (math.exp(-lam) * (lam**k)) / math.factorial(k)

def build_poisson_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10):
    """Retorna matriz [home_goals][away_goals] com probabilidades."""
    matrix = []
    for h in range(max_goals + 1):
        row = []
        for a in range(max_goals + 1):
            row.append(poisson_prob(lambda_home, h) * poisson_prob(lambda_away, a))
        matrix.append(row)
    return matrix

def extract_1x2_from_matrix(matrix):
    home_win = sum(matrix[h][a] for h in range(len(matrix)) for a in range(h))
    draw     = sum(matrix[i][i] for i in range(len(matrix)))
    away_win = sum(matrix[h][a] for h in range(len(matrix)) for a in range(h+1, len(matrix[0])))
    return home_win, draw, away_win

def fair_odd(prob: float) -> float:
    if prob <= 0: return 999.0
    return round(1 / prob, 2)

def build_cs_table(matrix, max_goals=10):
    """
    Lista fixa de placares conforme imagem de referência + LGH e LGA.
    LGH = soma prob de todos placares onde gols casa >= 4
    LGA = soma prob de todos placares onde gols visitante >= 4
    """
    FIXED_SCORES = [
        (0,0),(1,0),(0,1),
        (2,0),(2,1),(2,2),
        (0,2),(1,2),(2,3),
        (3,0),(3,1),(3,2),
        (3,3),(0,3),(1,3),(2,3)
    ]

    rows = []
    for (h, a) in FIXED_SCORES:
        prob = matrix[h][a] if h < len(matrix) and a < len(matrix[0]) else 0.0
        odd  = fair_odd(prob)
        tipo = "home" if h > a else ("draw" if h == a else "away")
        rows.append((f"{h}x{a}", prob, odd, tipo))

    # LGH: gols casa >= 4 (qualquer placar onde h >= 4)
    prob_lgh = sum(
        matrix[h][a]
        for h in range(4, max_goals + 1)
        for a in range(max_goals + 1)
    )
    rows.append(("LGH", prob_lgh, fair_odd(prob_lgh), "lgh"))

    # LGA: gols visitante >= 4 (qualquer placar onde a >= 4)
    prob_lga = sum(
        matrix[h][a]
        for h in range(max_goals + 1)
        for a in range(4, max_goals + 1)
    )
    rows.append(("LGA", prob_lga, fair_odd(prob_lga), "lga"))

    return rows


# ─────────────────────────────────────────
#  ODDS API
# ─────────────────────────────────────────
LIGAS = {
    "🇧🇷 Brasileirão Série A":    "soccer_brazil_campeonato",
    "🇧🇷 Brasileirão Série B":    "soccer_brazil_serie_b",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League":         "soccer_epl",
    "🇩🇪 Bundesliga":             "soccer_germany_bundesliga",
    "🇪🇸 La Liga":                "soccer_spain_la_liga",
    "🇮🇹 Serie A":                "soccer_italy_serie_a",
    "🇫🇷 Ligue 1":                "soccer_france_ligue_one",
    "⭐ Champions League":        "soccer_uefa_champs_league",
    "🌎 Copa Libertadores":       "soccer_conmebol_copa_libertadores",
}

def fetch_odds(sport, api_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {"apiKey": api_key, "regions": "eu", "markets": "h2h",
              "oddsFormat": "decimal", "inPlay": "true"}
    try:
        r = requests.get(url, params=params, timeout=15)
        remaining = int(r.headers.get("x-requests-remaining", -1))
        return (r.json(), remaining) if r.status_code == 200 else ([], -1)
    except:
        return [], -1

def parse_games(games):
    result = {}
    for g in games:
        gid  = g.get("id")
        home = g.get("home_team","Casa")
        away = g.get("away_team","Fora")
        ho, ao = None, None
        for bk in g.get("bookmakers",[]):
            for mkt in bk.get("markets",[]):
                if mkt.get("key")=="h2h":
                    for o in mkt.get("outcomes",[]):
                        if o["name"]==home: ho=o["price"]
                        elif o["name"]==away: ao=o["price"]
                    break
            if ho and ao: break
        if ho and ao:
            result[gid] = {"match": f"{home} vs {away}", "home_team": home,
                           "away_team": away, "home": ho, "away": ao}
    return result

def implied_lambdas(home_odd, away_odd):
    """Estima lambdas de Poisson a partir das odds 1x2 (aproximação)."""
    # Probabilidades implícitas (removendo margem simples)
    p_h = 1 / home_odd
    p_a = 1 / away_odd
    total = p_h + p_a
    p_h /= total; p_a /= total
    # Relação empírica: lambda médio ~2.7 gols por jogo
    # lambda_home / lambda_away ≈ (p_h / p_a) ^ 0.65
    ratio  = (p_h / p_a) ** 0.65
    lam_h  = round(1.35 * ratio, 3)   # média ~1.35 gols casa
    lam_a  = round(1.35 / ratio, 3)   # média ~1.35 gols fora
    return lam_h, lam_a


# ─────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────
def send_telegram(token, chat_id, text):
    if not token or not chat_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id":chat_id,"text":text,"parse_mode":"HTML"}, timeout=8)
    except: pass


# ─────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────
defaults = {"previous":{}, "alerts":[], "running":False, "req_left":"—",
            "last_check":"—", "current":{}, "games_data":{},
            "selected_game":None, "tg_token":"", "tg_chat":""}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v


# ─────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ Odds Monitor")
    st.markdown("---")

    api_key = st.text_input("🔑 The Odds API Key", type="password", placeholder="sua chave aqui")

    st.markdown("---")
    liga_label = st.selectbox("🏆 Liga", list(LIGAS.keys()))
    sport      = LIGAS[liga_label]

    # Botão buscar partidas
    if st.button("🔄 Buscar partidas ao vivo", use_container_width=True):
        if api_key:
            with st.spinner("Buscando..."):
                games_raw, remaining = fetch_odds(sport, api_key)
                st.session_state.games_data = parse_games(games_raw)
                st.session_state.req_left   = remaining
                st.session_state.last_check = datetime.now().strftime("%H:%M:%S")
        else:
            st.warning("Insira a API Key primeiro.")

    # Dropdown de confrontos
    game_options = {}
    if st.session_state.games_data:
        for gid, d in st.session_state.games_data.items():
            game_options[d["match"]] = gid

    selected_match = st.selectbox(
        "⚽ Confronto",
        options=["— selecione —"] + list(game_options.keys())
    )
    if selected_match != "— selecione —" and selected_match in game_options:
        st.session_state.selected_game = game_options[selected_match]
    else:
        st.session_state.selected_game = None

    st.markdown("---")
    st.markdown("**⚙️ Monitor de Odds**")
    tg_token  = st.text_input("🤖 Telegram Bot Token", type="password",
                               value=st.session_state.tg_token, placeholder="opcional")
    tg_chat   = st.text_input("💬 Telegram Chat ID",
                               value=st.session_state.tg_chat, placeholder="opcional")
    st.session_state.tg_token = tg_token
    st.session_state.tg_chat  = tg_chat

    threshold = st.slider("⚠️ Threshold (ticks)", 3, 30, 10)
    interval  = st.select_slider("⏱ Intervalo", options=[5,10,15,30,60], value=10)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ Iniciar", use_container_width=True, type="primary"):
            st.session_state.running  = True
            st.session_state.previous = {}
            st.session_state.alerts   = []
    with col2:
        if st.button("⏹ Parar", use_container_width=True):
            st.session_state.running = False

    st.markdown(f"""
    <div class='req-counter' style='margin-top:12px'>
    Req. restantes: <b>{st.session_state.req_left}</b><br>
    Última consulta: <b>{st.session_state.last_check}</b>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────
status_dot = ('<span class="status-dot dot-green"></span>MONITORANDO'
              if st.session_state.running else
              '<span class="status-dot dot-red"></span>PARADO')

st.markdown(f"""
<div class="header-bar">
  <div style="font-size:20px;font-weight:700">⚡ Odds Monitor — Back Casa / Back Fora + Poisson CS</div>
  <div style="font-size:13px;color:#8b949e;margin-top:4px">
    {status_dot} &nbsp;|&nbsp; {liga_label} &nbsp;|&nbsp;
    Threshold: <b>{threshold} ticks</b> &nbsp;|&nbsp; Intervalo: <b>{interval}s</b>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
#  LAYOUT PRINCIPAL — 3 colunas
# ─────────────────────────────────────────
col_monitor, col_matrix, col_cs = st.columns([2, 3, 2], gap="medium")

# ── Coluna 1: Monitor de odds
with col_monitor:
    st.markdown("#### 🟢 Partidas ao vivo")
    games_ph = st.empty()

# ── Coluna 2: Matriz Poisson
with col_matrix:
    st.markdown("#### 🔢 Matriz de Poisson")
    matrix_ph = st.empty()

# ── Coluna 3: Tabela Correct Score
with col_cs:
    st.markdown("#### 🎯 Correct Score — Odds Justas")
    cs_ph = st.empty()


# ─────────────────────────────────────────
#  FUNÇÕES DE RENDER
# ─────────────────────────────────────────
def cell_class(prob):
    if prob >= 0.08: return "cell-hot"
    if prob >= 0.04: return "cell-warm"
    if prob >= 0.01: return "cell-cool"
    return "cell-cold"

def render_matrix(game_data):
    if not game_data:
        matrix_ph.info("Selecione um confronto para ver a matriz.")
        return

    lam_h, lam_a = implied_lambdas(game_data["home"], game_data["away"])
    matrix = build_poisson_matrix(lam_h, lam_a, max_goals=10)
    hw, dr, aw = extract_1x2_from_matrix(matrix)

    header = f"""
    <div style='margin-bottom:10px;font-family:Share Tech Mono,monospace;font-size:13px'>
      <span style='color:#58a6ff'>λ Casa: <b>{lam_h}</b></span> &nbsp;|&nbsp;
      <span style='color:#f85149'>λ Fora: <b>{lam_a}</b></span><br>
      <span style='color:#3fb950'>Casa: {hw*100:.1f}%</span> &nbsp;|&nbsp;
      <span style='color:#e3b341'>Empate: {dr*100:.1f}%</span> &nbsp;|&nbsp;
      <span style='color:#f85149'>Fora: {aw*100:.1f}%</span>
    </div>"""

    # Cabeçalho da tabela (gols fora 0..10)
    thead = "<tr><th>C╲F</th>" + "".join(f"<th>{a}</th>" for a in range(11)) + "</tr>"
    tbody = ""
    for h in range(11):
        tbody += f"<tr><th>{h}</th>"
        for a in range(11):
            prob = matrix[h][a]
            pct  = f"{prob*100:.2f}%"
            cls  = cell_class(prob)
            tbody += f"<td class='{cls}'>{pct}</td>"
        tbody += "</tr>"

    html = f"""
    {header}
    <div class='poisson-wrap'>
      <table><thead>{thead}</thead><tbody>{tbody}</tbody></table>
    </div>"""
    matrix_ph.markdown(html, unsafe_allow_html=True)

def render_cs(game_data):
    if not game_data:
        cs_ph.info("Selecione um confronto.")
        return

    lam_h, lam_a = implied_lambdas(game_data["home"], game_data["away"])
    matrix = build_poisson_matrix(lam_h, lam_a, max_goals=10)
    cs_rows = build_cs_table(matrix, max_goals=10)

    COLOR_MAP = {
        "home": "#3fb950", "draw": "#e3b341",
        "away": "#f85149", "lgh":  "#58a6ff", "lga": "#bf91f3",
    }
    rows_html = ""
    for i, (score, prob, odd, tipo) in enumerate(cs_rows):
        color = COLOR_MAP.get(tipo, "#e6edf3")
        bg    = "background:#1c2128;" if i % 2 == 0 else ""
        sep   = "border-top:1px solid #30363d;" if score in ("LGH","LGA") else ""
        rows_html += (
            f"<tr style='{bg}{sep}'>"
            f"<td style='color:{color};font-weight:700;font-family:Share Tech Mono,monospace'>{score}</td>"
            f"<td style='color:#8b949e;font-family:Share Tech Mono,monospace'>{prob*100:.2f}%</td>"
            f"<td style='color:#e6edf3;font-weight:700;font-family:Share Tech Mono,monospace'>{odd}</td>"
            f"</tr>"
        )
    html = (
        "<div class='cs-wrap'>"
        "<table><thead><tr><th>Placar</th><th>Prob%</th><th>Odd Justa</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div>"
    )
    cs_ph.markdown(html, unsafe_allow_html=True)

def render_games(current, previous, threshold):
    if not current:
        games_ph.info("Nenhuma partida ao vivo.")
        return
    html = ""
    for gid, data in current.items():
        prev = previous.get(gid)
        match = data["match"]
        for side, label, icon in [("home","Back Casa","🏠"),("away","Back Fora","✈️")]:
            odd_new = data[side]
            odd_old = prev[side] if prev else odd_new
            diff    = tick_diff(odd_old, odd_new) if prev else 0
            card_cls = ("alert" if diff<0 and abs(diff)>=threshold else
                        "up"    if diff>0 and abs(diff)>=threshold else "")
            odd_color = ("#f85149" if diff<0 and abs(diff)>=threshold else
                         "#3fb950" if diff>0 and abs(diff)>=threshold else "#e6edf3")
            if diff<0:   tk_cls,tk_sym = "tick-down", f"▼ {abs(diff)} ticks"
            elif diff>0: tk_cls,tk_sym = "tick-up",   f"▲ {diff} ticks"
            else:        tk_cls,tk_sym = "tick-flat",  "— 0 ticks"
            html += f"""
            <div class="metric-card {card_cls}">
              <div class="match-title">{match}</div>
              <div style="display:flex;align-items:center;justify-content:space-between;margin-top:6px">
                <div>
                  <span style="font-size:13px;color:#8b949e">{icon} {label}</span><br>
                  <span class="odd-value" style="color:{odd_color}">{odd_new}</span>
                  {"<span class='odd-prev'>&nbsp; ant: "+str(odd_old)+"</span>" if prev else ""}
                </div>
                <span class="tick-badge {tk_cls}">{tk_sym}</span>
              </div>
            </div>"""
    games_ph.markdown(html, unsafe_allow_html=True)

def render_alerts(alerts):
    if not alerts:
        return
    rows=""
    for a in reversed(alerts[-40:]):
        color="#f85149" if a["diff"]<0 else "#3fb950"
        sym="▼" if a["diff"]<0 else "▲"
        rows+=f"""<div class="alert-row">
          <span style="color:#8b949e">{a['time']}</span>&nbsp;
          <span style="color:#58a6ff">{a['match']}</span>&nbsp;
          <span style="color:#8b949e">{a['label']}</span>&nbsp;
          <span style="color:{color};font-weight:700">{sym}{abs(a['diff'])}t</span>&nbsp;
          <span style="color:#e6edf3">{a['old']}→{a['new']}</span>
        </div>"""
    st.markdown("#### 🚨 Log de Alertas")
    st.markdown(f'<div class="alert-log">{rows}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────
#  POISSON DO CONFRONTO SELECIONADO
# ─────────────────────────────────────────
selected_data = None
if st.session_state.selected_game and st.session_state.selected_game in st.session_state.games_data:
    selected_data = st.session_state.games_data[st.session_state.selected_game]

render_matrix(selected_data)
render_cs(selected_data)


# ─────────────────────────────────────────
#  LOOP DO MONITOR
# ─────────────────────────────────────────
if st.session_state.running:
    if not api_key:
        st.error("⚠️ Insira sua API Key na barra lateral.")
        st.stop()

    games_raw, remaining = fetch_odds(sport, api_key)
    current = parse_games(games_raw)

    st.session_state.last_check = datetime.now().strftime("%H:%M:%S")
    if remaining >= 0: st.session_state.req_left = remaining

    # Atualiza dados do confronto selecionado
    if st.session_state.selected_game and st.session_state.selected_game in current:
        st.session_state.games_data[st.session_state.selected_game] = \
            current[st.session_state.selected_game]

    # Detecta alertas
    for gid, data in current.items():
        prev = st.session_state.previous.get(gid)
        if prev:
            for side, label in [("home","Casa"),("away","Fora")]:
                diff = tick_diff(prev[side], data[side])
                if abs(diff) >= threshold:
                    alert = {"time": st.session_state.last_check,
                             "match": data["match"], "label": label,
                             "old": prev[side], "new": data[side], "diff": diff}
                    st.session_state.alerts.append(alert)
                    dir_str = "📉 QUEDA" if diff<0 else "📈 SUBIDA"
                    send_telegram(tg_token, tg_chat,
                        f"⚡ <b>ALERTA DE ODDS</b>\n\n🏟 <b>{data['match']}</b>\n"
                        f"📊 Back {label}\nOdd anterior: <b>{prev[side]}</b>\n"
                        f"Odd atual: <b>{data[side]}</b>\n{dir_str}: <b>{abs(diff)} ticks</b>\n"
                        f"🕐 {st.session_state.last_check}")

    st.session_state.current  = current
    st.session_state.previous = current
    render_games(current, st.session_state.previous, threshold)
    render_alerts(st.session_state.alerts)

    time.sleep(interval)
    st.rerun()

else:
    render_games(st.session_state.current, {}, threshold)
    render_alerts(st.session_state.alerts)
    if not st.session_state.current:
        games_ph.markdown(
            '<div style="color:#8b949e;padding:16px">Configure e clique em ▶ Iniciar.</div>',
            unsafe_allow_html=True)
