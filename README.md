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

- `planos/`: arquivos `.jmx`
- `config/`: propriedades do JMeter e dos ambientes
- `data/`: credenciais, payloads e IDs para leitura
- `scripts/`: bootstrap e validação
- `resultados/`: saída non-GUI

## Pré-requisitos

- JMeter 5.6+
- Java 17+
- Python 3.11+
- APIs Spring e Python rodando
- banco do Python inicializado
- pelo menos um `ADMIN` ativo no Python

## Ordem de execução

1. Garantir admin ativo no Python usando [bootstrap_python_admin.md](./scripts/bootstrap_python_admin.md).
2. Executar:

```bash
python3 scripts/bootstrap_python_test_users.py
python3 scripts/bootstrap_spring_read_data.py
python3 scripts/bootstrap_python_read_data.py
python3 scripts/validar_massa.py
```

3. Validar no GUI:

```bash
jmeter
```

Abrir `planos/paridade_smoke.jmx`.

4. Executar non-GUI:

```bash
bash scripts/run_all.sh
```

## Planos

- `paridade_smoke.jmx`: validação rápida
- `paridade_baseline_leitura.jmx`: leituras com massa pré-criada
- `paridade_baseline_escrita.jmx`: criações controladas
- `paridade_full_regressao.jmx`: mistura leitura e escrita

## Regras de benchmark

- Python faz login uma vez por thread, via `Once Only Controller`
- Spring não faz login
- IDs de leitura vêm dos CSVs gerados pelos scripts
- no Python, `python_read_ids.csv` mantém `email`, `senha` e IDs na mesma linha para cada thread usar token e recursos do mesmo professor
- escritas usam nomes únicos por thread e iteração
