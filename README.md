# JMeter Paridade Suite

Suíte JMeter para comparação de endpoints com paridade funcional entre:

- Spring Boot em `http://localhost:8080`
- FastAPI Python em `http://localhost:8000`

Escopo:

- cursos
- módulos
- aulas
- avaliação manual
- operações de leitura equivalentes

Fora de escopo:

- IA
- autenticação como benchmark principal
- admin
- matrícula

## Objetivo do repositório

Este repositório pode ser usado de duas formas:

1. Como suíte JMeter portátil, focada em executar planos, gravar `.jtl` e gerar relatórios.
2. Como parte de uma orquestração maior no workspace local, com bootstrap, validação de massa, reset de banco e subida de serviços.

## Estrutura

- `planos/legacy`: planos históricos da API Python antiga (`/api/v1`, payloads em português)
- `planos/simple_py`: planos equivalentes adaptados para a PoC Python atual (`/courses`, `/modules`, `/lessons`, `/quiz`)
- `config/<variante>`: propriedades por variante
- `data/<variante>`: payloads e massa de leitura por variante
- `scripts/`: wrappers de execução e relatórios compartilhados
- `scripts/legacy/`: bootstrap, validação e utilitários da API Python legacy
- `scripts/simple_py/`: bootstrap e validação da PoC Python atual
- `scripts/spring/`: bootstrap da massa de leitura da API Spring
- `scripts/orchestrator/`: helpers usados pela automação completa de benchmark
- `scripts/tools/`: utilitários auxiliares, como reset de banco
- `tools/metrics/`: coleta de métricas, consolidação de campanhas e simulação de p99
- `resultados/<variante>`: saída non-GUI e relatórios por variante
- `local/benchmark.env`: configuração local por máquina para a orquestração

## Modos de uso

### 1. Modo portátil

Use este modo quando:

- a máquina já tem os serviços em execução
- você só quer rodar os testes JMeter
- você quer levar a suíte para outro ambiente sem depender do mesmo esquema de pastas do workspace atual

Neste modo, o repositório depende apenas de:

- JMeter instalado
- Java disponível
- Python 3 para os scripts de relatório
- endpoints Spring e Python acessíveis
- massa de teste previamente preparada

Os entrypoints principais são:

- `bash scripts/run_suite.sh legacy`
- `bash scripts/run_suite.sh simple_py`
- `bash scripts/run_load.sh legacy`
- `bash scripts/run_load.sh simple_py`

### 2. Modo orquestrado

Use este modo quando:

- você quer automatizar bootstrap, validação, subida de serviços e ciclo completo de benchmark
- a máquina segue o mesmo padrão do workspace atual ou um layout compatível

Este modo hoje depende de scripts externos ao repositório e de um ambiente mais acoplado ao workspace local.

Observação:
- a suíte agora também possui um `run_benchmark_cycle.sh` e um `benchmark_env.sh` dentro do próprio repositório
- a configuração por máquina deve ficar em `local/benchmark.env`
- use `config/benchmark.env.example` como ponto de partida

## Pré-requisitos mínimos para executar os testes

### Para rodar apenas a suíte JMeter

- JMeter 5.6+
- Java 17+
- Python 3.11+
- API Spring disponível
- API Python disponível
- arquivos de massa compatíveis em `data/<variante>/`

### Para usar a automação completa do ciclo

Além dos itens acima:

- Bash
- `curl`
- `psql`
- `dropdb`
- `createdb`
- projetos Spring e Python disponíveis na máquina
- ambiente capaz de subir os serviços com os comandos esperados

Antes de usar a automação completa:

```bash
cp config/benchmark.env.example local/benchmark.env
```

Depois ajuste os caminhos dos projetos e, se necessário, os comandos de start.

Observação:
- a automação completa foi pensada principalmente para Linux ou WSL
- em Windows puro, o caminho mais simples é usar o modo portátil

## O que precisa estar pronto antes da execução

### Variante `legacy`

- banco Python inicializado
- pelo menos um `ADMIN` ativo no Python
- `LOAD_TEST_MODE=true`
- `LOAD_TEST_PROFESSOR_ID` apontando para um professor com massa compatível com `data/legacy/python_read_ids.csv`

### Variante `simple_py`

- banco Python inicializado
- massa de leitura gerada em `data/simple_py/python_read_ids.csv`
- endpoints `/courses`, `/modules`, `/lessons` e `/quiz` disponíveis

### Para ambas

- API Spring acessível
- massa de leitura do Spring gerada
- CSVs de payload presentes

## Preparação de massa

### Para o legado

Garantir admin ativo no Python legacy usando [bootstrap_python_admin.md](./scripts/legacy/bootstrap_python_admin.md).

Executar:

