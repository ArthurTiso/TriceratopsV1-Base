from rpi_rf import RFDevice
import time

rfdevice = RFDevice(18)  # GPIO17 (pino 11)
rfdevice.enable_rx()

CODIGO_ESPERADO = 123456  # <-- coloque aqui o código do seu Arduino

print("Aguardando sinais RF...")

try:
    while True:
        if rfdevice.rx_code_timestamp is not None:
            
            codigo = rfdevice.rx_code

            if codigo == CODIGO_ESPERADO:
                print("🚀 MEU TRANSMISSOR DETECTADO! Código:", codigo)
          #  else:
                # opcional: comentar essa linha se quiser ignorar totalmente ruído
               # print("Ignorado:", codigo)

            rfdevice.rx_code_timestamp = None

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Encerrando...")
finally:
    rfdevice.cleanup()
