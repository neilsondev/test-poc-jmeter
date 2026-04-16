# Planos JMeter da suite de paridade

Este diretorio contem os planos `.jmx` usados para comparar endpoints equivalentes entre a API Spring e a API Python.

A suite nao tenta medir todo o produto. O foco e validar paridade funcional e obter uma base de tempo de resposta para cursos, modulos, aulas e avaliacao manual.

## Como ler os nomes

Os nomes seguem a estrutura:

```text
paridade_<tipo_do_teste>_<escopo>.jmx
```

- `paridade`: indica que o plano compara comportamentos equivalentes entre Spring e Python.
- `smoke`: validacao minima, curta, para confirmar que ambiente, massa e autenticacao estao funcionando.
- `baseline`: medicao controlada de referencia. Serve para comparar resultados ao longo do tempo.
- `full_regressao`: execucao mais ampla, misturando partes de leitura e escrita para validar o conjunto principal.
- `leitura`: plano focado em operacoes `GET`, usando massa ja criada.
- `escrita`: plano focado em operacoes `POST`, criando recursos novos.

Os nomes dos Thread Groups tambem seguem uma convencao:

- `TG`: Thread Group.
- `SPRING` ou `PYTHON`: stack exercitada.
- `READ`, `WRITE` ou `SMOKE`: perfil de carga daquele grupo.

Exemplo: `TG_PYTHON_READ` significa "Thread Group da stack Python para fluxo de leitura".

## Desenho comum dos planos

Todos os planos usam variaveis de ambiente carregadas por `config/ambientes.properties`, como `SPRING_HOST`, `SPRING_PORT`, `PYTHON_HOST`, `PYTHON_PORT` e `PROTO`.

As regras de resposta sao simples e explicitas:

- leituras esperam HTTP `200`;
- criacoes esperam HTTP `201`;
- login Python espera HTTP `200`;
- erro de leitura usa `continue`, para registrar falhas sem parar o grupo inteiro;
- erro de escrita usa `stopthread`, porque um recurso criado costuma alimentar a proxima chamada do mesmo fluxo.

O Spring nao faz login nos planos atuais. O Python faz login porque seus endpoints exigem autenticacao. Para reduzir distorcao, o login Python fica dentro de `Once Only Controller`, ou seja, acontece uma vez por thread, nao a cada iteracao.

Nas leituras, ha um `ConstantTimer` de `100 ms` nos planos de baseline/regressao. Esse timer aplica uma cadencia minima entre requisicoes e evita que o teste vire apenas uma rajada sem pausa.

## Arquivos de massa usados

- `../data/spring_read_ids.csv`: IDs de curso, modulo e aula usados nos testes de leitura Spring.
- `../data/python_read_ids.csv`: credenciais e IDs usados nos testes de leitura Python. Cada linha mantem `email`, `senha`, `curso_id`, `modulo_id`, `aula_id` e `prova_modulo_id` juntos para preservar o vinculo entre token e dono dos recursos.
- `../data/professores_login.csv`: credenciais de professores para login nos fluxos Python de escrita.
- `../data/payload_cursos.csv`: partes variaveis do payload de cursos usados nos fluxos de criacao.

## `paridade_smoke.jmx`

**Objetivo:** validar rapidamente se as duas APIs estão de pé, se os CSVs de massa estão legíveis e se os endpoints básicos respondem com sucesso.

**Por que existe:** antes de executar baselines maiores, este plano detecta problemas simples de ambiente: porta errada, token Python inválido, massa inexistente, IDs quebrados ou endpoint indisponível.

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
2. Faz `POST /api/v1/auth/login`.
3. Extrai `$.data.access_token` para `ACCESS_TOKEN`.
4. Envia `Authorization: Bearer ${ACCESS_TOKEN}` nas chamadas seguintes.
5. Executa `GET /api/v1/cursos`.
6. Executa `GET /api/v1/cursos/${curso_id}`.
7. Executa `GET /api/v1/cursos/${curso_id}/modulos`.
8. Executa `GET /api/v1/modulos/${modulo_id}/aulas`.
9. Valida HTTP `200` em todas as chamadas.

