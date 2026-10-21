"""
Servidor mock do Módulo 3 — testa o envio HTTP do Módulo 2 sem depender do
backend Laravel. Reproduz as regras de SensorCaptureController (spino-web):

* token Bearer obrigatório e igual a SPINO_MODULO3_TOKEN;
* equipe precisa existir e estar aprovada (MOCK001..MOCK004, como nos seeds);
* validação de team_code, event, elapsed_ms, load_grams e timestamp;
* "completed" registra como carga de ruptura o maior load_grams da equipe;
* qualquer amostra depois do "completed" volta a equipe para "running".

Rodar em outro terminal, a partir da raiz do projeto:
    python -m sender.mock_modulo3_server
"""

import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import carregar_env

ROTA = "/api/v1/sensors/capture"
EQUIPES_APROVADAS = ("MOCK001", "MOCK002", "MOCK003", "MOCK004")


class BancoMock:
    """Equivalente simplificado das tabelas teams e bridge_load_samples."""

    def __init__(self, equipes=EQUIPES_APROVADAS):
        self.lock = threading.Lock()
        self.equipes = {
            codigo: {"test_status": "pending", "actual_load_grams": None}
            for codigo in equipes
        }
        self.amostras = {codigo: [] for codigo in equipes}
        self.eventos = []  # (team_code, event, elapsed_ms, load_grams)


def _validar(dados):
    erros = []
    if not isinstance(dados, dict):
        return ["corpo deve ser um objeto JSON"]
    team_code = dados.get("team_code")
    if not isinstance(team_code, str) or not team_code or len(team_code) > 12:
        erros.append("team_code")
    if dados.get("event") not in (None, "sample", "started", "completed"):
        erros.append("event")
    for campo, maximo in (("elapsed_ms", 86400000), ("load_grams", 1000000)):
        valor = dados.get(campo)
        if not isinstance(valor, int) or isinstance(valor, bool) or not 0 <= valor <= maximo:
            erros.append(campo)
    if dados.get("timestamp") is not None:
        try:
            datetime.fromisoformat(str(dados["timestamp"]))
        except ValueError:
            erros.append("timestamp")
    return erros


def criar_handler(banco, token, verbose=True):
    class MockHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != ROTA:
                return self._responder(404, {"message": "Rota não encontrada."})

            enviado = self.headers.get("Authorization", "")
            if not token or enviado != f"Bearer {token}":
                return self._responder(401, {"message": "Não autorizado."})

            tamanho = int(self.headers.get("Content-Length", 0))
            try:
                dados = json.loads(self.rfile.read(tamanho))
            except json.JSONDecodeError:
                return self._responder(422, {"message": "JSON inválido."})

            erros = _validar(dados)
            if erros:
                return self._responder(422, {"message": "Dados inválidos.", "errors": erros})

            codigo = dados["team_code"]
            evento = dados.get("event") or "sample"
            with banco.lock:
                equipe = banco.equipes.get(codigo)
                if equipe is None:
                    return self._responder(404, {"message": "Equipe não encontrada."})

                banco.amostras[codigo].append((dados["elapsed_ms"], dados["load_grams"]))
                banco.eventos.append((codigo, evento, dados["elapsed_ms"], dados["load_grams"]))
                if evento == "completed":
                    equipe["test_status"] = "completed"
                    equipe["actual_load_grams"] = max(g for _, g in banco.amostras[codigo])
                else:
                    equipe["test_status"] = "running"

            if verbose:
                linha = f"[MOCK MÓDULO 3] {codigo} {evento:9s} t={dados['elapsed_ms'] / 1000:6.1f}s carga={dados['load_grams'] / 1000:7.2f} kg"
                if evento == "completed":
                    linha += f"  → RUPTURA REGISTRADA: {equipe['actual_load_grams'] / 1000:.2f} kg"
                print(linha, flush=True)

            self._responder(202, {"accepted": True, "team_code": codigo, "event": evento})

        def _responder(self, status, corpo):
            if verbose and status >= 400:
                print(f"[MOCK MÓDULO 3] recusado {status}: {corpo['message']}", flush=True)
            dados = json.dumps(corpo).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, format, *args):
            pass  # silencia o log padrão de acesso HTTP (já imprimimos o que importa)

    return MockHandler


def criar_servidor(porta, token, banco=None, verbose=True):
    banco = banco or BancoMock()
    servidor = ThreadingHTTPServer(("0.0.0.0", porta), criar_handler(banco, token, verbose))
    return servidor, banco


if __name__ == "__main__":
    carregar_env()
    porta = int(os.getenv("SPINO_MOCK_PORT", "8000"))
    token = os.getenv("SPINO_MODULO3_TOKEN")
    if not token:
        raise SystemExit("Defina SPINO_MODULO3_TOKEN (no .env) — o mock exige o mesmo token do Módulo 2")

    servidor, _ = criar_servidor(porta, token)
    print(f"🧪 Mock do Módulo 3 escutando em http://localhost:{porta}{ROTA}")
    print(f"   Equipes aprovadas: {', '.join(EQUIPES_APROVADAS)}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando mock do Módulo 3...")
