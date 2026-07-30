from rpi_rf import RFDevice
from receiver.base_receiver import BaseReceiver


class RFReceiver(BaseReceiver):
    def __init__(self, gpio=17):
        self.rfdevice = RFDevice(gpio)
        self.rfdevice.enable_rx()

    def receber(self):
        if self.rfdevice.rx_code_timestamp:
            codigo = self.rfdevice.rx_code
            self.rfdevice.rx_code_timestamp = None

            try:
                peso = int(codigo)

                # reconstrução do sistema
                pacote = self.montar_pacote(peso)

                return pacote

            except:
                return None

        return None

    def montar_pacote(self, peso):
        peso_max = peso  # simplificação inicial
        tempo = 0
        flag = 1

        # montar no formato esperado
        pacote = f"***100{peso_max:04d}{peso:04d}0000{tempo:04d}{flag}00###"

        return pacote

    def cleanup(self):
        self.rfdevice.cleanup()