**Como interpretar:** se o smoke falhar, os baselines não devem ser usados como comparação de performance. Primeiro corrija ambiente, login ou massa.

## `paridade_baseline_leitura.jmx`

**Objetivo:** medir uma linha de base para operações de leitura equivalentes entre Spring e Python.

**Por que existe:** leitura é o caminho mais estável para comparar tempo de resposta, porque usa massa pré-criada e evita custo de persistência de novos recursos.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Timer | Erro |
| --- | ---: | ---: | ---: | ---: | --- |
| `TG_SPRING_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_PYTHON_READ` | 10 | 20 | 20s | 100 ms | `continue` |

Cada grupo faz 10 threads x 20 iteracoes. Como o grupo Spring tem 7 samplers de leitura, ele gera ate 1400 amostras de leitura. O grupo Python tambem tem 7 samplers de leitura, mais o login uma vez por thread.

**Fluxo Spring:**

1. Le `spring_read_ids.csv`.
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
2. Mantem juntos `email`, `senha` e IDs da mesma linha.
3. Faz login uma vez por thread.
4. Executa:
   - `GET /api/v1/cursos`;
   - `GET /api/v1/cursos/${curso_id}`;
   - `GET /api/v1/cursos/${curso_id}/modulos`;
   - `GET /api/v1/cursos/${curso_id}/modulos/${modulo_id}`;
   - `GET /api/v1/modulos/${modulo_id}/aulas`;
   - `GET /api/v1/modulos/${modulo_id}/aulas/${aula_id}`;
   - `GET /api/v1/modulos/${prova_modulo_id}/prova`.
5. Valida HTTP `200`.

**Decisão importante de projeto:** o Python não usa um `CSVDataSet` simples neste baseline. O plano usa Groovy para selecionar a linha pelo número da thread e preservar o vínculo entre credencial e recursos. Isso evita um falso benchmark com `403`, que aconteceria se uma thread pegasse token de um professor e IDs pertencentes a outro.

**Como interpretar:** este é o plano principal para comparar p95/p99 de leitura. O login Python deve ser analisado separado dos endpoints de domínio.

## `paridade_baseline_escrita.jmx`

**Objetivo:** medir uma linha de base para criacao de recursos equivalentes entre Spring e Python.

**Por que existe:** escrita tem comportamento diferente de leitura porque envolve validacao, persistencia e encadeamento de IDs criados no proprio teste.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Erro |
| --- | ---: | ---: | ---: | --- |
| `TG_SPRING_WRITE` | 5 | 10 | 10s | `stopthread` |
| `TG_PYTHON_WRITE` | 5 | 10 | 10s | `stopthread` |

Cada grupo executa 5 threads x 10 iteracoes. Em cada iteracao, cria curso, modulo, aula e avaliacao. Isso gera ate 200 criacoes por stack.

**Fluxo Spring:**

1. Le `payload_cursos.csv`.
2. Cria curso com `POST /courses`.
3. Extrai `SPRING_COURSE_ID` de `$.dados.id`.
4. Cria modulo com `POST /courses/${SPRING_COURSE_ID}/modules`.
5. Extrai `SPRING_MODULE_ID`.
6. Cria aula com `POST /modules/${SPRING_MODULE_ID}/lessons`.
7. Extrai `SPRING_LESSON_ID`.
8. Cria avaliacao com `POST /modules/${SPRING_MODULE_ID}/quiz`.
9. Valida HTTP `201` em todas as criacoes.

**Fluxo Python:**

1. Le `professores_login.csv`.
2. Le `payload_cursos.csv`.
3. Faz login uma vez por thread.
4. Extrai `ACCESS_TOKEN`.
5. Cria curso com `POST /api/v1/cursos`.
6. Extrai `PY_CURSO_ID`.
7. Cria modulo com `POST /api/v1/cursos/${PY_CURSO_ID}/modulos`.
8. Extrai `PY_MODULO_ID`.
9. Cria aula com `POST /api/v1/modulos/${PY_MODULO_ID}/aulas`.
10. Extrai `PY_AULA_ID`.
11. Cria avaliacao manual com `POST /api/v1/modulos/${PY_MODULO_ID}/prova/manual`.
12. Valida HTTP `201` em todas as criacoes.

