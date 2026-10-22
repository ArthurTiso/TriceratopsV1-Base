from datetime import datetime

# Status exibidos pela interface local
IDLE = "IDLE"              # balança ligada, sem ensaio em andamento
TARANDO = "TARANDO"        # tara em andamento: balança deve estar sem carga
RUNNING = "RUNNING"        # ensaio em andamento
RUPTURA_DETECTADA = "RUPTURA_DETECTADA"  # queda de carga detectada, aguardando confirmação
BROKEN = "BROKEN"          # ruptura confirmada pelo operador (resultado enviado)
FINALIZADO = "FINALIZADO"  # ensaio encerrado no Módulo 3 sem o resultado do M2
INACTIVE = "INACTIVE"      # sem linhas do Arduino (cabo USB, energia)
ERRO_SENSOR = "ERRO_SENSOR"  # Arduino responde, mas o HX711 não

# Duas leituras por segundo; 1800 pontos = 15 minutos de gráfico.
LIMITE_HISTORICO = 1800


class SystemState:
    def __init__(self, equipe=None):
        self.equipe = equipe
        self.equipe_nome = None
        self.status = IDLE
        self.mensagem = None
        # Dados complementares do painel (eventos, Módulo 3, resultado...)
        self.extras = {}
        self.peso_atual = 0.0
        self.reset()

    def reset(self):
        """Zera os dados do ensaio (nova tara)."""
        self.peso_max = 0.0
        self.tempo = 0.0
        self.tempo_ruptura = None  # instante (s) em que a carga despencou
        self.historico = []  # [(tempo_s, carga_kg, pico_kg)]
        self.ultimo_update = None
        # Cronômetro: marca quando a carga mudou pela última vez
        self.ultima_mudanca_peso = None

    def atualizar_carga(self, carga_kg, pico_kg):
        agora = datetime.now()
        if self.ultima_mudanca_peso is None or carga_kg != self.peso_atual:
            self.ultima_mudanca_peso = agora
        self.peso_atual = carga_kg
        self.peso_max = pico_kg
        self.ultimo_update = agora

    def registrar_ponto(self, tempo_s):
        self.tempo = tempo_s
        ponto = (round(tempo_s, 1), self.peso_atual, self.peso_max)
        if self.historico and self.historico[-1][0] == ponto[0]:
            self.historico[-1] = ponto
        else:
            self.historico.append(ponto)
            self.historico = self.historico[-LIMITE_HISTORICO:]

    def set_status(self, status: str, mensagem=None):
        self.status = status
        self.mensagem = mensagem

    def get_snapshot(self):
        segundos_desde_mudanca = None
        if self.ultima_mudanca_peso is not None:
            segundos_desde_mudanca = (datetime.now() - self.ultima_mudanca_peso).total_seconds()

        return {
            **self.extras,
            "equipe": self.equipe,
            "equipe_nome": self.equipe_nome,
            "status": self.status,
            "mensagem": self.mensagem,
            "peso_atual": self.peso_atual,
            "peso_max": self.peso_max,
            "tempo": self.tempo,
            "tempo_ruptura": self.tempo_ruptura,
            "historico": self.historico,
            "segundos_desde_mudanca": segundos_desde_mudanca,
        }
