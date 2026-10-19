class BaseReceiver:
    def receber(self):
        """Devolve a próxima linha enviada pelo Módulo 1, ou None se não houver."""
        raise NotImplementedError("Método receber() deve ser implementado.")

    def enviar_comando(self, comando: str):
        """Envia um comando ao Módulo 1 (ex.: "t" para tarar)."""
        raise NotImplementedError("Método enviar_comando() deve ser implementado.")
