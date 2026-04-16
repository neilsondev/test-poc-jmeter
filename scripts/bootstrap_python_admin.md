# Bootstrap do Admin Python

O projeto Python exige um `ADMIN` ativo para ativar professores de benchmark, mas o código atual não garante seed automático.

Antes de rodar os scripts da suíte, garanta um admin ativo.

## Opção 1: usar um admin já existente

Se você já conhece um admin válido:

- e-mail: `admin@teste.com`
- senha: `Senha@123`

apenas ajuste `scripts/bootstrap_python_test_users.py` via ambiente:

```bash
export BOOTSTRAP_BASE_URL=http://localhost:8000
export BOOTSTRAP_ADMIN_EMAIL=admin@teste.com
export BOOTSTRAP_ADMIN_PASSWORD='Senha@123'
```

## Opção 2: criar manualmente no banco

Se não houver admin, crie um registro com:

- `perfil = ADMIN`
- `status = ATIVO`
- senha com hash bcrypt compatível com o projeto

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
