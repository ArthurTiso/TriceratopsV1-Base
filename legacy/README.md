# Código legado (fora de uso)

Mantido apenas como referência. Nada aqui é importado pelo Módulo 2.

## `rpi_rf/`

Primeira abordagem: receptor 433 MHz ligado direto no GPIO do Raspberry Pi,
lido com a biblioteca `rpi_rf`. Foi substituída pelo Arduino receptor via USB
(`firmware/receptor_rf/` + `receiver/serial_receiver.py`) porque:

- `rpi_rf` só decodifica códigos inteiros de controle remoto (rc-switch), não
  os pacotes RadioHead `RH_ASK` que o transmissor do Módulo 1 envia;
- `rf_receiver.py` montava um quadro de 22 caracteres (o protocolo tem 21),
  com flag e checksum fixos.

Dependências desses scripts: `requirements-pi.txt` (`rpi_rf`, `RPi.GPIO`).
