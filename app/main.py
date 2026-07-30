import time
import sys

from protocol.decoder import ProtocolDecoder
from core.system_state import SystemState
from core.processor import Processor

# 🔥 CONTROLE AQUI
USAR_RF = False  # True = Raspberry | False = Simulador


def main():
    receiver = None

    try:
        # 🔥 ESCOLHA DO RECEIVER
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

                import json

                with open("data.json", "w") as f:
                    json.dump(state.get_snapshot(), f)

            except Exception as e:
                print("ERRO:", e)

            print("-" * 50)

            # 🔥 IMPORTANTE PARA RF (não perder pacote)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nFinalizando sistema...")

    finally:
        # 🔥 LIMPEZA GPIO (só RF tem isso)
        if receiver and hasattr(receiver, 'cleanup'):
            receiver.cleanup()


if __name__ == "__main__":
    main()
