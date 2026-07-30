from datetime import datetime


class SystemState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.bateria = 0
        self.peso_atual = 0
        self.peso_max = 0
        self.angulo = 0
        self.tempo = 0
        self.status = "IDLE"

        self.historico = []  # [(tempo, peso)]
        self.ultimo_update = None

        # Cronômetro: marca quando o peso_atual mudou pela última vez
        self.ultima_mudanca_peso = None

    def atualizar(self, dados: dict):
        peso_anterior = self.peso_atual

        self.bateria = dados["bateria"]
        self.peso_atual = dados["peso_atual"]
        self.peso_max = dados["peso_max"]
        self.angulo = dados["angulo"]
        self.tempo = dados["tempo"]

        agora = datetime.now()
        self.ultimo_update = agora

        # Reinicia o cronômetro sempre que o peso_atual mudar
        if self.ultima_mudanca_peso is None or self.peso_atual != peso_anterior:
            self.ultima_mudanca_peso = agora

        # Atualiza histórico
        self.historico.append((self.tempo, self.peso_atual))

        # Limita histórico
        self.historico = self.historico[-50:]

    def set_status(self, status: str):
        self.status = status

    def get_snapshot(self):
        segundos_desde_mudanca = None
        if self.ultima_mudanca_peso is not None:
            segundos_desde_mudanca = (datetime.now() - self.ultima_mudanca_peso).total_seconds()

        return {
            "bateria": self.bateria,
            "peso_atual": self.peso_atual,
            "peso_max": self.peso_max,
            "angulo": self.angulo,
            "tempo": self.tempo,
            "status": self.status,
            "historico": self.historico,
            "segundos_desde_mudanca": segundos_desde_mudanca
        }