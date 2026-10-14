// ============================================================
// SPINO — Arduino receptor do Módulo 2
//
// Recebe os quadros do transmissor (Módulo 1, RadioHead RH_ASK a
// 2000 bps) e repassa cada quadro pela USB serial ao Raspberry Pi,
// um por linha:
//
//   ***BBBCCCCAAAADDDTTTTFKK###
//
// O RH_ASK já descarta pacotes corrompidos (CRC-16), então só
// chegam ao Pi quadros íntegros.
//
// Ligações: DATA do módulo receptor 433 MHz no pino 2. Os pinos
// 12 (TX) e 10 (PTT) são reservados pelo RH_ASK.
// ============================================================

#include <RH_ASK.h>
#include <SPI.h>  // exigido pela RadioHead, mesmo sem usar SPI

const uint8_t PIN_RF_RX         = 2;
const uint8_t PIN_RF_TX_UNUSED  = 12;
const uint8_t PIN_RF_PTT_UNUSED = 10;

// Velocidade precisa ser a mesma do transmissor (2000 bps).
RH_ASK radio(
  2000,
  PIN_RF_RX,
  PIN_RF_TX_UNUSED,
  PIN_RF_PTT_UNUSED,
  false
);

const uint8_t TAMANHO_QUADRO = 27;

void setup() {

  Serial.begin(9600);  // deve casar com SPINO_SERIAL_BAUD no Módulo 2

  if (!radio.init()) {
    Serial.println("ERRO: radio RH_ASK nao inicializou");
  } else {
    Serial.println("Receptor SPINO pronto");
  }
}

void loop() {

  uint8_t buf[RH_ASK_MAX_MESSAGE_LEN];
  uint8_t len = sizeof(buf);

  if (radio.recv(buf, &len)) {

    if (
      len == TAMANHO_QUADRO &&
      buf[0] == '*' &&
      buf[TAMANHO_QUADRO - 1] == '#'
    ) {
      Serial.write(buf, len);
      Serial.println();
    }
  }
}
