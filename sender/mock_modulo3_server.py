"""
Servidor mock do Módulo 3 — só para testar o envio HTTP do Módulo 2
localmente, sem depender do backend Laravel real.

Rodar em outro terminal, a partir da raiz do projeto:
    python -m sender.mock_modulo3_server
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORTA = 8000


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho)

        try:
            dados = json.loads(corpo)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "(sem token)")
        print(f"[MOCK MÓDULO 3] recebido ({auth}): {dados}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        pass  # silencia o log padrão de acesso HTTP (já imprimimos o que importa)


if __name__ == "__main__":
    servidor = HTTPServer(("0.0.0.0", PORTA), MockHandler)
    print(f"🧪 Mock do Módulo 3 escutando em http://localhost:{PORTA}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando mock do Módulo 3...")
