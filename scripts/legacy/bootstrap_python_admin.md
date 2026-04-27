# Bootstrap do Admin Python

O projeto Python exige um `ADMIN` ativo para ativar professores de benchmark, mas o código atual não garante seed automático.

Antes de rodar os scripts da suíte, garanta um admin ativo.

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

Ele pede a senha do usuário do banco no terminal, gera um hash bcrypt compatível com o projeto e executa um `INSERT INTO usuarios ... ON CONFLICT (email) DO UPDATE` para deixar o admin ativo.

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

Sem isso, os scripts de bootstrap da suíte não vão conseguir ativar professores.
