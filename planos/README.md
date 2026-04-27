# Planos JMeter da suíte de paridade

## Variantes

A suíte agora possui duas variantes em paralelo:

- `legacy/`: mantém os planos históricos voltados para a API Python antiga com `/api/v1`.
- `simple_py/`: adapta o mesmo desenho de testes para a PoC Python atual usada na collection Postman simples.

Os nomes dos cenários permanecem equivalentes entre as variantes. A diferença está no contrato Python exercitado e na massa utilizada.

Este diretório contém os planos `.jmx` usados para comparar endpoints equivalentes entre a API Spring e a API Python.

A suíte não tenta medir todo o produto. O foco é validar paridade funcional e obter uma base de tempo de resposta para cursos, módulos, aulas e avaliação manual.

## Como ler os nomes

Os nomes seguem a estrutura:

```text
paridade_<tipo_do_teste>_<escopo>.jmx
```

- `paridade`: indica que o plano compara comportamentos equivalentes entre Spring e Python.
- `smoke`: validação mínima, curta, para confirmar que ambiente, massa e endpoints estão funcionando.
- `baseline`: medição controlada de referência. Serve para comparar resultados ao longo do tempo.
- `full_regressao`: execução mais ampla, misturando partes de leitura e escrita para validar o conjunto principal.
- `load`: carga mista parametrizável, sem JWT no Python.
- `leitura`: plano focado em operações `GET`, usando massa já criada.
- `escrita`: plano focado em operações `POST`, criando recursos novos.

Os nomes dos Thread Groups também seguem uma convenção:

- `TG`: Thread Group.
- `SPRING` ou `PYTHON`: stack exercitada.
- `READ`, `WRITE` ou `SMOKE`: perfil de carga daquele grupo.

Exemplo: `TG_PYTHON_READ` significa "Thread Group da stack Python para fluxo de leitura".

## Desenho comum dos planos

Todos os planos usam variáveis de ambiente carregadas por `config/ambientes.properties`, como `SPRING_HOST`, `SPRING_PORT`, `PYTHON_HOST`, `PYTHON_PORT` e `PROTO`.

Os fluxos Python pressupõem a API FastAPI em modo sem JWT:

```bash
LOAD_TEST_MODE=true
LOAD_TEST_PROFESSOR_ID=1
```

Nenhum plano Python faz `POST /api/v1/auth/login`, extrai token ou envia header `Authorization`. O professor definido em `LOAD_TEST_PROFESSOR_ID` precisa existir e ter acesso à massa usada em `data/python_read_ids.csv`.

As regras de resposta são simples e explicitas:

- leituras esperam HTTP `200`;
- criações esperam HTTP `201`;
- erro de leitura usa `continue`, para registrar falhas sem parar o grupo inteiro;
- erro de escrita usa `stopthread`, porque um recurso criado costuma alimentar a próxima chamada do mesmo fluxo.

O Spring não faz login. O Python também não faz login nos planos atuais; a validação de JWT deve estar desabilitada no FastAPI durante estas execuções.

Nas leituras, há um `ConstantTimer` de `100 ms` nos planos de baseline/regressão. Esse timer aplica uma cadência mínima entre requisições e evita que o teste vire apenas uma rajada sem pausa.

## Arquivos de massa usados

- `../data/spring_read_ids.csv`: IDs de curso, modulo e aula usados nos testes de leitura Spring.
- `../data/python_read_ids.csv`: IDs usados nos testes de leitura Python. O arquivo ainda possui colunas de credenciais por compatibilidade com scripts, mas os planos sem JWT usam os IDs.
- `../data/professores_login.csv`: credenciais usadas pelos scripts de bootstrap, não pelos planos JMeter sem JWT.
- `../data/payload_cursos.csv`: partes variáveis do payload de cursos usados nos fluxos de criação.

## `paridade_smoke.jmx`

**Objetivo:** validar rapidamente se as duas APIs estão de pé, se os CSVs de massa estão legíveis e se os endpoints básicos respondem com sucesso.

**Por que existe:** antes de executar baselines maiores, este plano detecta problemas simples de ambiente: porta errada, `LOAD_TEST_MODE` desligado, massa inexistente, IDs quebrados ou endpoint indisponível.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Erro |
| --- | ---: | ---: | ---: | --- |
| `TG_SPRING_SMOKE` | 1 | 1 | 1s | `stopthread` |
| `TG_PYTHON_SMOKE` | 1 | 1 | 1s | `stopthread` |

**Fluxo Spring:**

1. Le `spring_read_ids.csv`.
2. Executa `GET /courses`.
3. Executa `GET /courses/${course_id}`.
4. Executa `GET /courses/${course_id}/modules`.
5. Executa `GET /modules/${module_id}/lessons`.
6. Valida HTTP `200` em todas as chamadas.

**Fluxo Python:**