```bash
bash scripts/legacy/bootstrap_python_admin_insert.sh
python3 scripts/legacy/bootstrap_python_test_users.py
python3 scripts/spring/bootstrap_spring_read_data.py
python3 scripts/legacy/bootstrap_python_read_data.py
python3 scripts/legacy/validar_massa.py
```

### Para a PoC Python atual (`simple_py`)

Executar:

```bash
python3 scripts/spring/bootstrap_spring_read_data.py
python3 scripts/simple_py/bootstrap_python_read_data.py
python3 scripts/simple_py/validar_massa.py
```

## Execução dos testes

### Validar no GUI

```bash
jmeter
```

Abrir:

- `planos/legacy/paridade_smoke.jmx`
- `planos/simple_py/paridade_smoke.jmx`

### Executar a suíte non-GUI

```bash
bash scripts/run_suite.sh legacy
bash scripts/run_suite.sh simple_py
```

Para executar cenários específicos:

```bash
bash scripts/run_suite.sh simple_py --scenarios smoke,baseline_leitura
```

### Executar carga

Use quando smoke e baselines estiverem estáveis:

```bash
bash scripts/run_load.sh legacy
bash scripts/run_load.sh simple_py
```

Para ajustar a carga:

```bash
LOAD_THREADS=50 LOAD_LOOPS=40 LOAD_RAMP_SECONDS=90 LOAD_DELAY_MS=25 bash scripts/run_load.sh simple_py
```

### Executar o ciclo completo de benchmark

Quando quiser usar a orquestração completa da suíte:

```bash
bash run_benchmark_cycle.sh --variant simple_py --run-flow suite+load
```

Exemplo com label:

```bash
bash run_benchmark_cycle.sh --variant simple_py --run-flow suite+load --label suite-load-maio-2026
```

## Planos disponíveis

- `paridade_smoke.jmx`: validação rápida
- `paridade_baseline_leitura.jmx`: leituras com massa pré-criada
- `paridade_baseline_escrita.jmx`: criações controladas
- `paridade_full_regressao.jmx`: mistura leitura e escrita
- `paridade_load_sem_jwt.jmx`: carga mista histórica da variante `legacy`
- `paridade_load_simple_py.jmx`: carga mista da variante `simple_py`

## Regras de benchmark

- Na variante `legacy`, Python não faz login e não envia `Authorization`; os planos pressupõem `LOAD_TEST_MODE=true`
- Na variante `simple_py`, Python também não faz login, mas não depende de `LOAD_TEST_MODE`
- Spring não faz login
- IDs de leitura vêm dos CSVs gerados pelos scripts
- no legado, `LOAD_TEST_PROFESSOR_ID` deve conseguir acessar os IDs usados em `data/legacy/python_read_ids.csv`
- escritas usam nomes únicos por thread e iteração

## Relatórios

Para regenerar o relatório de uma variante:

```bash
python3 scripts/gerar_relatorio_variantes.py --variant legacy
python3 scripts/gerar_relatorio_variantes.py --variant simple_py
```

Para regenerar o relatório de uma pasta específica de resultados:

```bash
python3 scripts/gerar_relatorio_variantes.py --variant simple_py --results-dir /caminho/da/rodada
```

Os relatórios gerados são:

- `resultados/<variante>/relatorio/dashboard.html`
- `resultados/<variante>/relatorio/relatorio_resultados.md`
- `resultados/<variante>/relatorio/summary_by_label.csv`
- `resultados/<variante>/relatorio/comparison_spring_python.csv`

Cada dashboard explicita o objetivo de cada cenário antes de mostrar as métricas.

## Métricas e consolidação

As rodadas executadas pelo `run_benchmark_cycle.sh` podem gerar:

- `resultados/<variante>/<run_id>/metricas/metrics.csv`
- `resultados/<variante>/<run_id>/metricas/report.md`

Para consolidar várias rodadas da mesma campanha:

```bash
python3 tools/metrics/consolidate_benchmark_runs.py --label suite-load-maio-2026
```

Para estudar sensibilidade de `p99` sem alterar o `.jtl`:

```bash
python3 tools/metrics/simulate_p99_sensitivity.py --jtl /caminho/arquivo.jtl --label "Python Load Course List"
```

## Limitações atuais de portabilidade

Hoje, a suíte é mais portátil no modo de execução dos planos do que no modo de orquestração completa.

Os pontos que ainda dificultam levar a automação completa para outra máquina são:

- expectativa de projetos irmãos com nomes e caminhos específicos
- uso forte de Bash e ferramentas típicas de Linux
- dependência opcional de reset de banco e subida automatizada dos serviços

Se a meta for usar em Windows, a recomendação atual é:

1. subir Spring e Python separadamente
2. preparar a massa
3. usar `run_suite.sh`, `run_load.sh` e `gerar_relatorio_variantes.py`
