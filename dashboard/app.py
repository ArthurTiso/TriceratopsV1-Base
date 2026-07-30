import streamlit as st
import json
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import os

st.set_page_config(layout="wide")

st.title("🏗️ Monitoramento de Ponte")

# 🔄 AUTO REFRESH CONTROLADO
st_autorefresh(interval=1000, key="refresh")


def get_status_color(status):
    if status == "RUNNING":
        return "green"
    elif status == "BROKEN":
        return "red"
    elif status == "INACTIVE":
        return "orange"
    return "gray"


# 📦 FUNÇÃO SEGURA DE LEITURA
def carregar_dados():
    if not os.path.exists("data.json"):
        return None

    try:
        with open("data.json", "r") as f:
            return json.load(f)
    except:
        return None


data = carregar_dados()

# 🚫 SEM DADOS
if not data:
    st.warning("⏳ Aguardando dados do sistema...")
    st.stop()

status = data.get("status", "UNKNOWN")
cor = get_status_color(status)

# 🔝 MÉTRICAS
col1, col2, col3, col4 = st.columns(4)

col1.metric("🔋 Bateria", data.get("bateria", 0))
col2.metric("⏱ Tempo", data.get("tempo", 0))
col3.metric("📐 Ângulo", data.get("angulo", 0))
col4.metric("📊 Status", status)

st.markdown("---")

# 🎯 PESO CENTRAL
st.markdown(
    f"""
    <h1 style='text-align: center; color: {cor}; font-size: 80px;'>
        {data.get("peso_atual", 0)} kg
    </h1>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"<h3 style='text-align: center;'>Peso Máximo: {data.get('peso_max', 0)} kg</h3>",
    unsafe_allow_html=True
)

# 🚨 ALERTAS
if status == "BROKEN":
    st.error("🚨 A PONTE QUEBROU!")

if status == "INACTIVE":
    st.warning("⚠️ Sistema sem atualização recente")

st.markdown("---")

# 📈 GRÁFICO
historico = data.get("historico", [])

if historico:
    tempos = [p[0] for p in historico]
    pesos = [p[1] for p in historico]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=tempos,
        y=pesos,
        mode='lines+markers',
        name="Peso"
    ))

    fig.update_layout(
        title="Evolução do Peso",
        xaxis_title="Tempo (s)",
        yaxis_title="Peso (kg)",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("📭 Ainda não há dados suficientes para o gráfico.")