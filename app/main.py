import time

from app.config import ARQUIVO_ESTADO, carregar_config
from app.console import AJUDA, Console
from app.pipeline import Pipeline
from sender.api_sender import ApiSender
from sender.ensaio_ativo import ConsultaEnsaioAtivo
from sender.modulo3_payload import url_captura, url_ensaio_ativo

# python -m app.main
# Configuração: arquivo .env na raiz do projeto (veja .env.example)


def criar_receiver(config):
    if config.receptor == "serial":
        from receiver.serial_receiver import SerialReceiver
        print(f"📡 Balança (Módulo 1) via USB em {config.porta_serial}")
        print("   O Arduino reinicia e faz a tara ao conectar: mantenha a balança SEM CARGA.")
        return SerialReceiver(config.porta_serial, config.baud_serial)

    from receiver.simulated_receiver import SimulatedReceiver
    print("🧪 Modo SIMULADOR — balança simulada; cada 'novo' simula um ensaio até a ruptura")
    return SimulatedReceiver()


def main():
    receiver = None
    sender = None
    consulta = None

    try:
        config = carregar_config()
        receiver = criar_receiver(config)
        sender = ApiSender(url_captura(config.modulo3_url), config.modulo3_token)
        consulta = ConsultaEnsaioAtivo(
            url_ensaio_ativo(config.modulo3_url, config.device_code), config.modulo3_token
        )
        pipeline = Pipeline(
            config.device_code,
            receiver,
            sender,
            consulta=consulta,
            arquivo_estado=ARQUIVO_ESTADO,
            intervalo_envio_s=config.intervalo_envio_s,
            peso_minimo_colapso_kg=config.peso_minimo_colapso_kg,
            fracao_colapso=config.fracao_colapso,
            confirmacao_colapso_s=config.confirmacao_colapso_s,
        )
        console = Console()

        print(f"Módulo 3: {config.modulo3_url} | este M2: {config.device_code}")
        print("Arme o ensaio no Módulo 3 (Administração → Ensaios) para este M2.")
        print(AJUDA)

        while True:
            comando = console.proximo()
            if comando is not None and not pipeline.executar_comando(comando):
                break

            linha = receiver.receber()
            if linha:
                pipeline.processar_linha(linha)
            else:
                pipeline.verificar()
                # A serial já espera pelo timeout de leitura; o simulador não.
                time.sleep(0.02)

    except KeyboardInterrupt:
        pass

    finally:
        print("\nFinalizando sistema...")
        if receiver and hasattr(receiver, "cleanup"):
            receiver.cleanup()

        if consulta:
            consulta.parar()
        if sender:
            sender.parar()


if __name__ == "__main__":
    main()
