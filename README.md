# Spino — Módulo 2 · Processamento de borda

Recebe os quadros do Módulo 1 (Arduino transmissor 433 MHz) por meio de um
Arduino receptor ligado via USB ao Raspberry Pi, acompanha o ciclo de cada
ensaio, exibe os dados na interface local e envia a telemetria ao Módulo 3
(API Laravel) sem bloquear a leitura.

```
Arduino transmissor ──RF 433 MHz (RH_ASK)──► Arduino receptor ──USB serial──► Raspberry Pi
                                                                                 │
                                    receiver/ → protocol/ → core/ ───────────────┤
                                                                ├─► data.json ──► dashboard/ (Streamlit)
                                                                └─► sender/ ────► Módulo 3 (HTTP POST)
```

| Pasta | Função |
|---|---|
| `firmware/receptor_rf/` | Sketch do Arduino receptor: RH_ASK → uma linha por quadro na serial |
| `receiver/` | `SerialReceiver` (hardware) e `SimulatedReceiver` (reproduz o firmware do Módulo 1) |
| `protocol/` | Decoder e encoder do quadro SPINO |
| `core/` | Estado do ensaio, detecção de colapso e novo ensaio, política de envio |
| `sender/` | Contrato HTTP, envio em background e mock do Módulo 3 |
| `app/` | Configuração, pipeline e loop principal |
| `dashboard/` | Interface local |
| `legacy/` | RF direto no GPIO do Pi (fora de uso) |

## Protocolo do Módulo 1

```
*** BAT CM   CA   DEF TEM  F CHK ###     (27 caracteres)
```

- `CM` / `CA`: carga máxima / atual em kg × 10 (`0123` = 12,3 kg);
- `TEM`: segundos de ensaio, congelado no colapso;
- `F`: 1 no colapso (firmware antigo: 1 durante todo o ensaio — ambos aceitos);
- `BAT` / `DEF`: reservados, enviados como 0;
- `CHK`: soma dos 3 últimos dígitos do corpo, módulo 100.

## Ciclo do ensaio

| Situação | Detecção | Envio ao Módulo 3 |
|---|---|---|
| Novo ensaio | primeiro quadro; após colapso, tempo diferente do congelado; tempo voltou | `started` |
| Em andamento | — | `sample` a cada 1 s e a cada novo pico |
| Colapso | flag de colapso, ou carga ≤ 20% da máxima (máx. ≥ 2 kg) com tempo parado por ≥ 2 s | `completed`, uma única vez |
| Após colapso | quadro final repetido pelo Arduino | nenhum |
| Sem quadros por 10 s | — | status `INACTIVE` no painel |

## Instalação

Python 3.10 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / Raspberry Pi
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e ajuste os valores. Variáveis definidas no
terminal têm prioridade sobre o arquivo.

| Variável | Descrição |
|---|---|
| `SPINO_TEAM_CODE` | Código da equipe em ensaio (aprovada no Módulo 3) |
| `SPINO_MODULO3_URL` | Endpoint `/api/v1/sensors/capture` do Módulo 3 |
| `SPINO_MODULO3_TOKEN` | Igual a `SENSORS_API_TOKEN` do Módulo 3 |
| `SPINO_SEND_INTERVAL_SECONDS` | Intervalo mínimo entre amostras (padrão 1) |
| `SPINO_RECEIVER` | `serial` (Arduino receptor) ou `simulador` |
| `SPINO_SERIAL_PORT` / `SPINO_SERIAL_BAUD` | Ex.: `COM3` ou `/dev/ttyACM0`, 9600 |
| `SPINO_SIM_FIRMWARE` / `SPINO_SIM_PERDA_RF` | Simulador: `atual` ou `corrigido`; fração de perda de quadros |

No Raspberry Pi, o usuário precisa pertencer ao grupo `dialout` para abrir a
porta serial.

## Execução

```bash
python -m app.main                       # Módulo 2
streamlit run dashboard/app.py           # interface local
python -m sender.mock_modulo3_server     # opcional: Módulo 3 simulado (porta 8000)
```

O firmware do receptor (`firmware/receptor_rf/receptor_rf.ino`) usa a
biblioteca RadioHead; o DATA do módulo 433 MHz fica no pino 2.

## Testes

```bash
python -m unittest discover -s tests
```

## Contrato com o Módulo 3

`POST /api/v1/sensors/capture` com `Authorization: Bearer <token>`:

```json
{
  "team_code": "MOCK001",
  "elapsed_ms": 12000,
  "load_grams": 7300,
  "event": "sample",
  "timestamp": "2026-10-08T12:00:00+00:00"
}
```

`event`: `started`, `sample` ou `completed`. Carga em gramas, com resolução de
100 g. Erros 401, 404 e 422 são registrados sem nova tentativa; falhas de rede,
5xx e 429 são repetidas.
