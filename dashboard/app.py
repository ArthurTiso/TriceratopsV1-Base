import streamlit as st
import json
import os
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Spino — Ensaio de Ponte", layout="wide")

# ⏳ Tempo sem mudança de peso para acionar alerta visual (segundos)
ALERTA_CRONOMETRO_SEGUNDOS = 45
ZONA_ATENCAO_SEGUNDOS = 30  # a partir daqui a barra já sinaliza "atenção"

st_autorefresh(interval=1000, key="refresh")

STATUS_META = {
    "RUNNING":  {"label": "EM TESTE",   "css": "status-running"},
    "BROKEN":   {"label": "ROMPEU",     "css": "status-broken"},
    "INACTIVE": {"label": "INATIVO",    "css": "status-inactive"},
    "IDLE":     {"label": "AGUARDANDO", "css": "status-idle"},
    "SEM_DADOS": {"label": "AGUARDANDO DADOS DO MÓDULO 1", "css": "status-idle"},
}


def status_meta(status):
    return STATUS_META.get(status, {"label": status or "DESCONHECIDO", "css": "status-inactive"})


def formatar_mmss(segundos):
    if segundos is None:
        return "--:--"
    total = int(segundos)
    return f"{total // 60:02d}:{total % 60:02d}"


def carregar_dados():
    if not os.path.exists("data.json"):
        return None
    try:
        with open("data.json", "r") as f:
            return json.load(f)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────
