import time

from app.config import ARQUIVO_ESTADO, carregar_config
from app.pipeline import Pipeline
from sender.api_sender import ApiSender

# python -m app.main
# Configuração: arquivo .env na raiz do projeto (veja .env.example)


def criar_receiver(config):
    if config.receptor == "serial":
        from receiver.serial_receiver import SerialReceiver
        print(f"📡 Modo SERIAL — Arduino receptor em {config.porta_serial}")
        return SerialReceiver(config.porta_serial, config.baud_serial)

    from receiver.simulated_receiver import SimulatedReceiver
    print(f"🧪 Modo SIMULADOR — firmware '{config.firmware_simulado}', perda RF {config.perda_rf_simulada:.0%}")
    return SimulatedReceiver(firmware=config.firmware_simulado, perda_rf=config.perda_rf_simulada)


def main():
    receiver = None
    sender = None

    try:
        config = carregar_config()
        receiver = criar_receiver(config)
        sender = ApiSender(config.modulo3_url, config.modulo3_token)
        pipeline = Pipeline(
            config.team_code,
            sender,
            arquivo_estado=ARQUIVO_ESTADO,
            intervalo_envio_s=config.intervalo_envio_s,
        )

        print(f"Equipe: {config.team_code} | Módulo 3: {config.modulo3_url}")
        print("Sistema iniciado. Aguardando quadros do Módulo 1...\n")

        while True:
            pacote = receiver.receber()
            if pacote:
                pipeline.processar_quadro(pacote)
            else:
                pipeline.verificar_inatividade()
                # A serial já espera pelo timeout de leitura; o simulador não.
                time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nFinalizando sistema...")

    finally:
        if receiver and hasattr(receiver, "cleanup"):
            receiver.cleanup()

        if sender:
            sender.parar()


if __name__ == "__main__":
    main()
