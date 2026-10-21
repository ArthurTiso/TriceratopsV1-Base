# Spino — Módulo 2 · Processamento no notebook

O Módulo 1 (células de carga + HX711 + Arduino) fica ligado por cabo USB a um
notebook. O Módulo 2 lê a balança, controla cada ensaio (tara, cronômetro e
detecção de ruptura), exibe os dados na interface local e envia a telemetria
ao Módulo 3 (API Laravel).

```
Células de carga ─► HX711 ─► Arduino (Módulo 1) ──USB serial 115200──► Notebook (Módulo 2)
                                                                          │
                     receiver/ → protocol/ → core/ ───────────────────────┤
                       ▲                         ├─► data.json ─► dashboard/ (Streamlit)
          comandos do operador (terminal)        └─► sender/ ───► Módulo 3 (HTTP POST)
```

| Pasta | Função |
|---|---|
| `firmware/modulo1_balanca_usb/` | Firmware do Arduino do Módulo 1 |
| `receiver/` | `SerialReceiver` (Arduino via USB) e `SimulatedReceiver` (reproduz o firmware) |
| `protocol/` | Interpretação das linhas enviadas pelo Arduino |
| `core/` | Estado, controle do ensaio (tara, cronômetro, colapso) e política de envio |
| `sender/` | Contrato HTTP, envio em background e mock do Módulo 3 |
| `app/` | Configuração, console do operador, pipeline e loop principal |
| `dashboard/` | Interface local |

## Comunicação com o Módulo 1

A cada 500 ms o Arduino envia uma linha:

```
AMOSTRA_KG=12.3 | MEDIA_KG=12.1 | PICO_ABS_KG=12.4 | BRUTO=-325112
```

- `MEDIA_KG`: média móvel das últimas 10 leituras do HX711 (com sinal);
- `PICO_ABS_KG`: maior magnitude da média desde a última tara;
- durante a tara: `TARA=n/20`; ao fim: `Tara concluida. Offset=...`;
- sensor sem resposta: `ERRO: HX711 sem dados...`.

O Módulo 2 envia `t` para tarar. Ao abrir a porta USB o Arduino reinicia e faz
a tara de inicialização — a balança deve estar sem carga.

## Ciclo do ensaio

A comissão arma cada ensaio no Módulo 3 (Administração → Ensaios), escolhendo a
equipe e este M2 (`SPINO_DEVICE_CODE`, ex.: `M2-01`). O Módulo 2 consulta o
ensaio armado a cada 2 s e o anuncia no terminal; o operador confirma com `novo`.

| Etapa | Como acontece | Envio ao Módulo 3 |
|---|---|---|
| Início | ensaio armado no Módulo 3 → operador digita `novo` → tara → cronômetro começa no fim da tara | `started` |
| Em andamento | carga = \|MEDIA_KG\|, pico = PICO_ABS_KG | `sample` a cada 1 s e a cada novo pico |
| Colapso | pico ≥ 2 kg e carga ≤ 20% do pico por ≥ 1 s | `completed` com o pico, uma única vez |
| Encerramento manual | operador digita `fim` | `completed` com o pico |
| Cancelamento | `cancelar` no Módulo 2 ou ensaio cancelado/encerrado no Módulo 3 | nenhum |
| Tara inesperada (Arduino reiniciado) | ensaio interrompido | nenhum |
| Sem linhas por 5 s / erro no HX711 | status `INACTIVE` / `ERRO_SENSOR` no painel | pausado |

## Instalação

Python 3.10 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e ajuste os valores. Variáveis definidas no
terminal têm prioridade sobre o arquivo.

| Variável | Descrição |
|---|---|
| `SPINO_RECEIVER` | `serial` (Arduino) ou `simulador` |
| `SPINO_SERIAL_PORT` / `SPINO_SERIAL_BAUD` | Porta do Arduino (ex.: `COM3`) e 115200 |
| `SPINO_MODULO3_URL` | Endereço do Módulo 3 (ex.: `https://pontedepalito.ifspcaraguatatuba.edu.br`) |
| `SPINO_MODULO3_TOKEN` | Igual a `SENSORS_API_TOKEN` do Módulo 3 |
| `SPINO_DEVICE_CODE` | Código deste M2 no Módulo 3 (padrão `M2-01`) |
| `SPINO_SEND_INTERVAL_SECONDS` | Intervalo mínimo entre amostras (padrão 1) |
| `SPINO_COLAPSO_PESO_MINIMO_KG` / `_FRACAO` / `_CONFIRMACAO_S` | Regra de colapso (2,0 kg · 0,20 · 1,0 s) |

## Execução

```bash
python -m app.main                       # Módulo 2 (console do operador)
streamlit run dashboard/app.py           # interface local
python -m sender.mock_modulo3_server     # opcional: Módulo 3 simulado (porta 8000, MOCK001 já armado)
```

Comandos no terminal do Módulo 2:

| Comando | Ação |
|---|---|
| `novo` | tara a balança sem carga e inicia o ensaio armado no Módulo 3 |
| `fim` | encerra o ensaio atual como concluído |
| `cancelar` | descarta o ensaio atual |
| `tara` | zera a balança fora de ensaio |
| `ajuda` / `sair` | lista os comandos / encerra |

O Monitor Serial da IDE do Arduino deve estar fechado: a porta USB só pode
ser usada por um programa por vez.

## Testes

```bash
python -m unittest discover -s tests
```

## Contrato com o Módulo 3

Com `Authorization: Bearer <token>`:

`GET /api/v1/sensors/devices/{M2}/active-run` → `{"active": true, "run_id": "...", "status": "armed", "team": {"code": "...", "name": "..."}}`

`POST /api/v1/sensors/capture`:

```json
{
  "test_run_id": "uuid-do-ensaio",
  "device_code": "M2-01",
  "sequence": 925430861,
  "elapsed_ms": 12500,
  "load_grams": 7300,
  "event": "sample",
  "timestamp": "2026-10-21T12:00:00+00:00"
}
```

`event`: `started`, `sample` ou `completed`. Carga em gramas, com resolução de
100 g; o `completed` leva o pico calculado pelo Arduino. A `sequence` cresce a
cada leitura e continua acima da anterior se o mesmo ensaio for retomado, então
reenvios são reconhecidos como duplicatas. Erros 401, 404 e 422 são registrados
sem nova tentativa; falhas de rede, 5xx e 429 são repetidas.