1. Lê `python_read_ids.csv`.
2. Executa `GET /api/v1/cursos`.
3. Executa `GET /api/v1/cursos/${curso_id}`.
4. Executa `GET /api/v1/cursos/${curso_id}/modulos`.
5. Executa `GET /api/v1/modulos/${modulo_id}/aulas`.
6. Valida HTTP `200` em todas as chamadas.

**Como interpretar:** se o smoke falhar, os baselines não devem ser usados como comparação de performance. Primeiro corrija ambiente, `LOAD_TEST_MODE`, `LOAD_TEST_PROFESSOR_ID` ou massa.

## `paridade_baseline_leitura.jmx`

**Objetivo:** medir uma linha de base para operações de leitura equivalentes entre Spring e Python.

**Por que existe:** leitura é o caminho mais estável para comparar tempo de resposta, porque usa massa pré-criada e evita custo de persistência de novos recursos.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Timer | Erro |
| --- | ---: | ---: | ---: | ---: | --- |
| `TG_SPRING_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_PYTHON_READ` | 10 | 20 | 20s | 100 ms | `continue` |

Cada grupo faz 10 threads x 20 iterações. Como o grupo Spring tem 7 samplers de leitura, ele gera até 1400 amostras de leitura. O grupo Python também tem 7 samplers de leitura, sem amostras de login.

**Fluxo Spring:**

1. Lê `spring_read_ids.csv`.
2. Executa:
   - `GET /courses`;
   - `GET /courses/${course_id}`;
   - `GET /courses/${course_id}/modules`;
   - `GET /modules/${module_id}`;
   - `GET /modules/${module_id}/lessons`;
   - `GET /lessons/${lesson_id}`;
   - `GET /modules/${module_id}/quiz`.
3. Valida HTTP `200`.

**Fluxo Python:**

1. Usa um `JSR223Sampler` em Groovy para selecionar uma linha de `python_read_ids.csv` por thread.
2. Mantém juntos os IDs da mesma linha.
3. Executa:
   - `GET /api/v1/cursos`;
   - `GET /api/v1/cursos/${curso_id}`;
   - `GET /api/v1/cursos/${curso_id}/modulos`;
   - `GET /api/v1/cursos/${curso_id}/modulos/${modulo_id}`;
   - `GET /api/v1/modulos/${modulo_id}/aulas`;
   - `GET /api/v1/modulos/${modulo_id}/aulas/${aula_id}`;
   - `GET /api/v1/modulos/${prova_modulo_id}/prova`.
4. Valida HTTP `200`.

**Decisão importante de projeto:** o Python não usa um `CSVDataSet` simples neste baseline. O plano usa Groovy para selecionar a linha pelo número da thread e manter os IDs relacionados entre si. Em modo sem JWT, a identidade real vem de `LOAD_TEST_PROFESSOR_ID`; por isso este professor precisa ser compatível com a massa.

**Como interpretar:** este é o plano principal para comparar p95/p99 de leitura sem custo de JWT no Python.

## `paridade_baseline_escrita.jmx`

**Objetivo:** medir uma linha de base para criacao de recursos equivalentes entre Spring e Python.

**Por que existe:** escrita tem comportamento diferente de leitura porque envolve validacao, persistencia e encadeamento de IDs criados no proprio teste.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Erro |
| --- | ---: | ---: | ---: | --- |
| `TG_SPRING_WRITE` | 5 | 10 | 10s | `stopthread` |
| `TG_PYTHON_WRITE` | 5 | 10 | 10s | `stopthread` |

Cada grupo executa 5 threads x 10 iterações. Em cada iteração, cria curso, modulo, aula e avaliação. Isso gera até 200 criações por stack.

**Fluxo Spring:**

1. Lê `payload_cursos.csv`.
2. Cria curso com `POST /courses`.
3. Extrai `SPRING_COURSE_ID` de `$.dados.id`.
4. Cria modulo com `POST /courses/${SPRING_COURSE_ID}/modules`.
5. Extrai `SPRING_MODULE_ID`.
6. Cria aula com `POST /modules/${SPRING_MODULE_ID}/lessons`.
7. Extrai `SPRING_LESSON_ID`.
8. Cria avaliacao com `POST /modules/${SPRING_MODULE_ID}/quiz`.
9. Valida HTTP `201` em todas as criacoes.

**Fluxo Python:**

1. Lê `payload_cursos.csv`.
2. Cria curso com `POST /api/v1/cursos`.
3. Extrai `PY_CURSO_ID`.
4. Cria modulo com `POST /api/v1/cursos/${PY_CURSO_ID}/modulos`.
5. Extrai `PY_MODULO_ID`.
6. Cria aula com `POST /api/v1/modulos/${PY_MODULO_ID}/aulas`.
7. Extrai `PY_AULA_ID`.
8. Cria avaliação manual com `POST /api/v1/modulos/${PY_MODULO_ID}/prova/manual`.
9. Valida HTTP `201` em todas as criações.

