from rpi_rf import RFDevice

rfdevice = RFDevice(17)  # GPIO
rfdevice.enable_rx()

print("Aguardando sinal RF...")

try:
    while True:
        if rfdevice.rx_code_timestamp != None:
            print("Recebido:", rfdevice.rx_code)
            rfdevice.rx_code_timestamp = None

except KeyboardInterrupt:
    pass

rfdevice.cleanup()