# Bootstrap Manual do Admin Python Legacy

Este guia descreve o caminho manual para garantir um `ADMIN` ativo na variante `legacy`.

Use este material quando:

- você estiver preparando a variante `legacy` manualmente
- não quiser depender da orquestração completa
- o bootstrap automático do admin não for desejado ou não estiver disponível no ambiente

No fluxo atual com `run_benchmark_cycle.sh`, o seed da variante `legacy` já pode chamar `bootstrap_python_admin_insert.sh` automaticamente quando a rodada é configurada para refazer massa.

## Opção 1: usar um admin já existente

Se você já conhece um admin válido:

- e-mail: `admin@teste.com`
- senha: `Senha@123`

apenas ajuste `scripts/legacy/bootstrap_python_test_users.py` via ambiente:

```bash
export BOOTSTRAP_BASE_URL=http://localhost:8000
export BOOTSTRAP_ADMIN_EMAIL=admin@teste.com
export BOOTSTRAP_ADMIN_PASSWORD='Senha@123'
```

## Opção 2: criar manualmente no banco

Se não houver admin, use o script:

```bash
bash scripts/legacy/bootstrap_python_admin_insert.sh
```

O script usa, por padrão:

- usuário do banco: usuário logado no terminal (`$USER`)
- banco: `llm_ufc`
- host: `localhost`
- porta: `5432`
- e-mail admin: `admin@teste.com`
- senha admin: `Senha@123`

Ele gera um hash bcrypt compatível com o projeto e executa um `INSERT INTO usuarios ... ON CONFLICT (email) DO UPDATE` para deixar o admin ativo.

Se `DB_PASSWORD` ou `PGPASSWORD` já estiverem definidos no ambiente, o script reutiliza esse valor e não precisa perguntar a senha no terminal.

Se precisar sobrescrever algum valor:

```bash
DB_USER=postgres DB_NAME=llm_ufc BOOTSTRAP_ADMIN_EMAIL=admin@teste.com bash scripts/legacy/bootstrap_python_admin_insert.sh
```

Se o `python3` global não tiver o módulo `bcrypt`, aponte para um Python disponível dentro da própria suíte:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/legacy/bootstrap_python_admin_insert.sh
```

O jeito mais seguro é usar o mesmo padrão de senha já empregado nos testes do projeto Python.

## Validação

Depois de criar o admin, valide:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email_ou_usuario":"admin@teste.com","senha":"Senha@123"}'
```

O retorno esperado deve conter:

- `status = 200`
- `data.access_token`

Sem isso, os scripts de bootstrap da suíte não vão conseguir ativar professores na variante `legacy`.