**Decisão importante de projeto:** os nomes dos recursos usam `${__threadNum}` e `${__counter(FALSE,)}` para evitar colisões entre threads e iterações.

**Como interpretar:** este plano compara custo de criação encadeada. Ele não deve ser misturado diretamente com leitura, porque inclui escrita em banco e dependência dos IDs extraídos nas etapas anteriores.

## `paridade_full_regressao.jmx`

**Objetivo:** executar uma regressão mais ampla, combinando leitura e escrita nas duas stacks.

**Por que existe:** depois que smoke e baselines isolados passam, este plano verifica se o conjunto principal continua funcional sob uma carga mista.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Timer | Erro |
| --- | ---: | ---: | ---: | ---: | --- |
| `TG_SPRING_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_PYTHON_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_SPRING_WRITE` | 5 | 5 | 10s | - | `stopthread` |
| `TG_PYTHON_WRITE` | 5 | 5 | 10s | - | `stopthread` |

**Fluxo de leitura Spring:**

1. Lê `spring_read_ids.csv`.
2. Executa:
   - `GET /courses`;
   - `GET /courses/${course_id}`;
   - `GET /modules/${module_id}/quiz`.
3. Valida HTTP `200`.

**Fluxo de leitura Python:**

1. Seleciona dados de `python_read_ids.csv` via Groovy, mantendo IDs da mesma linha.
2. Executa:
   - `GET /api/v1/cursos`;
   - `GET /api/v1/cursos/${curso_id}`;
   - `GET /api/v1/modulos/${prova_modulo_id}/prova`.
3. Valida HTTP `200`.

**Fluxo de escrita Spring:**

1. Cria curso com `POST /courses`.
2. Extrai `SPRING_COURSE_ID`.
3. Valida HTTP `201`.

**Fluxo de escrita Python:**

1. Cria curso com `POST /api/v1/cursos`.
2. Valida HTTP `201`.

**Decisão importante de projeto:** o plano de regressão não repete todos os endpoints do baseline. Ele escolhe um subconjunto representativo para reduzir tempo de execução e ainda cobrir lista, busca por ID, avaliação e criação de curso.

**Como interpretar:** este plano é bom para detectar regressão funcional e degradação grosseira. Para conclusão fina de performance, use os baselines de leitura e escrita separados.

## `paridade_load_sem_jwt.jmx`

**Objetivo:** aplicar carga mista nas duas PoCs sem medir validacao JWT no Python.

**Carga padrao:**

| Grupo | Threads | Loops | Ramp-up | Timer | Erro |
| --- | ---: | ---: | ---: | ---: | --- |
| `TG_SPRING_LOAD_MIXED` | 30 | 30 | 60s | 50 ms | `continue` |
| `TG_PYTHON_LOAD_MIXED` | 30 | 30 | 60s | 50 ms | `continue` |

Cada iteração executa quatro leituras e uma criação de curso. Isso mantém a carga majoritariamente de leitura, mas inclui escrita suficiente para exercitar banco e serialização.

**Parâmetros ajustáveis:**

```bash
LOAD_THREADS=50 LOAD_LOOPS=40 LOAD_RAMP_SECONDS=90 LOAD_DELAY_MS=25 bash scripts/run_load.sh legacy
```

**Fluxo Python:** seleciona IDs de `python_read_ids.csv`, executa `GET /api/v1/cursos`, `GET /api/v1/cursos/${curso_id}`, `GET /api/v1/cursos/${curso_id}/modulos`, `GET /api/v1/modulos/${modulo_id}/aulas` e cria curso com `POST /api/v1/cursos`, sem login e sem header `Authorization`.

## Ordem recomendada de uso

1. Rode `paridade_smoke.jmx`.
2. Se o smoke passar, rode `paridade_baseline_leitura.jmx`.
3. Rode `paridade_baseline_escrita.jmx`.
4. Rode `paridade_full_regressao.jmx` para validar o conjunto misto.
5. Rode `paridade_load_sem_jwt.jmx` para carga mista sem JWT.

O script `scripts/run_all.sh` executa smoke, baselines e regressão da variante `legacy`, gravando os resultados em `resultados/<variante>/<cenario>`. O plano de carga é executado separadamente por `scripts/run_load.sh <variante>`.

## Como os resultados devem ser lidos

- Use `Erro` primeiro. Resultado com erro funcional não deve ser tratado como benchmark confiável.
- Compare Spring e Python por operação equivalente, não apenas pelo total do cenário.
- Confirme que não há amostras de login Python; os planos atuais medem os endpoints de domínio sem JWT.
- Prefira `p95` e `p99` para avaliar estabilidade. A média pode esconder picos.
- Em leitura, confira se `LOAD_TEST_PROFESSOR_ID` consegue acessar os IDs de `python_read_ids.csv`.
- Em escrita, lembre que cada etapa depende da anterior. Uma falha de curso pode invalidar modulo, aula e avaliação.
