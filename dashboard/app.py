"""Painel do Módulo 2 — streamlit run dashboard/app.py

Lê o estado gravado pelo Módulo 2 (data.json) a cada segundo e envia os
comandos do "Controle manual" para ele (pasta comandos/).
"""

import html
import importlib.util
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent


def _carregar_comandos():
    # Carregado pelo caminho: este arquivo também se chama app.py, e um
    # "import app.comandos" acharia o próprio painel em vez do pacote app/.
    spec = importlib.util.spec_from_file_location("spino_comandos", RAIZ / "app" / "comandos.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


enviar_comando = _carregar_comandos().enviar_comando

ARQUIVO_ESTADO = RAIZ / "data.json"
PASTA_COMANDOS = RAIZ / "comandos"

st.set_page_config(page_title="Spino — Módulo 2", layout="wide")

CORES = {
    "bg": "#0F1418", "surface": "#182128", "surface2": "#212C35", "border": "#2C3740",
    "text": "#EEF2F4", "dim": "#8592A0", "accent": "#F2C230", "steel": "#4C9AC8",
    "ok": "#3BB273", "danger": "#C25058", "warn": "#F2A030",
}

# Tons da tela na ruptura. A tela inteira (fundo, cartões e faixa) muda para
# o tema escolhido em TEMA_RUPTURA enquanto o status for BROKEN.
TEMAS_RUPTURA = {
    "A": {"bg": CORES["bg"], "surface": CORES["surface"], "border": CORES["border"],
          "faixa": "#7A2E33", "faixa_texto": "#F6DADC", "destaque": "#8A3A40"},
    "B": {"bg": CORES["bg"], "surface": CORES["surface"], "border": CORES["border"],
          "faixa": "#9E2A33", "faixa_texto": "#FCE4E6", "destaque": "#B23A44"},
    "C": {"bg": "#170F12", "surface": "#21161A", "border": "#3A2328",
          "faixa": "#9E2A33", "faixa_texto": "#FCE4E6", "destaque": "#B23A44"},
    "D": {"bg": "#210F13", "surface": "#2D151A", "border": "#4A2228",
          "faixa": "#B02E38", "faixa_texto": "#FFFFFF", "destaque": "#C9434D"},
    "E": {"bg": "#2C0E13", "surface": "#3A141A", "border": "#5C232B",
          "faixa": "#C23440", "faixa_texto": "#FFFFFF", "destaque": "#DA505B"},
}
TEMA_RUPTURA = "C"

# Faixa de status: (texto, classe CSS)
STATUS = {
    "RUNNING": ("● EM ENSAIO", "f-ensaio"),
    "RUPTURA_DETECTADA": ("RUPTURA DETECTADA · {carga} kg — CONFIRME", "f-detectada"),
    "TARANDO": ("TARANDO — NÃO TOQUE NA PONTE", "f-tarando"),
    "BROKEN": ("RUPTURA · {carga} kg", "f-ruptura"),
    "FINALIZADO": ("ENSAIO ENCERRADO · {carga} kg", "f-ruptura"),
    "INACTIVE": ("SEM DADOS DA BALANÇA", "f-alerta"),
    "ERRO_SENSOR": ("ERRO NO SENSOR DA BALANÇA", "f-alerta"),
    "IDLE": ("AGUARDANDO ENSAIO", "f-idle"),
    "SEM_DADOS": ("MÓDULO 2 DESLIGADO", "f-idle"),
}

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
#MainMenu, header, footer {{ visibility: hidden; }}
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp {{ background-color: {CORES['bg']} !important; }}
.block-container {{ padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 1400px; }}
* {{ font-family: 'IBM Plex Mono', monospace; }}
.topo {{ display:flex; align-items:center; justify-content:space-between; color:{CORES['dim']}; margin-bottom:12px; }}
.marca {{ font-family:'Oswald',sans-serif; font-size:1.7rem; letter-spacing:.2em; font-weight:700; color:{CORES['text']}; }}
.marca small {{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; color:{CORES['dim']}; letter-spacing:.1em; margin-left:10px; }}
.info {{ display:flex; gap:26px; font-size:.95rem; align-items:center; }}
.info b {{ color:{CORES['text']}; font-size:1.1rem; }}
.led {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
.led.on {{ background:{CORES['ok']}; box-shadow:0 0 8px {CORES['ok']}; }}
.led.off {{ background:{CORES['danger']}; box-shadow:0 0 8px {CORES['danger']}; }}
.led.na {{ background:{CORES['border']}; }}
.faixa {{ text-align:center; padding:12px; border-radius:8px; font-family:'Oswald',sans-serif; font-weight:700;
          font-size:1.8rem; letter-spacing:.14em; margin-bottom:6px; }}
.f-ensaio {{ background:{CORES['accent']}; color:#111; }}
.f-tarando {{ background:{CORES['accent']}; color:#111; animation:pisca 1.2s infinite; }}
.f-ruptura {{ background:#7A2E33; color:#F6DADC; }}
.f-detectada {{ background:#7A2E33; color:#F6DADC; animation:pisca 1.2s infinite; }}
.f-alerta {{ background:#5C3A12; color:#F8D29A; border:1px solid #B87A20; }}
.f-idle {{ background:{CORES['surface2']}; color:{CORES['dim']}; border:1px solid {CORES['border']}; }}
.f-pronto {{ background:#3A3113; color:#F2D27A; border:1px solid #8C7424; }}
@keyframes pisca {{ 50% {{ opacity:.55; }} }}
.mensagem {{ text-align:center; color:{CORES['dim']}; margin-bottom:12px; font-size:.95rem; min-height:1.2em; }}
.card {{ background:{CORES['surface']}; border:1px solid {CORES['border']}; border-radius:12px; padding:14px 18px; }}
.rotulo {{ font-size:.8rem; letter-spacing:.18em; color:{CORES['dim']}; font-weight:600; }}
.maxima {{ text-align:center; min-height:300px; display:flex; flex-direction:column; justify-content:center;
           align-items:center; margin-top:30px; margin-bottom:12px; }}
.maxima.ruptura {{ border-color:#8A3A40; }}
.maxima.ruptura .rotulo {{ color:#E79A9F; }}
.maxima .valor {{ font-size:clamp(3.5rem, 6.5vw, 7rem); font-weight:700; line-height:1; margin:14px 0 8px;
                  color:{CORES['text']}; white-space:nowrap; }}
.maxima .valor small {{ font-size:.32em; opacity:.8; }}
.selo {{ display:inline-block; margin:6px 0 4px; padding:6px 14px; border-radius:20px; font-weight:700; font-size:.95rem; }}
.selo.ok {{ background:rgba(59,178,115,.15); color:#7fe3a9; border:1px solid {CORES['ok']}; }}
.selo.pend {{ background:rgba(76,154,200,.15); color:#9fd0ee; border:1px solid {CORES['steel']}; }}
.selo.aviso {{ background:rgba(242,160,48,.12); color:#F2B860; border:1px solid #B87A20; }}
.eventos {{ font-size:.85rem; line-height:1.65; color:{CORES['dim']}; margin-top:6px; }}
.eventos .ev-ok {{ color:#7fe3a9; }} .eventos .ev-aviso {{ color:#F2B860; }} .eventos .ev-erro {{ color:#FF8B8B; }}
.eventos .ev-ruptura {{ color:#E79A9F; font-weight:700; }} .eventos .ev-info {{ color:{CORES['text']}; }}
.alerta {{ background:rgba(242,160,48,.12); border:1px solid #B87A20; color:#F2B860; border-radius:8px;
           padding:10px 12px; font-size:.88rem; margin-bottom:10px; }}
.pronto {{ background:rgba(76,154,200,.10); border:1px solid {CORES['steel']}; color:#9fd0ee; border-radius:8px;
           padding:10px 12px; font-size:.88rem; margin-bottom:10px; }}
div[data-testid="stExpander"] details {{ background:{CORES['surface']}; border:1px solid {CORES['border']}; border-radius:12px; }}
.st-key-confirmar_ruptura button, .st-key-ruptura_sim button {{ background:#B23A44 !important; border-color:#DA505B !important;
          color:#FFFFFF !important; font-size:1.25rem !important; padding:14px 0 !important; }}
.st-key-confirmar_ruptura button:hover, .st-key-ruptura_sim button:hover {{ background:#C9434D !important; }}
div[data-testid="stExpander"] summary p {{ letter-spacing:.15em; font-weight:600; color:{CORES['dim']}; }}
.stButton button, div[data-testid="stButton"] button {{ width:100%; font-weight:700; letter-spacing:.04em; }}
</style>
""")


def carregar_estado():
    try:
        return json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def mmss(segundos):
    if segundos is None:
        return "--:--"
    total = int(segundos)
    return f"{total // 60:02d}:{total % 60:02d}"


def kg(valor):
    return f"{valor:.1f}".replace(".", ",")


def led(valor):
    return "on" if valor else ("na" if valor is None else "off")


def comando(texto, aviso):
    enviar_comando(texto, PASTA_COMANDOS)
    st.toast(aviso)


def topo(dados):
    equipe = dados.get("equipe_nome") or dados.get("equipe") or "—"
    codigo = dados.get("equipe")
    sufixo = f" ({html.escape(codigo)})" if codigo and codigo != equipe else ""
    mostra_tempo = dados.get("em_ensaio") or dados.get("status") in ("BROKEN", "FINALIZADO")
    st.html(
        '<div class="topo">'
        f'<div class="marca">SPINO<small>MÓDULO 2 · {html.escape(dados.get("device_code") or "")}</small></div>'
        '<div class="info">'
        f'<span>EQUIPE <b>{html.escape(equipe)}</b>{sufixo}</span>'
        f'<span>DURAÇÃO <b>{mmss(dados.get("tempo") if mostra_tempo else None)}</b></span>'
        f'<span><i class="led {led(dados.get("balanca_online"))}"></i>BALANÇA</span>'
        f'<span><i class="led {led(dados.get("m3_online"))}"></i>MÓDULO 3</span>'
        '</div></div>'
    )


def faixa(dados):
    status = dados.get("status", "SEM_DADOS")
    texto, classe = STATUS.get(status, (status, "f-idle"))
    armado = dados.get("armado")
    if status == "IDLE" and armado:
        texto, classe = f"PRONTO · {armado['equipe_nome']}", "f-pronto"
    texto = texto.format(carga=kg(dados.get("peso_max", 0)))
    st.html(f'<div class="faixa {classe}">{html.escape(texto)}</div>')
    st.html(f'<div class="mensagem">{html.escape(dados.get("mensagem") or "")}</div>')


def tema(dados):
    """Cores de fundo, cartões e bordas: as normais ou as do tema de ruptura."""
    if dados.get("status") == "BROKEN":
        return TEMAS_RUPTURA[TEMA_RUPTURA]
    return {"bg": CORES["bg"], "surface": CORES["surface"], "border": CORES["border"]}


def css_ruptura():
    t = TEMAS_RUPTURA[TEMA_RUPTURA]
    st.html(f"""<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp {{ background-color:{t['bg']} !important; }}
.card {{ background:{t['surface']}; border-color:{t['border']}; }}
.maxima.ruptura {{ border-color:{t['destaque']}; }}
.f-ruptura {{ background:{t['faixa']}; color:{t['faixa_texto']}; }}
div[data-testid="stExpander"] details {{ background:{t['surface']}; border-color:{t['border']}; }}
</style>""")


def grafico(dados):
    cores = tema(dados)
    historico = dados.get("historico", [])
    tempos = [p[0] for p in historico]
    picos = [p[2] if len(p) > 2 else p[1] for p in historico]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tempos, y=picos, mode="lines", line=dict(color=CORES["steel"], width=4, shape="hv"),
        fill="tozeroy", fillcolor="rgba(76,154,200,.13)",
        hovertemplate="t=%{x:.1f}s · %{y:.1f} kg<extra></extra>",
    ))
    if picos:
        fig.add_trace(go.Scatter(x=[tempos[-1]], y=[picos[-1]], mode="markers",
                                 marker=dict(color=CORES["accent"], size=11), hoverinfo="skip"))
    ruptura = dados.get("tempo_ruptura")
    if ruptura is not None and dados.get("status") == "BROKEN":
        fig.add_vline(x=ruptura, line=dict(color=CORES["danger"], width=1.5, dash="dash"),
                      annotation_text=f"ruptura · {mmss(ruptura)}", annotation_position="top right",
                      annotation_font=dict(color="#E79A9F", size=14))
    if not historico:
        fig.add_annotation(text="aguardando leituras da balança", showarrow=False, xref="paper",
                           yref="paper", x=0.5, y=0.5, font=dict(color=CORES["dim"], size=15))
    fig.update_layout(
        height=430, margin=dict(l=10, r=20, t=30, b=10), showlegend=False,
        paper_bgcolor=cores["surface"], plot_bgcolor=cores["surface"],
        font=dict(color=CORES["text"], family="IBM Plex Mono", size=13),
        xaxis=dict(title="tempo (s)", gridcolor=cores["border"], zeroline=False, rangemode="tozero"),
        yaxis=dict(title="carga máxima (kg)", gridcolor=cores["border"], zeroline=False, rangemode="tozero"),
    )
    st.html('<div class="rotulo" style="margin:4px 0 6px">CARGA MÁXIMA × TEMPO</div>')
    st.plotly_chart(fig, config={"displayModeBar": False})


def selo(dados):
    resultado = dados.get("resultado")
    if dados.get("status") not in ("BROKEN", "FINALIZADO") or not resultado:
        return ""
    registro = resultado["registro"]
    if registro == "confirmado":
        return '<div class="selo ok">✓ registrado no Módulo 3</div>'
    if registro == "enviando":
        return '<div class="selo pend">⏳ enviando ao Módulo 3…</div>'
    if resultado.get("modo") == "local":
        return '<div class="selo aviso">💾 modo local — salvo em resultados.csv</div>'
    return (f'<div class="selo aviso">⚠ não registrado no Módulo 3 — lance '
            f'{kg(resultado["carga_kg"])} kg em Rupturas</div>')


def carga_maxima(dados):
    terminou = dados.get("status") in ("BROKEN", "FINALIZADO")
    rotulo = "CARGA DE RUPTURA" if dados.get("status") == "BROKEN" else "CARGA MÁXIMA"
    st.html(
        f'<div class="card maxima {"ruptura" if terminou else ""}">'
        f'<div class="rotulo">{rotulo}</div>'
        f'<div class="valor">{kg(dados.get("peso_max", 0))}<small> kg</small></div>'
        f'{selo(dados)}</div>'
    )


def eventos(dados):
    itens = dados.get("eventos") or []
    linhas = "".join(
        f'{e["hora"]} <span class="ev-{e["tipo"]}">{html.escape(e["texto"])}</span><br>'
        for e in reversed(itens)
    ) or "nenhum evento ainda"
    st.html(f'<div class="card"><div class="rotulo">EVENTOS</div><div class="eventos">{linhas}</div></div>')


def confirmar_ruptura(dados):
    """Único caminho que encerra o ensaio no Módulo 3: o operador confirma a ruptura."""
    if not dados.get("em_ensaio"):
        st.session_state.pedir_confirmacao_ruptura = False
        return
    detectada = bool(dados.get("ruptura_detectada"))
    carga = kg(dados.get("peso_max", 0))
    destino = "em resultados.csv" if dados.get("modo") == "local" else "no Módulo 3"

    if detectada:
        # Queda de carga já detectada: um clique basta.
        st.html(f'<div class="alerta">A carga caiu. Confira a ponte e confirme: <b>{carga} kg</b> '
                f'serão registrados {destino} e o ensaio será encerrado.</div>')
        if st.button("💥 CONFIRMAR RUPTURA", key="confirmar_ruptura", width="stretch"):
            comando("fim", f"Ruptura confirmada: {carga} kg")
        return

    # Sem queda detectada: pede uma segunda confirmação para evitar encerrar por engano.
    if not st.session_state.get("pedir_confirmacao_ruptura", False):
        if st.button("💥 CONFIRMAR RUPTURA", key="confirmar_ruptura", width="stretch"):
            st.session_state.pedir_confirmacao_ruptura = True
            st.rerun(scope="fragment")
        return
    st.html(f'<div class="alerta">A queda de carga ainda não foi detectada. Confirmar registra '
            f'<b>{carga} kg</b> {destino} e encerra o ensaio.</div>')
    sim, nao = st.columns(2)
    if sim.button("Confirmar", key="ruptura_sim", width="stretch"):
        comando("fim", f"Ruptura confirmada: {carga} kg")
        st.session_state.pedir_confirmacao_ruptura = False
    if nao.button("Voltar", key="ruptura_nao", width="stretch"):
        st.session_state.pedir_confirmacao_ruptura = False
        st.rerun(scope="fragment")


def controle_manual(dados):
    m3_online = dados.get("m3_online")
    em_ensaio = bool(dados.get("em_ensaio"))
    tarando = dados.get("status") == "TARANDO"
    armado = dados.get("armado") if m3_online else None
    local = dados.get("modo") == "local"
    aberto = m3_online is False or local

    with st.expander("CONTROLE MANUAL (M2)", expanded=aberto):
        if m3_online is False:
            st.html('<div class="alerta">Módulo 3 sem resposta — modo local: o resultado fica em '
                    'resultados.csv para lançar depois em Rupturas.</div>')
        if armado:
            st.html(f'<div class="pronto">Ensaio armado no Módulo 3: <b>{html.escape(armado["equipe_nome"])}</b>. '
                    'Monte a ponte sem carga e inicie.</div>')
            equipe = None
        else:
            equipe = st.text_input("Equipe (modo local)", key="equipe_local", placeholder="ex.: EQUIPE 07")

        if st.button("▶ INICIAR ENSAIO", type="primary", disabled=em_ensaio or tarando, key="iniciar"):
            if armado:
                comando("novo", f"Iniciando o ensaio de {armado['equipe_nome']}")
            elif equipe and equipe.strip():
                comando(f"novo {equipe.strip()}", f"Iniciando em modo local: {equipe.strip()}")
            else:
                st.toast("Informe a equipe para iniciar em modo local.")

        confirmar = st.session_state.get("confirmar_cancelamento", False)
        if not confirmar:
            if st.button("✕ CANCELAR ENSAIO", disabled=not (em_ensaio or tarando), key="cancelar"):
                st.session_state.confirmar_cancelamento = True
                st.rerun(scope="fragment")
        else:
            st.html('<div class="alerta">Cancelar descarta o ensaio sem registrar resultado.</div>')
            sim, nao = st.columns(2)
            if sim.button("Confirmar", key="cancelar_sim"):
                comando("cancelar", "Ensaio cancelado")
                st.session_state.confirmar_cancelamento = False
            if nao.button("Voltar", key="cancelar_nao"):
                st.session_state.confirmar_cancelamento = False
                st.rerun(scope="fragment")

        if st.button("⚖ TARAR", disabled=em_ensaio or tarando, key="tarar"):
            comando("tara", "Tarando — mantenha a balança sem carga")


@st.fragment(run_every=1)
def painel():
    dados = carregar_estado() or {
        "status": "SEM_DADOS", "peso_max": 0, "historico": [], "m3_online": None, "balanca_online": None,
        "mensagem": "Inicie o Módulo 2: python -m app.main",
    }
    if dados.get("status") == "BROKEN":
        css_ruptura()
    topo(dados)
    faixa(dados)
    esquerda, direita = st.columns([1, 2.3], gap="medium")
    with esquerda:
        carga_maxima(dados)
        confirmar_ruptura(dados)
    with direita:
        grafico(dados)
        # Eventos e controle manual ficam logo abaixo do gráfico, na mesma largura.
        col_eventos, col_controle = st.columns(2, gap="medium")
        with col_eventos:
            eventos(dados)
        with col_controle:
            if dados.get("status") != "SEM_DADOS":
                controle_manual(dados)


painel()
