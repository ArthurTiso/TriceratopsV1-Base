from datetime import datetime, timedelta


class Processor:
    def __init__(self, state):
        self.state = state
        self.tempo_ultimo_dado = None

    def processar(self, dados: dict):
        agora = datetime.now()

        # Atualiza estado base
        self.state.atualizar(dados)

        # 🔥 STATUS BASEADO NO ARDUINO (CORRETO)
        if dados["flag"] == 0:
            self.state.set_status("RUNNING")

        elif dados["flag"] == 1:
            self.state.set_status("BROKEN")

        # Atualiza tempo do último dado
        self.tempo_ultimo_dado = agora

        # 🔥 DETECÇÃO DE INATIVIDADE (AGORA FUNCIONA DE VERDADE)
        if self.state.ultimo_update:
            if agora - self.state.ultimo_update > timedelta(seconds=10):
                self.state.set_status("INACTIVE")
