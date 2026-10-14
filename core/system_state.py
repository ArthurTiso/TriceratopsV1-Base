from datetime import datetime

# Status do ensaio exibidos pela interface local
IDLE = "IDLE"            # nenhum ensaio recebido ainda
RUNNING = "RUNNING"      # ensaio em andamento
BROKEN = "BROKEN"        # colapso detectado; aguardando o próximo ensaio
INACTIVE = "INACTIVE"    # ensaio em andamento, mas sem quadros há algum tempo

# Um ponto por segundo de ensaio; 900 pontos = 15 minutos de gráfico.
LIMITE_HISTORICO = 900


class SystemState:
    def __init__(self, equipe=None):
        self.equipe = equipe
        self.status = IDLE
        self.reset()

    def reset(self):
        """Zera os dados de medição (início de um novo ensaio)."""
        self.bateria = 0
        self.peso_atual = 0.0
        self.peso_max = 0.0
        self.angulo = 0
        self.tempo = 0

        self.historico = []  # [(tempo_s, peso_kg)]
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

        # O Arduino envia 2 quadros por segundo; o gráfico guarda um ponto
        # por segundo de ensaio.
        if not self.historico or self.historico[-1][0] != self.tempo:
            self.historico.append((self.tempo, self.peso_atual))
            self.historico = self.historico[-LIMITE_HISTORICO:]
        else:
            self.historico[-1] = (self.tempo, self.peso_atual)

    def set_status(self, status: str):
        self.status = status

    def get_snapshot(self):
        segundos_desde_mudanca = None
        if self.ultima_mudanca_peso is not None:
            segundos_desde_mudanca = (datetime.now() - self.ultima_mudanca_peso).total_seconds()

        return {
            "equipe": self.equipe,
            "bateria": self.bateria,
            "peso_atual": self.peso_atual,
            "peso_max": self.peso_max,
            "angulo": self.angulo,
            "tempo": self.tempo,
            "status": self.status,
            "historico": self.historico,
            "segundos_desde_mudanca": segundos_desde_mudanca,
        }
