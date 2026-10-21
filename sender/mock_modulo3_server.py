"""
Servidor mock do Módulo 3 — testa o Módulo 2 sem o backend Laravel. Reproduz as
regras de ActiveTestRunController e SensorCaptureController (spino-web):

* sem token, como o Módulo 3 atual; se SPINO_MODULO3_TOKEN estiver definido,
  o mock passa a exigi-lo (para testar o envio com token);
* GET  /api/v1/sensors/devices/{M2}/active-run — ensaio armado para o M2;
* POST /api/v1/sensors/capture — leitura vinculada a test_run_id, device_code
  e sequence (sequência repetida com os mesmos dados = duplicata aceita);
* "completed" encerra o ensaio com o maior load_grams dele;
* ensaios cancelados ou encerrados não aceitam leituras (422).

Para simular a comissão (Administração → Ensaios), abra no navegador:
    http://127.0.0.1:8000/mock/armar/MOCK002     arma um ensaio para o M2
    http://127.0.0.1:8000/mock/cancelar          cancela o ensaio ativo

Rodar a partir da raiz do projeto:
    python -m sender.mock_modulo3_server
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import carregar_env

ROTA_CAPTURA = "/api/v1/sensors/capture"
ROTA_ENSAIO_ATIVO = re.compile(r"^/api/v1/sensors/devices/([^/]+)/active-run$")
EQUIPES = {
    "MOCK001": "Palitos Mágicos",
    "MOCK002": "Palitos Atômicos",
    "MOCK003": "Palitos Alvinegros",
    "MOCK004": "Viga Mestra",
}


class BancoMock:
    """Equivalente simplificado das tabelas teams, test_devices, test_runs e samples."""

    def __init__(self):
        self.lock = threading.Lock()
        self.equipes = {
            codigo: {"name": nome, "test_status": "pending", "actual_load_grams": None}
            for codigo, nome in EQUIPES.items()
        }
        self.dispositivos = set()
        self.ensaios = {}  # uuid -> {"equipe", "device", "status", "amostras": {seq: (ms, g)}}
        self.eventos = []  # (team_code, event, elapsed_ms, load_grams, run_id)

    def armar(self, equipe, device):
        with self.lock:
            device = device.upper()
            if equipe not in self.equipes:
                raise ValueError(f"Equipe {equipe} não existe")
            for ensaio in self.ensaios.values():
                if ensaio["status"] in ("armed", "running") and (
                    ensaio["equipe"] == equipe or ensaio["device"] == device
                ):
                    raise ValueError("Já existe um ensaio ativo para esta equipe ou este M2")
            self.dispositivos.add(device)
            run_id = str(uuid.uuid4())
            self.ensaios[run_id] = {"equipe": equipe, "device": device, "status": "armed", "amostras": {}}
            return run_id

    def cancelar_ativos(self):
        with self.lock:
            for ensaio in self.ensaios.values():
                if ensaio["status"] in ("armed", "running"):
                    ensaio["status"] = "cancelled"

    def ensaio_ativo(self, device):
        for run_id, ensaio in reversed(list(self.ensaios.items())):
            if ensaio["device"] == device and ensaio["status"] in ("armed", "running"):
                return run_id, ensaio
        return None, None


def _validar(dados):
    erros = []
    if not isinstance(dados, dict):
        return ["corpo deve ser um objeto JSON"]
    try:
        uuid.UUID(str(dados.get("test_run_id")))
    except ValueError:
        erros.append("test_run_id")
    device = dados.get("device_code")
    if not isinstance(device, str) or not device or len(device) > 32:
        erros.append("device_code")
    sequencia = dados.get("sequence")
    if not isinstance(sequencia, int) or isinstance(sequencia, bool) or sequencia < 1:
        erros.append("sequence")
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


def criar_handler(banco, token, device_padrao="M2-01", verbose=True):
    def log(texto):
        if verbose:
            print(texto, flush=True)

    class MockHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/mock/armar/"):
                equipe = self.path.rsplit("/", 1)[-1].upper()
                try:
                    run_id = banco.armar(equipe, device_padrao)
                except ValueError as e:
                    return self._responder(422, {"message": str(e)})
                log(f"[MOCK MÓDULO 3] ensaio armado: {equipe} no {device_padrao} ({run_id})")
                return self._responder(200, {"armed": True, "team": equipe, "run_id": run_id})
            if self.path == "/mock/cancelar":
                banco.cancelar_ativos()
                log("[MOCK MÓDULO 3] ensaios ativos cancelados")
                return self._responder(200, {"cancelled": True})

            encontrado = ROTA_ENSAIO_ATIVO.match(self.path)
            if not encontrado:
                return self._responder(404, {"message": "Rota não encontrada."})
            if not self._autorizado():
                return self._responder(401, {"message": "Não autorizado."})

            device = encontrado.group(1).upper()
            with banco.lock:
                if device not in banco.dispositivos:
                    return self._responder(404, {"message": "Dispositivo não cadastrado para o evento."})
                run_id, ensaio = banco.ensaio_ativo(device)
                if ensaio is None:
                    return self._responder(200, {"active": False})
                equipe = ensaio["equipe"]
                corpo = {
                    "active": True,
                    "run_id": run_id,
                    "status": ensaio["status"],
                    "team": {"code": equipe, "name": banco.equipes[equipe]["name"]},
                }
            self._responder(200, corpo)

        def do_POST(self):
            if self.path != ROTA_CAPTURA:
                return self._responder(404, {"message": "Rota não encontrada."})
            if not self._autorizado():
                return self._responder(401, {"message": "Não autorizado."})

            tamanho = int(self.headers.get("Content-Length", 0))
            try:
                dados = json.loads(self.rfile.read(tamanho))
            except json.JSONDecodeError:
                return self._responder(422, {"message": "JSON inválido."})

            erros = _validar(dados)
            if erros:
                return self._responder(422, {"message": "Dados inválidos.", "errors": {e: [e] for e in erros}})

            evento = dados.get("event") or "sample"
            with banco.lock:
                ensaio = banco.ensaios.get(dados["test_run_id"])
                if ensaio is None:
                    return self._recusar("test_run_id", "Ensaio não encontrado.")
                if ensaio["device"] != dados["device_code"].upper():
                    return self._recusar("device_code", "Este M2 não pertence ao ensaio informado.")
                if ensaio["status"] not in ("armed", "running"):
                    return self._recusar("test_run_id", "O ensaio não está aceitando novas leituras.")

                leitura = (dados["elapsed_ms"], dados["load_grams"])
                existente = ensaio["amostras"].get(dados["sequence"])
                if existente is not None:
                    if existente != leitura:
                        return self._recusar("sequence", "A sequência já foi usada com outra leitura.")
                    return self._responder(202, {"accepted": True, "duplicate": True, "event": evento})

                ensaio["amostras"][dados["sequence"]] = leitura
                codigo = ensaio["equipe"]
                equipe = banco.equipes[codigo]
                banco.eventos.append((codigo, evento, *leitura, dados["test_run_id"]))
                if evento == "completed":
                    ensaio["status"] = "finished"
                    equipe["test_status"] = "completed"
                    equipe["actual_load_grams"] = max(g for _, g in ensaio["amostras"].values())
                else:
                    ensaio["status"] = "running"
                    equipe["test_status"] = "running"

            linha = f"[MOCK MÓDULO 3] {codigo} {evento:9s} seq={dados['sequence']} t={leitura[0] / 1000:6.1f}s carga={leitura[1] / 1000:7.2f} kg"
            if evento == "completed":
                linha += f"  → RUPTURA REGISTRADA: {equipe['actual_load_grams'] / 1000:.2f} kg"
            log(linha)
            self._responder(202, {"accepted": True, "duplicate": False, "event": evento})

        def _autorizado(self):
            return not token or self.headers.get("Authorization", "") == f"Bearer {token}"

        def _recusar(self, campo, mensagem):
            return self._responder(422, {"message": mensagem, "errors": {campo: [mensagem]}})

        def _responder(self, status, corpo):
            if status >= 400 and status != 404:
                log(f"[MOCK MÓDULO 3] recusado {status}: {corpo['message']}")
            dados = json.dumps(corpo).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, format, *args):
            pass  # silencia o log padrão de acesso HTTP (já imprimimos o que importa)

    return MockHandler


def criar_servidor(porta, token, banco=None, device_padrao="M2-01", verbose=True):
    banco = banco or BancoMock()
    handler = criar_handler(banco, token, device_padrao, verbose)
    return ThreadingHTTPServer(("0.0.0.0", porta), handler), banco


if __name__ == "__main__":
    carregar_env()
    porta = int(os.getenv("SPINO_MOCK_PORT", "8000"))
    token = os.getenv("SPINO_MODULO3_TOKEN") or None
    device = os.getenv("SPINO_DEVICE_CODE", "M2-01").upper()

    servidor, banco = criar_servidor(porta, token, device_padrao=device)
    banco.armar("MOCK001", device)
    print(f"🧪 Mock do Módulo 3 em http://127.0.0.1:{porta} — ensaio da MOCK001 já armado no {device}")
    print(f"   Armar outro: http://127.0.0.1:{porta}/mock/armar/MOCK002  |  cancelar: http://127.0.0.1:{porta}/mock/cancelar")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando mock do Módulo 3...")
