#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-llm_ufc}"
DB_USER="${DB_USER:-${USER}}"

ADMIN_NAME="${BOOTSTRAP_ADMIN_NAME:-Admin Teste}"
ADMIN_CPF="${BOOTSTRAP_ADMIN_CPF:-000.000.000-00}"
ADMIN_EMAIL="${BOOTSTRAP_ADMIN_EMAIL:-admin@teste.com}"
ADMIN_PASSWORD="${BOOTSTRAP_ADMIN_PASSWORD:-Senha@123}"

if ! command -v psql >/dev/null 2>&1; then
  echo "Erro: psql nao encontrado no PATH." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if [[ -z "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c 'import bcrypt' >/dev/null 2>&1; then
  echo "Erro: nao encontrei um Python com o modulo bcrypt." >&2
  echo "Instale as dependencias da suite ou defina PYTHON_BIN para um Python disponivel dentro deste projeto." >&2
  exit 1
fi

read -r -s -p "Senha do banco para ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}: " DB_PASSWORD
echo

PASSWORD_HASH="$(
  ADMIN_PASSWORD="$ADMIN_PASSWORD" "$PYTHON_BIN" -c 'import os, bcrypt; print(bcrypt.hashpw(os.environ["ADMIN_PASSWORD"].encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8"))'
)"

PGPASSWORD="$DB_PASSWORD" psql \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  --set ON_ERROR_STOP=1 \
  --set admin_name="$ADMIN_NAME" \
  --set admin_cpf="$ADMIN_CPF" \
  --set admin_email="$ADMIN_EMAIL" \
  --set password_hash="$PASSWORD_HASH" <<'SQL'
INSERT INTO usuarios (
  nome,
  cpf,
  email,
  senha,
  perfil,
  status,
  foto_perfil,
  criado_em
)
VALUES (
  :'admin_name',
  :'admin_cpf',
  :'admin_email',
  :'password_hash',
  'ADMIN',
  'ATIVO',
  NULL,
  NOW()
)
ON CONFLICT (email) DO UPDATE SET
  nome = EXCLUDED.nome,
  cpf = EXCLUDED.cpf,
  senha = EXCLUDED.senha,
  perfil = 'ADMIN',
  status = 'ATIVO';
SQL

echo "Admin ativo em ${ADMIN_EMAIL}."