**Decisao importante de projeto:** os nomes dos recursos usam `${__threadNum}` e `${__counter(FALSE,)}` para evitar colisoes entre threads e iteracoes.

**Como interpretar:** este plano compara custo de criacao encadeada. Ele nao deve ser misturado diretamente com leitura, porque inclui escrita em banco e dependencia dos IDs extraidos nas etapas anteriores.

## `paridade_full_regressao.jmx`

**Objetivo:** executar uma regressao mais ampla, combinando leitura e escrita nas duas stacks.

**Por que existe:** depois que smoke e baselines isolados passam, este plano verifica se o conjunto principal continua funcional sob uma carga mista.

**Carga projetada:**

| Grupo | Threads | Loops | Ramp-up | Timer | Erro |
| --- | ---: | ---: | ---: | ---: | --- |
| `TG_SPRING_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_PYTHON_READ` | 10 | 20 | 20s | 100 ms | `continue` |
| `TG_SPRING_WRITE` | 5 | 5 | 10s | - | `stopthread` |
| `TG_PYTHON_WRITE` | 5 | 5 | 10s | - | `stopthread` |

**Fluxo de leitura Spring:**

1. Le `spring_read_ids.csv`.
2. Executa:
   - `GET /courses`;
   - `GET /courses/${course_id}`;
   - `GET /modules/${module_id}/quiz`.
3. Valida HTTP `200`.

**Fluxo de leitura Python:**

1. Seleciona dados de `python_read_ids.csv` via Groovy, mantendo credencial e IDs da mesma linha.
2. Faz login uma vez por thread.
3. Executa:
   - `GET /api/v1/cursos`;
   - `GET /api/v1/cursos/${curso_id}`;
   - `GET /api/v1/modulos/${prova_modulo_id}/prova`.
4. Valida HTTP `200`.

**Fluxo de escrita Spring:**

1. Cria curso com `POST /courses`.
2. Extrai `SPRING_COURSE_ID`.
3. Valida HTTP `201`.

**Fluxo de escrita Python:**

1. Le `professores_login.csv`.
2. Faz login uma vez por thread.
3. Cria curso com `POST /api/v1/cursos`.
4. Valida HTTP `201`.

**Decisao importante de projeto:** o plano de regressao nao repete todos os endpoints do baseline. Ele escolhe um subconjunto representativo para reduzir tempo de execucao e ainda cobrir lista, busca por ID, avaliacao e criacao de curso.

**Como interpretar:** este plano e bom para detectar regressao funcional e degradacao grosseira. Para conclusao fina de performance, use os baselines de leitura e escrita separados.

## Ordem recomendada de uso

1. Rode `paridade_smoke.jmx`.
2. Se o smoke passar, rode `paridade_baseline_leitura.jmx`.
3. Rode `paridade_baseline_escrita.jmx`.
4. Rode `paridade_full_regressao.jmx` para validar o conjunto misto.

O script `scripts/run_all.sh` executa essa ordem e grava os resultados em `resultados/<cenario>`.

## Como os resultados devem ser lidos

- Use `Erro` primeiro. Resultado com erro funcional nao deve ser tratado como benchmark confiavel.
- Compare Spring e Python por operacao equivalente, nao apenas pelo total do cenario.
- Separe login Python da comparacao dos endpoints de dominio.
- Prefira `p95` e `p99` para avaliar estabilidade. A media pode esconder picos.
- Em leitura, confira se o Python esta usando token e IDs da mesma linha de `python_read_ids.csv`.
- Em escrita, lembre que cada etapa depende da anterior. Uma falha de curso pode invalidar modulo, aula e avaliacao.

