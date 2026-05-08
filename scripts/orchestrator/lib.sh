#!/usr/bin/env bash

timestamp_now() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

human_timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log_line() {
  local level="$1"
  shift
  local message="$*"
  local line="[$(human_timestamp)] [$level] $message"
  echo "$line" >&2
  if [[ -n "${ORCHESTRATOR_LOG:-}" ]]; then
    echo "$line" >>"$ORCHESTRATOR_LOG"
  fi
}

log_info() {
  log_line INFO "$@"
}

log_warn() {
  log_line WARN "$@"
}

log_error() {
  log_line ERROR "$@"
}

die() {
  log_error "$@"
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Comando obrigatorio nao encontrado: $1"
  fi
}

require_dir() {
  if [[ ! -d "$1" ]]; then
    die "Diretorio obrigatorio nao encontrado: $1"
  fi
}

require_file() {
  if [[ ! -f "$1" ]]; then
    die "Arquivo obrigatorio nao encontrado: $1"
  fi
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|Yes|y|Y|on|ON|On)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

normalize_bool() {
  if is_true "${1:-}"; then
    echo "true"
  else
    echo "false"
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

trim() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf "%s" "$value"
}

load_dotenv_file() {
  local path="${1:-.env}"
  local line key value
  [[ -f "$path" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$(trim "$line")" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue

    key="$(trim "${line%%=*}")"
    value="${line#*=}"
    value="${value%$'\r'}"

    if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done <"$path"
}

csv_contains() {
  local csv="${1:-}"
  local needle="${2:-}"
  local item
  IFS=',' read -r -a __csv_items <<<"$csv"
  for item in "${__csv_items[@]}"; do
    item="$(trim "$item")"
    if [[ "$item" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

sanitize_slug() {
  local value="${1:-}"
  value="$(printf "%s" "$value" | tr '[:upper:]' '[:lower:]')"
  value="$(printf "%s" "$value" | tr -cs 'a-z0-9._-' '-')"
  value="${value#-}"
  value="${value%-}"
  printf "%s" "${value:-run}"
}

json_array_from_csv() {
  local csv="${1:-}"
  local item
  local out=()
  IFS=',' read -r -a __json_items <<<"$csv"
  for item in "${__json_items[@]}"; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    out+=("\"$item\"")
  done
  if [[ "${#out[@]}" -eq 0 ]]; then
    printf "[]"
  else
    printf "[%s]" "$(join_by ", " "${out[@]}")"
  fi
}
