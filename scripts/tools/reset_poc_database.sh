#!/usr/bin/env bash
set -euo pipefail

SPRING_DB_NAME="${SPRING_DB_NAME:-poc_llm_simples}"
SPRING_DB_OWNER="${SPRING_DB_OWNER:-poc_user}"

PYTHON_LEGACY_DB_NAME="${PYTHON_LEGACY_DB_NAME:-${PYTHON_DB_NAME:-llm_ufc}}"
PYTHON_LEGACY_DB_OWNER="${PYTHON_LEGACY_DB_OWNER:-${PYTHON_DB_OWNER:-${USER}}}"

PYTHON_SIMPLE_DB_NAME="${PYTHON_SIMPLE_DB_NAME:-poc_llm_simple_py}"
PYTHON_SIMPLE_DB_OWNER="${PYTHON_SIMPLE_DB_OWNER:-poc_user}"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

DB_KEYS=("spring" "python_legacy" "python_simple")
DB_LABELS=(
  "Spring Boot Java"
  "FastAPI Python legacy"
  "FastAPI Python novo"
)
DB_NAMES=(
  "$SPRING_DB_NAME"
  "$PYTHON_LEGACY_DB_NAME"
  "$PYTHON_SIMPLE_DB_NAME"
)
DB_OWNERS=(
  "$SPRING_DB_OWNER"
  "$PYTHON_LEGACY_DB_OWNER"
  "$PYTHON_SIMPLE_DB_OWNER"
)

SELECTED_DB_NAMES=()
SELECTED_DB_OWNERS=()
SELECTED_DB_LABELS=()
SELECTED_DB_KEYS=()

CLI_MODE=0
AUTO_CONFIRM=0

usage() {
  cat <<'EOF'
Uso:
  bash scripts/tools/reset_poc_database.sh
  bash scripts/tools/reset_poc_database.sh --db spring --db python_legacy --yes

Opcoes:
  --db <chave>    Seleciona um banco. Pode ser repetido.
                  Chaves validas: spring, python_legacy, python_simple
  --yes           Pula a confirmacao interativa final.
  --help          Exibe esta ajuda.
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Erro: comando '$1' não encontrado no PATH." >&2
    exit 1
  fi
}

join_by() {
  local separator="$1"
  shift
  local first=1
  local item
  for item in "$@"; do
    if [[ $first -eq 1 ]]; then
      printf "%s" "$item"
      first=0
    else
      printf "%s%s" "$separator" "$item"
    fi
  done
}

db_index_for_key() {
  local key="$1"
  local i
  for i in "${!DB_KEYS[@]}"; do
    if [[ "${DB_KEYS[$i]}" == "$key" ]]; then
      echo "$i"
      return 0
    fi
  done
  return 1
}

append_db_by_index() {
  local index="$1"
  local existing_key

  for existing_key in "${SELECTED_DB_KEYS[@]}"; do
    if [[ "$existing_key" == "${DB_KEYS[$index]}" ]]; then
      return 0
    fi
  done

  SELECTED_DB_KEYS+=("${DB_KEYS[$index]}")
  SELECTED_DB_LABELS+=("${DB_LABELS[$index]}")
  SELECTED_DB_NAMES+=("${DB_NAMES[$index]}")
  SELECTED_DB_OWNERS+=("${DB_OWNERS[$index]}")
}

pick_databases() {
  echo "Escolha quais bancos deseja deletar e recriar:"
  echo
  local i
  for i in "${!DB_KEYS[@]}"; do
    printf "  %d) %-22s - %s owner=%s\n" \
      "$((i + 1))" \
      "${DB_LABELS[$i]}" \
      "${DB_NAMES[$i]}" \
      "${DB_OWNERS[$i]}"
  done
  echo
  read -r -p "Digite os números separados por espaço ou vírgula (ex.: 1 3): " raw_choices

  local normalized_choices
  normalized_choices="${raw_choices//,/ }"

  if [[ -z "${normalized_choices// }" ]]; then
    echo "Nenhuma opção informada."
    exit 1
  fi

  local -a seen=()
  local choice index found seen_index
  for choice in $normalized_choices; do
    if [[ ! "$choice" =~ ^[1-3]$ ]]; then
      echo "Opção inválida: '$choice'."
      exit 1
    fi

    index=$((choice - 1))
    found=0
    for seen_index in "${seen[@]}"; do
      if [[ "$seen_index" -eq "$index" ]]; then
        found=1
        break
      fi
    done

    if [[ "$found" -eq 0 ]]; then
      seen+=("$index")
      append_db_by_index "$index"
    fi
  done
}

pick_databases_from_cli() {
  if [[ "${#SELECTED_DB_KEYS[@]}" -eq 0 ]]; then
    echo "Erro: nenhum banco foi selecionado via --db." >&2
    exit 1
  fi
}

confirm_databases() {
  local confirmation_target
  confirmation_target="$(join_by "," "${SELECTED_DB_NAMES[@]}")"

  echo
  echo "ATENÇÃO: esta ação vai apagar todos os dados dos bancos selecionados."
  echo "Host: ${POSTGRES_HOST}"
  echo "Porta: ${POSTGRES_PORT}"
  echo

  local i
  for i in "${!SELECTED_DB_NAMES[@]}"; do
    printf "  - %s: %s owner=%s\n" \
      "${SELECTED_DB_LABELS[$i]}" \
      "${SELECTED_DB_NAMES[$i]}" \
      "${SELECTED_DB_OWNERS[$i]}"
  done

  if [[ "$AUTO_CONFIRM" -eq 1 ]]; then
    echo
    echo "Confirmacao automatica habilitada por --yes."
    return 0
  fi

  echo
  read -r -p "Para confirmar, digite exatamente: ${confirmation_target} " confirmation

  if [[ "$confirmation" != "$confirmation_target" ]]; then
    echo "Confirmação incorreta. Operação cancelada."
    exit 1
  fi
}

reset_database() {
  local db_name="$1"
  local db_owner="$2"

  echo
  echo "Encerrando conexões ativas em '${db_name}'..."
  psql \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --dbname postgres \
    --command "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${db_name}' AND pid <> pg_backend_pid();" \
    >/dev/null

  echo "Apagando banco '${db_name}'..."
  dropdb \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --if-exists \
    "$db_name"

  echo "Recriando banco '${db_name}'..."
  createdb \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --owner "$db_owner" \
    "$db_name"

  echo
  echo "Banco '${db_name}' recriado com sucesso."
}

parse_args() {
  local db_key index

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --db)
        CLI_MODE=1
        if [[ $# -lt 2 ]]; then
          echo "Erro: --db exige uma chave." >&2
          exit 1
        fi
        db_key="$2"
        if ! index="$(db_index_for_key "$db_key")"; then
          echo "Erro: chave de banco invalida '$db_key'." >&2
          exit 1
        fi
        append_db_by_index "$index"
        shift 2
        ;;
      --yes)
        AUTO_CONFIRM=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Erro: argumento desconhecido '$1'." >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

main() {
  require_command psql
  require_command dropdb
  require_command createdb

  parse_args "$@"

  if [[ "$CLI_MODE" -eq 1 ]]; then
    pick_databases_from_cli
  else
    pick_databases
  fi

  confirm_databases

  local i
  for i in "${!SELECTED_DB_NAMES[@]}"; do
    reset_database "${SELECTED_DB_NAMES[$i]}" "${SELECTED_DB_OWNERS[$i]}"
  done
}

main "$@"
