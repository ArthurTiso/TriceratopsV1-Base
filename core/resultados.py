"""Registro local de todos os resultados de ensaio (resultados.csv).

Serve de backup oficial e de base para lançar resultados manualmente no
Módulo 3 (Rupturas) quando o envio automático não for confirmado. Formato
pensado para abrir direto no Excel em português (separador ";", decimal ",").
"""

import csv
from datetime import datetime
from pathlib import Path

CAMPOS = (
    "data_hora",
    "equipe_codigo",
    "equipe_nome",
    "carga_ruptura_kg",
    "duracao_s",
    "motivo",
    "modo",
    "registro_modulo3",
    "run_id",
)

# Situação do registro no Módulo 3
ENVIANDO = "enviando"
CONFIRMADO = "confirmado"
LOCAL = "modo local (não enviado)"


def _decimal(valor):
    return f"{valor:.1f}".replace(".", ",")


class RegistroResultados:
    def __init__(self, caminho):
        self.caminho = Path(caminho) if caminho else None

    def gravar(self, resultado: dict):
        if self.caminho is None:
            return
        novo = not self.caminho.exists()
        linha = {
            "data_hora": resultado["data_hora"],
            "equipe_codigo": resultado["equipe_codigo"],
            "equipe_nome": resultado["equipe_nome"],
            "carga_ruptura_kg": _decimal(resultado["carga_kg"]),
            "duracao_s": _decimal(resultado["duracao_s"]),
            "motivo": resultado["motivo"],
            "modo": resultado["modo"],
            "registro_modulo3": resultado["registro"],
            "run_id": resultado.get("run_id") or "",
        }
        try:
            with open(self.caminho, "a", encoding="utf-8-sig" if novo else "utf-8", newline="") as f:
                escritor = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
                if novo:
                    escritor.writeheader()
                escritor.writerow(linha)
        except OSError as e:  # arquivo aberto no Excel etc.
            print(f"⚠️  Não foi possível gravar {self.caminho}: {e}")


def novo_resultado(equipe_codigo, equipe_nome, carga_kg, duracao_s, motivo, modo, run_id, registro):
    return {
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "equipe_codigo": equipe_codigo,
        "equipe_nome": equipe_nome,
        "carga_kg": carga_kg,
        "duracao_s": duracao_s,
        "motivo": motivo,
        "modo": modo,
        "run_id": run_id,
        "registro": registro,
    }
