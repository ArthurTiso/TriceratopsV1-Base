# Módulo 2 — integração com o Módulo 3

O Módulo 2 recebe e processa as leituras do Módulo 1 e as envia para o
Módulo 3 sem bloquear a aquisição RF.

## Configuração no Raspberry Pi

Defina as variáveis abaixo antes de iniciar o processo. Use `.env.example`
como referência; não versione o token real.

```bash
export SPINO_TEAM_CODE=PONTE001
export SPINO_MODULO3_URL=http://IP_DO_SERVIDOR:8000/api/v1/sensors/capture
export SPINO_MODULO3_TOKEN=mesmo-token-configurado-no-modulo-3
export SPINO_SEND_INTERVAL_SECONDS=1
python -m app.main
```

## Contrato HTTP enviado ao Módulo 3

```json
{
  "team_code": "PONTE001",
  "elapsed_ms": 12000,
  "load_grams": 7250,
  "event": "sample"
}
```

O Módulo 2 exibe e processa `peso_atual` em **kg**. Antes do envio ele o
converte para `load_grams`, unidade usada pelo Módulo 3 no banco; o placar
volta a apresentar esse valor em kg. Quando o Arduino sinaliza ruptura,
`event` é enviado uma única vez como `completed`.

A leitura RF permanece na frequência nativa. Por padrão, o envio HTTP é
amostrado em uma leitura por segundo para ficar abaixo do limite da API;
`SPINO_SEND_INTERVAL_SECONDS` pode ajustar esse intervalo.

## Testes

```bash
python -m unittest discover -s tests
```
