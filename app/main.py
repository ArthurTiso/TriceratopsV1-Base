import time
import sys
import json

from protocol.decoder import ProtocolDecoder
from core.system_state import SystemState
from core.processor import Processor
from sender.api_sender import ApiSender

#python -m app.main

#  CONTROLE AQUI
USAR_RF = False  # True = Raspberry | False = Simulador


def main():
    receiver = None
    sender = None

    try:
        #  ESCOLHA DO RECEIVER
        if USAR_RF:
            from receiver.rf_receiver import RFReceiver
            receiver = RFReceiver(gpio=27)
            print("📡 Modo RF ativado")

        else:
            from receiver.simulated_receiver import SimulatedReceiver
            receiver = SimulatedReceiver()
            print("🧪 Modo SIMULADOR ativado")

        decoder = ProtocolDecoder()
        state = SystemState()
        processor = Processor(state)
        sender = ApiSender()

        print("Sistema iniciado. Aguardando pacotes...\n")

        while True:
            pacote = receiver.receber()
            time.sleep(0.4)
            if not pacote:
                continue

            print("PACOTE:", pacote)

            try:
                dados = decoder.decodificar(pacote)

                processor.processar(dados)

                print("STATE:", state.get_snapshot())

                with open("data.json", "w") as f:
                    json.dump(state.get_snapshot(), f)

                #  ENVIO PRO MÓDULO 3 — enfileira e segue, não espera resposta
                sender.enviar({
                    "bateria": dados["bateria"],
                    "peso_max": dados["peso_max"],
                    "peso_atual": dados["peso_atual"],
                    "angulo": dados["angulo"],
                    "tempo": dados["tempo"],
                    "status": state.status,
                })

            except Exception as e:
                print("ERRO:", e)

            print("-" * 50)

            #  IMPORTANTE PARA RF (não perder pacote)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nFinalizando sistema...")

    finally:
        #  LIMPEZA GPIO (só RF tem isso)
        if receiver and hasattr(receiver, 'cleanup'):
            receiver.cleanup()

        if sender:
            sender.parar()


if __name__ == "__main__":
    main()