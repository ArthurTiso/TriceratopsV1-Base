import random
from receiver.base_receiver import BaseReceiver


class SimulatedReceiver(BaseReceiver):
    def __init__(self):
        self.bateria = 100
        self.peso_atual = 0
        self.peso_max = 0
        self.angulo = 0
        self.tempo = 0
        self.quebrou = False

    def _gerar_checksum(self, dados_str):
        soma = sum(int(d) for d in dados_str[-3:])
        return f"{soma % 100:02d}"

    def _formatar(self, valor, tamanho):
        return str(valor).zfill(tamanho)

    def receber(self):
        # Incrementa tempo sempre
        self.tempo += 1

        if not self.quebrou:
            # Peso sobe gradualmente
            incremento = random.randint(1, 5)
            self.peso_atual += incremento

            # Atualiza peso máximo (registro)
            if self.peso_atual > self.peso_max:
                self.peso_max = self.peso_atual

            # Chance de quebra (aumenta com o tempo)
            chance_quebra = min(0.02 + self.tempo * 0.002, 0.35)

            if random.random() < chance_quebra:
                print("[EVENTO] Ponte QUEBROU!")
                self.quebrou = True

        else:
            # Após quebra, peso despenca
            self.peso_atual = max(0, self.peso_atual - random.randint(20, 50))

        # Flag: 1 = quebrou
        flag = 1 if self.quebrou else 0

        # Monta dados
        dados = (
            self._formatar(self.bateria, 3) +
            self._formatar(self.peso_max, 4) +
            self._formatar(self.peso_atual, 4) +
            self._formatar(self.angulo, 3) +
            self._formatar(self.tempo, 4) +
            str(flag)
        )

        checksum = self._gerar_checksum(dados)

        pacote = f"***{dados}{checksum}###"

        return pacote