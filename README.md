# JMeter Paridade Suite

Suíte JMeter para comparação de endpoints com paridade funcional entre:

- `poc-llm-ufc-simples` em `http://localhost:8080`
- `agentico_poc_fastapi` em `http://localhost:8000`

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

## Estrutura

- `planos/legacy`: planos históricos da API Python antiga (`/api/v1`, payloads em português)
- `planos/simple_py`: planos equivalentes adaptados para a PoC Python atual (`/courses`, `/modules`, `/lessons`, `/quiz`)
- `config/<variante>`: propriedades por variante
- `data/<variante>`: payloads e massa de leitura por variante
- `scripts/`: wrappers de execução e relatórios compartilhados
- `scripts/legacy/`: bootstrap, validação e utilitários da API Python legacy
- `scripts/simple_py/`: bootstrap e validação da PoC Python atual
- `scripts/spring/`: bootstrap da massa de leitura da API Spring
- `resultados/<variante>`: saída non-GUI e relatórios por variante

## Pré-requisitos

- JMeter 5.6+
- Java 17+
- Python 3.11+
- APIs Spring e Python rodando
- banco do Python inicializado
- pelo menos um `ADMIN` ativo no Python
- API Python com `LOAD_TEST_MODE=true`
- `LOAD_TEST_PROFESSOR_ID` apontando para um professor com massa compatível com `data/python_read_ids.csv`

## Ordem de execução

1. Garantir admin ativo no Python legacy usando [bootstrap_python_admin.md](./scripts/legacy/bootstrap_python_admin.md).
2. Confirmar o modo sem JWT no FastAPI:

```bash
LOAD_TEST_MODE=true
LOAD_TEST_PROFESSOR_ID=1
```

3. Executar para o legado:

```bash
python3 scripts/legacy/bootstrap_python_test_users.py
python3 scripts/spring/bootstrap_spring_read_data.py
python3 scripts/legacy/bootstrap_python_read_data.py
python3 scripts/legacy/validar_massa.py
```

Para a PoC Python atual (`simple_py`):

```bash
python3 scripts/spring/bootstrap_spring_read_data.py
python3 scripts/simple_py/bootstrap_python_read_data.py
python3 scripts/simple_py/validar_massa.py
```

4. Validar no GUI:

```bash
jmeter
```

Abrir `planos/legacy/paridade_smoke.jmx` ou `planos/simple_py/paridade_smoke.jmx`.

5. Executar non-GUI:

```bash
bash scripts/run_suite.sh legacy
bash scripts/run_suite.sh simple_py
```

6. Executar carga quando smoke e baselines estiverem estáveis:

```bash
bash scripts/run_load.sh legacy
bash scripts/run_load.sh simple_py
```

Para ajustar a carga:

```bash
LOAD_THREADS=50 LOAD_LOOPS=40 LOAD_RAMP_SECONDS=90 LOAD_DELAY_MS=25 bash scripts/run_load.sh simple_py
```

## Planos

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

- `python3 scripts/gerar_relatorio_variantes.py --variant legacy`
- `python3 scripts/gerar_relatorio_variantes.py --variant simple_py`

O relatório novo gera:

- `resultados/<variante>/relatorio/dashboard.html`
- `resultados/<variante>/relatorio/relatorio_resultados.md`
- `resultados/<variante>/relatorio/summary_by_label.csv`
- `resultados/<variante>/relatorio/comparison_spring_python.csv`

Cada dashboard agora explicita o objetivo de cada cenário antes de mostrar as métricas.