# ESTILO — identidade visual "instrumento de ensaio estrutural"
# Usamos st.html() (não st.markdown) para injetar HTML/CSS: st.markdown
# passa tudo pelo parser de markdown, que trata linhas em branco dentro
# de um bloco HTML como fim de bloco — quebrando o parsing. st.html()
# renderiza o texto exatamente como está, sem essa armadilha.
# ────────────────────────────────────────────────────────────────
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
:root {
    --bg:        #12181C;
    --surface:   #1C242B;
    --surface-2: #232D35;
    --accent:    #F2C230;
    --steel:     #4C7A96;
    --danger:    #D94F4F;
    --text:      #E8ECEF;
    --text-dim:  #7C8894;
    --border:    #2C3740;
}
#MainMenu, header, footer { visibility: hidden; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp {
    background-color: var(--bg) !important;
}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 1200px;
}
* { font-family: 'IBM Plex Mono', monospace; }
.spino-topbar {
    display: flex;
    justify-content: flex-end;
    gap: 18px;
    color: var(--text-dim);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    font-weight: 500;
    margin-bottom: 14px;
    padding-right: 4px;
}
.spino-topbar span b { color: var(--text); font-weight: 600; }
.spino-topbar .divider { color: var(--border); }
.spino-band {
    text-align: center;
    padding: 10px 0;
    border-radius: 6px;
    font-family: 'Oswald', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    letter-spacing: 0.12em;
    margin-bottom: 22px;
}
.status-running  { background: var(--accent); color: #12181C; }
.status-broken   { background: var(--danger); color: #12181C; }
.status-inactive { background: var(--text-dim); color: #12181C; }
.status-idle     { background: var(--surface-2); color: var(--text-dim); border: 1px solid var(--border); }
.spino-hero {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 30px 20px 26px;
    text-align: center;
    margin-bottom: 20px;
    overflow: hidden;
}
.spino-hero .eyebrow {
    font-family: 'Oswald', sans-serif;
    font-size: 0.85rem;
    letter-spacing: 0.15em;
    color: var(--text-dim);
    font-weight: 600;
}
.spino-hero .valor {
    font-size: 5.2rem;
    font-weight: 700;
    line-height: 1.1;
    margin: 6px 0 2px;
}
.spino-hero .valor small { font-size: 1.8rem; font-weight: 500; opacity: 0.8; }
.spino-hero .registro { color: var(--text-dim); font-size: 1rem; letter-spacing: 0.04em; }
.crack-overlay { position: absolute; inset: 0; pointer-events: none; }
.spino-crono {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 22px;
}
.spino-crono .eyebrow {
    font-family: 'Oswald', sans-serif;
    font-size: 0.85rem;
    letter-spacing: 0.15em;
    color: var(--text-dim);
    font-weight: 600;
}
.spino-crono .tempo { font-size: 2.1rem; font-weight: 600; margin: 4px 0 10px; }
.crono-track { background: var(--surface-2); border-radius: 6px; height: 8px; overflow: hidden; }
.crono-fill  { height: 100%; border-radius: 6px; transition: width 0.4s ease; }
.spino-chart-label {
    font-family: 'Oswald', sans-serif;
    font-size: 0.85rem;
    letter-spacing: 0.15em;
    color: var(--text-dim);
    font-weight: 600;
    margin-bottom: 6px;
}
</style>
""")


data = carregar_dados()

if not data:
    data = {
        "bateria": 0, "peso_atual": 0, "peso_max": 0, "angulo": 0, "tempo": 0,
        "status": "SEM_DADOS", "historico": [], "segundos_desde_mudanca": None,
    }

status = data.get("status", "UNKNOWN")
meta = status_meta(status)

peso_atual = data.get("peso_atual", 0)
peso_max = data.get("peso_max", 0)
bateria = data.get("bateria", 0)
angulo = data.get("angulo", 0)
tempo = data.get("tempo", 0)
segundos_desde_mudanca = data.get("segundos_desde_mudanca")

# ---- barra superior ----
st.html(
    '<div class="spino-topbar">'
    f'<span>BATERIA <b>{bateria}%</b></span>'
    '<span class="divider">│</span>'
    f'<span>ÂNGULO <b>{angulo}°</b></span>'
    '<span class="divider">│</span>'
    f'<span>DURAÇÃO <b>{tempo}s</b></span>'
    '</div>'
)

# ---- faixa de status ----
st.html(f'<div class="spino-band {meta["css"]}">{meta["label"]}</div>')

# ---- cronômetro ----
if segundos_desde_mudanca is None:
    pct = 0
    cor_barra = "var(--steel)"
elif segundos_desde_mudanca >= ALERTA_CRONOMETRO_SEGUNDOS:
    pct = 100
    cor_barra = "var(--danger)"
elif segundos_desde_mudanca >= ZONA_ATENCAO_SEGUNDOS:
    pct = (segundos_desde_mudanca / ALERTA_CRONOMETRO_SEGUNDOS) * 100
    cor_barra = "var(--accent)"
else:
    pct = (segundos_desde_mudanca / ALERTA_CRONOMETRO_SEGUNDOS) * 100
    cor_barra = "var(--steel)"

st.html(
    '<div class="spino-crono">'
    '<div class="eyebrow">DESDE ÚLTIMA MUDANÇA DE PESO</div>'
    f'<div class="tempo">{formatar_mmss(segundos_desde_mudanca)}</div>'
    '<div class="crono-track">'
    f'<div class="crono-fill" style="width:{pct:.0f}%; background:{cor_barra};"></div>'
    '</div>'
    '</div>'
)

# ---- cartão de peso (hero) + trinca se rompeu ----
crack_svg = ""
if status == "BROKEN":
    crack_svg = (
        '<svg class="crack-overlay" viewBox="0 0 400 160" preserveAspectRatio="none">'
        '<polyline points="0,55 60,50 95,80 140,60 170,95 210,58 245,88 285,52 320,72 400,50" '
        'fill="none" stroke="#D94F4F" stroke-width="2.5" opacity="0.75" '
        'style="filter: drop-shadow(0 0 3px #D94F4F);" />'
        '</svg>'
    )

st.html(
    f'<div class="spino-hero">{crack_svg}'
    '<div class="eyebrow">PESO ATUAL</div>'
    f'<div class="valor">{peso_atual}<small> kg</small></div>'
    f'<div class="registro">REGISTRO MÁXIMO — {peso_max} kg</div>'
    '</div>'
)

# ---- gráfico peso × tempo ----
historico = data.get("historico", [])

st.html('<div class="spino-chart-label">PESO × TEMPO (kg / s)</div>')

if historico:
    tempos = [p[0] for p in historico]
    pesos = [p[1] for p in historico]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tempos, y=pesos,
        mode="lines+markers",
        line=dict(color="#4C7A96", width=2.5),
        marker=dict(color="#F2C230", size=5),
        hovertemplate="t=%{x}s · %{y}kg<extra></extra>",
    ))
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#1C242B",
        plot_bgcolor="#1C242B",
        font=dict(color="#E8ECEF", family="IBM Plex Mono", size=13),
        xaxis=dict(title="tempo (s)", gridcolor="#2C3740", zeroline=False),
        yaxis=dict(title="peso (kg)", gridcolor="#2C3740", zeroline=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.html('<div style="color: #7C8894; text-align:center; padding: 30px 0;">ainda não há dados suficientes para o gráfico</div>')