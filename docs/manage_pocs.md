# manage_pocs.sh

Script para subir e derrubar as PoCs sem rodar JMeter.

Ele reaproveita os helpers do orquestrador já usados pelo `run_benchmark_cycle.sh`, mas foca apenas em lifecycle:

- subir Spring
- subir Python (`legacy` ou `simple_py`)
- subir os dois
- subir worker Celery opcionalmente
- resetar banco
- refazer seed opcionalmente
- derrubar depois os processos iniciados pelo próprio script

## Local

```bash
bash scripts/orchestrator/manage_pocs.sh
```

## Subcomandos

### `up`

Sobe os serviços selecionados.

Exemplos:

```bash
# sobe Spring + simple_py
bash scripts/orchestrator/manage_pocs.sh up --variant simple_py --services both

# sobe apenas Python simple_py com 2 workers
bash scripts/orchestrator/manage_pocs.sh up --variant simple_py --services python --api-workers 2

# sobe Python legacy com worker Celery
bash scripts/orchestrator/manage_pocs.sh up --variant legacy --services python --worker true

# reseta banco e refaz seed antes de subir
bash scripts/orchestrator/manage_pocs.sh up \
  --variant simple_py \
  --services both \
  --reset-databases true \
  --reseed-data true \
  --non-interactive
```

Opções úteis:

- `--variant legacy|simple_py`
- `--services spring|python|both`
- `--worker true|false`
- `--api-workers N`
- `--celery-workers N`
- `--wait-ready true|false`
- `--reset-databases true|false`
- `--reset-targets spring,python`
- `--reseed-data true|false`
- `--reseed-targets spring,python`
- `--non-interactive`

Regras:

- `--worker true` exige `--services python` ou `--services both`
- `--reset-targets python` é resolvido para o banco da variante escolhida
- `--reseed-targets python` usa os scripts de seed da variante escolhida

## `down`

Derruba os processos registrados pelo último `up`.

Exemplos:

```bash
# derruba tudo que o manage_pocs.sh subiu
bash scripts/orchestrator/manage_pocs.sh down --services both

# derruba apenas Spring
bash scripts/orchestrator/manage_pocs.sh down --services spring

# derruba apenas a parte Python
bash scripts/orchestrator/manage_pocs.sh down --services python
```

Observação:

- o `down` só conhece os processos registrados em `tmp/manage_pocs/processes.tsv`
- ele não derruba serviços que tenham sido iniciados manualmente ou por outro script

## `reset-db`

Reseta banco sem subir serviço.

Exemplos:

```bash
# reseta apenas o banco da variante Python atual
bash scripts/orchestrator/manage_pocs.sh reset-db --variant simple_py --services python

# reseta Spring + Python da variante atual
bash scripts/orchestrator/manage_pocs.sh reset-db --variant legacy --services both --yes

# escolhe explicitamente os alvos
bash scripts/orchestrator/manage_pocs.sh reset-db --variant simple_py --reset-targets spring,python --yes
```

## `status`

Mostra o manifest atual e informa se cada PID ainda está ativo.

```bash
bash scripts/orchestrator/manage_pocs.sh status
```

## Arquivos de estado

O script salva estado em:

- `tmp/manage_pocs/processes.tsv`
- `tmp/manage_pocs/state.env`
- `tmp/manage_pocs/logs/`

Isso permite subir em um comando e derrubar depois em outro.
