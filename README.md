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
Módulo 3 a cada 2 s. O ensaio pode ser iniciado de três formas — todas fazem a
tara (ponte montada, sem carga) e começam a medir:

* **Iniciar no Módulo 3**: o M2 percebe o ensaio passar de armado para em
  andamento e começa sozinho;
* **Iniciar ensaio no painel** (Controle manual) ou `novo` no terminal;
* **Modo local**, sem ensaio armado ou com o Módulo 3 fora do ar: informar a
  equipe no painel ou `novo EQUIPE` — nada é enviado ao Módulo 3.

| Etapa | Como acontece | Envio ao Módulo 3 |
|---|---|---|
| Início | uma das formas acima → tara → cronômetro começa no fim da tara | `started` |
| Em andamento | carga = \|MEDIA_KG\|, pico = PICO_ABS_KG | `sample` a cada 1 s e a cada novo pico |
| Ruptura detectada | pico ≥ 2 kg e carga ≤ 20% do pico por ≥ 1 s: o painel pede a confirmação; o ensaio segue aberto | `sample` (continua) |
| Ruptura confirmada | **Confirmar ruptura** no painel ou `fim` | `completed` com o pico, uma única vez |
| Encerrar/Cancelar no Módulo 3 | o M2 para; o pico fica em `resultados.csv` para lançar em Rupturas | nenhum |
| Cancelar no Módulo 2 | painel ou `cancelar` | nenhum |
| Tara inesperada (Arduino reiniciado) | ensaio interrompido | nenhum |
| Sem linhas por 5 s / erro no HX711 | status `INACTIVE` / `ERRO_SENSOR` no painel | pausado |

O Módulo 3 só encerra o ensaio e registra a ruptura quando o operador confirma
no Módulo 2: a queda de carga detectada apenas avisa (faixa "Ruptura detectada"
e botão Confirmar ruptura em destaque). Se a carga voltar a subir antes da
confirmação, o aviso some e o ensaio continua. Confirmar sem a queda detectada
pede uma segunda confirmação.

Um ensaio que já estava em andamento quando o Módulo 2 é aberto nunca é tarado
automaticamente (a ponte pode estar carregada): use Iniciar ensaio no painel.

Todo resultado é gravado em `resultados.csv` (separador `;`, abre no Excel),
com a situação do registro no Módulo 3: `confirmado`, não registrado (com o
motivo) ou modo local.

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
| `SPINO_MODULO3_TOKEN` | Opcional; enviado como `Bearer` apenas se preenchido |
| `SPINO_DEVICE_CODE` | Código deste M2 no Módulo 3 (padrão `M2-01`) |
| `SPINO_SEND_INTERVAL_SECONDS` | Intervalo mínimo entre amostras (padrão 1) |
| `SPINO_COLAPSO_PESO_MINIMO_KG` / `_FRACAO` / `_CONFIRMACAO_S` | Regra de colapso (2,0 kg · 0,20 · 1,0 s) |

## Execução

No Windows, `iniciar_spino.bat` (dois cliques) abre o Módulo 2 e o painel.
Manualmente:

```bash
python -m app.main                       # Módulo 2
streamlit run dashboard/app.py           # painel (http://localhost:8501)
python -m sender.mock_modulo3_server     # opcional: Módulo 3 simulado (porta 8000)
```

O painel mostra o status, o gráfico da carga máxima, a carga máxima, os
eventos e as luzes da balança e do Módulo 3. Durante o ensaio, o botão
**Confirmar ruptura** fica acima dos eventos. A seção **Controle manual (M2)**
fica recolhida e abre sozinha quando o Módulo 3 não responde:

| Botão | Terminal | Ação |
|---|---|---|
| Confirmar ruptura | `fim` | registra a carga máxima no Módulo 3 e encerra |
| Iniciar ensaio | `novo` / `novo EQUIPE` | tara e inicia o ensaio armado (ou em modo local) |
| Cancelar | `cancelar` | descarta o ensaio, com confirmação |
| Tarar | `tara` | zera a balança fora de ensaio |

O Monitor Serial da IDE do Arduino deve estar fechado: a porta USB só pode
ser usada por um programa por vez.

## Testes

```bash
python -m unittest discover -s tests
```

## Contrato com o Módulo 3

Sem autenticação (o cabeçalho `Authorization: Bearer <token>` só é enviado se `SPINO_MODULO3_TOKEN` estiver preenchido):

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
