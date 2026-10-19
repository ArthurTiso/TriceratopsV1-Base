#include <Arduino.h>
#include <HX711.h>
#include <math.h>


// Somente celulas de carga -> HX711 -> Arduino -> USB -> computador.
const uint8_t PIN_HX_DAT = 46;
const uint8_t PIN_HX_CLK = 47;


// Calibracao inicial pelas duas series de 6, 10, 15, 20, 25 e 30 kg.
// As medicoes usaram a escala anterior de -34496.02.
// Validar novamente: ha variacao entre as series. Tara corrige apenas o zero.
const float ESCALA = -26422.05f;
const uint8_t TOTAL_AMOSTRAS_TARA = 20;
const uint8_t TAMANHO_MEDIA = 10;
const unsigned long INTERVALO_SERIAL = 500UL;
const unsigned long TEMPO_SEM_HX = 2000UL;


HX711 balanca;
bool tarando = true;
bool temLeitura = false;
int64_t somaTara = 0;
uint8_t contadorTara = 0;
long offsetTara = 0;
long leituraBruta = 0;
float pesoAmostra = 0.0f;
float pesoMedio = 0.0f;
float picoAbsoluto = 0.0f;
float amostras[TAMANHO_MEDIA] = {0};
float somaMedia = 0.0f;
uint8_t indiceMedia = 0;
uint8_t quantidadeMedia = 0;
unsigned long ultimaLeituraHX = 0;
unsigned long ultimoSerial = 0;


void limparMedia() {
  somaMedia = 0.0f;
  indiceMedia = 0;
  quantidadeMedia = 0;
  pesoMedio = 0.0f;
  for (uint8_t i = 0; i < TAMANHO_MEDIA; i++) amostras[i] = 0.0f;
}


void iniciarTara() {
  tarando = true;
  temLeitura = false;
  somaTara = 0;
  contadorTara = 0;
  offsetTara = 0;
  balanca.set_offset(0);
  pesoAmostra = 0.0f;
  picoAbsoluto = 0.0f;
  limparMedia();
  ultimaLeituraHX = millis();
  Serial.println(F("Tarando: deixe a balanca sem carga (20 amostras)."));
}


void atualizarPeso(float kg) {
  pesoAmostra = kg;
  // Media movel: substitui a leitura mais antiga quando completar 10.
  somaMedia -= amostras[indiceMedia];
  amostras[indiceMedia] = kg;
  somaMedia += kg;
  indiceMedia = (indiceMedia + 1) % TAMANHO_MEDIA;
  if (quantidadeMedia < TAMANHO_MEDIA) quantidadeMedia++;
  pesoMedio = somaMedia / quantidadeMedia;


  // Mantem o sinal na amostra e na media para nao esconder cargas negativas.
  // O pico e a maior magnitude da media desde a ultima tara.
  float magnitude = fabs(pesoMedio);
  if (magnitude > picoAbsoluto) picoAbsoluto = magnitude;
}


void processarHX711() {
  // Sem bloquear o programa quando o HX711 nao tem dados disponiveis.
  if (!balanca.is_ready()) return;


  unsigned long agora = millis();
  if (!tarando && agora - ultimaLeituraHX >= TEMPO_SEM_HX) {
    // Ao reconectar, nao mistura leituras novas com as anteriores a falha.
    limparMedia();
  }
  leituraBruta = balanca.read();
  ultimaLeituraHX = millis();
  temLeitura = true;


  if (tarando) {
    somaTara += (int64_t)leituraBruta;
    contadorTara++;
    if (contadorTara < TOTAL_AMOSTRAS_TARA) return;
    offsetTara = (long)(somaTara / TOTAL_AMOSTRAS_TARA);
    balanca.set_offset(offsetTara);
    tarando = false;
    // Aguarda a primeira amostra apos a tara antes de mostrar os pesos.
    temLeitura = false;
    Serial.print(F("Tara concluida. Offset="));
    Serial.println(offsetTara);
    return;
  }


  float kg = (leituraBruta - offsetTara) / ESCALA;
  if (isfinite(kg)) atualizarPeso(kg);
}


void processarComandos() {
  while (Serial.available() > 0) {
    char comando = Serial.read();
    // A tara tambem limpa a media e o pico.
    if (comando == 't' || comando == 'T') iniciarTara();
  }
}


void mostrarNoPC() {
  unsigned long agora = millis();
  if (agora - ultimoSerial < INTERVALO_SERIAL) return;
  ultimoSerial = agora;


  if (agora - ultimaLeituraHX >= TEMPO_SEM_HX) {
    Serial.println(F("ERRO: HX711 sem dados ha pelo menos 2 s. Confira DT, SCK, alimentacao e GND."));
    return;  // Nao apresenta pesos antigos como se fossem atuais.
  }


  if (tarando) {
    Serial.print(F("TARA="));
    Serial.print(contadorTara);
    Serial.print('/');
    Serial.print(TOTAL_AMOSTRAS_TARA);
    if (temLeitura) {
      Serial.print(F(" | BRUTO="));
      Serial.print(leituraBruta);
    }
    Serial.println();
    return;
  }
  if (!temLeitura) return;


  Serial.print(F("AMOSTRA_KG="));
  Serial.print(pesoAmostra, 1);
  Serial.print(F(" | MEDIA_KG="));
  Serial.print(pesoMedio, 1);
  Serial.print(F(" | PICO_ABS_KG="));
  Serial.print(picoAbsoluto, 1);
  Serial.print(F(" | BRUTO="));
  Serial.println(leituraBruta);
}


void setup() {
  Serial.begin(115200);
  Serial.println(F("SPINO - balanca no PC via USB"));
  Serial.println(F("HX711: DT=46 | SCK=47 | Monitor Serial=115200 baud"));
  Serial.print(F("Escala de calibracao: "));
  Serial.println(ESCALA, 2);
  Serial.println(F("MEDIA_KG: media movel das ultimas 10 amostras, mantendo o sinal."));
  Serial.println(F("PICO_ABS_KG: maior magnitude da media desde a tara."));
  Serial.println(F("Comando: t + Enviar, sem carga, para tarar e zerar o pico."));
  balanca.begin(PIN_HX_DAT, PIN_HX_CLK);
  balanca.set_scale(ESCALA);
  iniciarTara();
}


void loop() {
  processarComandos();
  processarHX711();
  mostrarNoPC();
}
