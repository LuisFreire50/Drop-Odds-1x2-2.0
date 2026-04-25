import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Odds Monitor",
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

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
}

.main { background-color: #0d1117; }

.metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.metric-card.alert {
    border-color: #f85149;
    box-shadow: 0 0 12px rgba(248,81,73,0.3);
}
.metric-card.up {
    border-color: #3fb950;
    box-shadow: 0 0 12px rgba(63,185,80,0.25);
}

.match-title {
    font-size: 15px;
    font-weight: 700;
    color: #58a6ff;
    margin-bottom: 4px;
}
.odd-value {
    font-family: 'Share Tech Mono', monospace;
    font-size: 22px;
    font-weight: 700;
}
.odd-prev {
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    color: #8b949e;
}
.tick-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    font-family: 'Share Tech Mono', monospace;
}
.tick-down { background: rgba(248,81,73,0.15); color: #f85149; }
.tick-up   { background: rgba(63,185,80,0.15);  color: #3fb950; }
.tick-flat { background: rgba(139,148,158,0.1); color: #8b949e; }

.alert-log {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 16px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    max-height: 320px;
    overflow-y: auto;
}
.alert-row { padding: 5px 0; border-bottom: 1px solid #21262d; }
.alert-row:last-child { border-bottom: none; }

.status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
.dot-green { background: #3fb950; box-shadow: 0 0 6px #3fb950; }
.dot-red   { background: #f85149; }

.header-bar {
    background: linear-gradient(90deg, #161b22 0%, #1c2128 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.req-counter {
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: #8b949e;
}

div[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
#  TABELA DE TICKS BETFAIR
# ─────────────────────────────────────────
@st.cache_resource
def build_tick_table():
    ticks = []
    steps = [
        (1.01, 2.00, 0.01), (2.00, 3.00, 0.02), (3.00, 4.00, 0.05),
        (4.00, 6.00, 0.10), (6.00, 10.00, 0.20), (10.00, 20.00, 0.50),
        (20.00, 30.00, 1.00), (30.00, 50.00, 2.00), (50.00, 100.00, 5.00),
        (100.00, 1000.00, 10.00)
    ]
    for start, end, step in steps:
        v = start
        while v <= end + 1e-9:
            ticks.append(round(v, 2))
            v = round(v + step, 2)
    return sorted(set(ticks))

TICK_TABLE = build_tick_table()

def tick_diff(old: float, new: float) -> int:
    def idx(o):
        return min(range(len(TICK_TABLE)), key=lambda i: abs(TICK_TABLE[i] - o))
    return idx(new) - idx(old)


# ─────────────────────────────────────────
#  ODDS API
# ─────────────────────────────────────────
LIGAS = {
    "🇧🇷 Brasileirão Série A":      "soccer_brazil_campeonato",
    "🇧🇷 Brasileirão Série B":      "soccer_brazil_serie_b",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League":           "soccer_epl",
    "🇩🇪 Bundesliga":               "soccer_germany_bundesliga",
    "🇪🇸 La Liga":                  "soccer_spain_la_liga",
    "🇮🇹 Serie A":                  "soccer_italy_serie_a",
    "🇫🇷 Ligue 1":                  "soccer_france_ligue_one",
    "⭐ Champions League":          "soccer_uefa_champs_league",
    "🌎 Copa Libertadores":         "soccer_conmebol_copa_libertadores",
}

def fetch_odds(sport: str, api_key: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "inPlay": "true"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        remaining = int(r.headers.get("x-requests-remaining", -1))
        if r.status_code == 200:
            return r.json(), remaining
        else:
            return [], -1
    except:
        return [], -1

def parse_odds(games):
    result = {}
    for g in games:
        gid  = g.get("id")
        home = g.get("home_team", "Casa")
        away = g.get("away_team", "Fora")
        ho, ao = None, None
        for bk in g.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt.get("key") == "h2h":
                    for o in mkt.get("outcomes", []):
                        if o["name"] == home: ho = o["price"]
                        elif o["name"] == away: ao = o["price"]
                    break
            if ho and ao: break
        if ho and ao:
            result[gid] = {"match": f"{home} vs {away}", "home": ho, "away": ao,
                           "home_team": home, "away_team": away}
    return result


# ─────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────
def send_telegram(token, chat_id, text):
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8
        )
    except:
        pass


# ─────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────
if "previous"   not in st.session_state: st.session_state.previous   = {}
if "alerts"     not in st.session_state: st.session_state.alerts     = []
if "running"    not in st.session_state: st.session_state.running    = False
if "req_left"   not in st.session_state: st.session_state.req_left   = "—"
if "last_check" not in st.session_state: st.session_state.last_check = "—"
if "current"    not in st.session_state: st.session_state.current    = {}


# ─────────────────────────────────────────
#  SIDEBAR — CONFIGURAÇÕES
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ Odds Monitor")
    st.markdown("---")

    api_key   = st.text_input("🔑 The Odds API Key", type="password", placeholder="sua chave aqui")
    tg_token  = st.text_input("🤖 Telegram Bot Token", type="password", placeholder="opcional")
    tg_chat   = st.text_input("💬 Telegram Chat ID", placeholder="opcional")

    st.markdown("---")

    liga_label = st.selectbox("🏆 Liga", list(LIGAS.keys()))
    sport      = LIGAS[liga_label]

    threshold  = st.slider("⚠️ Threshold (ticks)", min_value=3, max_value=30, value=10)
    interval   = st.select_slider("⏱ Intervalo", options=[5, 10, 15, 30, 60], value=10)

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

    st.markdown("---")
    st.markdown(f"""
    <div class='req-counter'>
    Requisições restantes: <b>{st.session_state.req_left}</b><br>
    Última consulta: <b>{st.session_state.last_check}</b>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────
status_dot = '<span class="status-dot dot-green"></span>MONITORANDO' \
             if st.session_state.running else \
             '<span class="status-dot dot-red"></span>PARADO'

st.markdown(f"""
<div class="header-bar">
  <div style="font-size:26px">⚡</div>
  <div>
    <div style="font-size:20px; font-weight:700; font-family:'Barlow',sans-serif">
      Odds Monitor — Back Casa / Back Fora
    </div>
    <div style="font-size:13px; color:#8b949e; margin-top:2px">
      {status_dot} &nbsp;|&nbsp; {liga_label} &nbsp;|&nbsp; 
      Threshold: <b>{threshold} ticks</b> &nbsp;|&nbsp; 
      Intervalo: <b>{interval}s</b>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
#  LAYOUT PRINCIPAL
# ─────────────────────────────────────────
col_games, col_alerts = st.columns([3, 2], gap="large")

with col_games:
    st.markdown("#### 🟢 Partidas ao vivo")
    games_placeholder = st.empty()

with col_alerts:
    st.markdown("#### 🚨 Log de Alertas")
    alerts_placeholder = st.empty()


# ─────────────────────────────────────────
#  FUNÇÕES DE RENDER
# ─────────────────────────────────────────
def render_games(current, previous, threshold):
    if not current:
        games_placeholder.info("Nenhuma partida ao vivo encontrada para esta liga.")
        return

    html = ""
    for gid, data in current.items():
        prev = previous.get(gid)
        match = data["match"]

        for side, label, icon in [("home", "Back Casa", "🏠"), ("away", "Back Fora", "✈️")]:
            odd_new = data[side]
            odd_old = prev[side] if prev else odd_new
            diff    = tick_diff(odd_old, odd_new) if prev else 0

            if abs(diff) >= threshold:
                card_class = "alert" if diff < 0 else "up"
            else:
                card_class = ""

            odd_color = "#f85149" if diff < 0 and abs(diff) >= threshold else \
                        "#3fb950" if diff > 0 and abs(diff) >= threshold else "#e6edf3"

            if diff < 0:
                tick_class, tick_sym = "tick-down", f"▼ {abs(diff)} ticks"
            elif diff > 0:
                tick_class, tick_sym = "tick-up", f"▲ {diff} ticks"
            else:
                tick_class, tick_sym = "tick-flat", "— 0 ticks"

            html += f"""
            <div class="metric-card {card_class}">
              <div class="match-title">{match}</div>
              <div style="display:flex; align-items:center; justify-content:space-between; margin-top:6px">
                <div>
                  <span style="font-size:13px;color:#8b949e">{icon} {label}</span><br>
                  <span class="odd-value" style="color:{odd_color}">{odd_new}</span>
                  {"<span class='odd-prev'>&nbsp; ant: " + str(odd_old) + "</span>" if prev else ""}
                </div>
                <span class="tick-badge {tick_class}">{tick_sym}</span>
              </div>
            </div>"""

    games_placeholder.markdown(html, unsafe_allow_html=True)


def render_alerts(alerts):
    if not alerts:
        alerts_placeholder.markdown(
            '<div class="alert-log" style="color:#8b949e">Nenhum alerta ainda...</div>',
            unsafe_allow_html=True)
        return

    rows = ""
    for a in reversed(alerts[-40:]):
        color = "#f85149" if a["diff"] < 0 else "#3fb950"
        sym   = "▼" if a["diff"] < 0 else "▲"
        rows += f"""
        <div class="alert-row">
          <span style="color:#8b949e">{a['time']}</span>&nbsp;
          <span style="color:#58a6ff">{a['match']}</span>&nbsp;
          <span style="color:#8b949e">{a['label']}</span>&nbsp;
          <span style="color:{color};font-weight:700">{sym}{abs(a['diff'])}t</span>&nbsp;
          <span style="color:#e6edf3">{a['old']} → {a['new']}</span>
        </div>"""

    alerts_placeholder.markdown(
        f'<div class="alert-log">{rows}</div>',
        unsafe_allow_html=True)


# ─────────────────────────────────────────
#  LOOP PRINCIPAL
# ─────────────────────────────────────────
if st.session_state.running:
    if not api_key:
        st.error("⚠️ Insira sua API Key da The Odds API na barra lateral.")
        st.stop()

    games_raw, remaining = fetch_odds(sport, api_key)
    current = parse_odds(games_raw)

    st.session_state.last_check = datetime.now().strftime("%H:%M:%S")
    if remaining >= 0:
        st.session_state.req_left = remaining

    # Detecta alertas
    for gid, data in current.items():
        prev = st.session_state.previous.get(gid)
        if prev:
            for side, label in [("home", "Casa"), ("away", "Fora")]:
                diff = tick_diff(prev[side], data[side])
                if abs(diff) >= threshold:
                    alert = {
                        "time":  st.session_state.last_check,
                        "match": data["match"],
                        "label": label,
                        "old":   prev[side],
                        "new":   data[side],
                        "diff":  diff
                    }
                    st.session_state.alerts.append(alert)

                    # Telegram
                    dir_str = "📉 QUEDA" if diff < 0 else "📈 SUBIDA"
                    msg = (f"⚡ <b>ALERTA DE ODDS</b>\n\n"
                           f"🏟 <b>{data['match']}</b>\n"
                           f"📊 Back {label}\n"
                           f"Odd anterior: <b>{prev[side]}</b>\n"
                           f"Odd atual: <b>{data[side]}</b>\n"
                           f"{dir_str}: <b>{abs(diff)} ticks</b>\n"
                           f"🕐 {st.session_state.last_check}")
                    send_telegram(tg_token, tg_chat, msg)

    st.session_state.current  = current
    st.session_state.previous = current

    render_games(current, st.session_state.previous, threshold)
    render_alerts(st.session_state.alerts)

    time.sleep(interval)
    st.rerun()

else:
    render_games(st.session_state.current, {}, threshold)
    render_alerts(st.session_state.alerts)

    if not st.session_state.running and not st.session_state.current:
        games_placeholder.markdown(
            '<div style="color:#8b949e;padding:20px">Configure as credenciais e clique em ▶ Iniciar.</div>',
            unsafe_allow_html=True)
