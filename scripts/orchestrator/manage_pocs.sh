#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SUITE_ROOT/benchmark_env.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/lib.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/process_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/prompt_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/bootstrap_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/spring_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/python_utils.sh"

STATE_DIR="${JMETER_SUITE_DIR}/tmp/manage_pocs"
LOGS_DIR="${STATE_DIR}/logs"
PROCESS_MANIFEST_PATH="${STATE_DIR}/processes.tsv"
STATE_FILE_PATH="${STATE_DIR}/state.env"

COMMAND="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

VARIANT="${VARIANT:-simple_py}"
SERVICES="${SERVICES:-both}"
API_WORKERS="${API_WORKERS:-$DEFAULT_API_WORKERS}"
CELERY_WORKERS="${CELERY_WORKERS:-$DEFAULT_CELERY_WORKERS}"
START_WORKER="${START_WORKER:-false}"
WAIT_READY="${WAIT_READY:-true}"
RESET_DATABASES="${RESET_DATABASES:-false}"
RESEED_DATA="${RESEED_DATA:-false}"
RESET_TARGETS="${RESET_TARGETS:-}"
RESEED_TARGETS="${RESEED_TARGETS:-}"
NON_INTERACTIVE="${NON_INTERACTIVE:-false}"

START_SPRING="false"
START_PYTHON="false"
PYTHON_BASE_URL=""
ORCHESTRATOR_LOG=""
RUN_RESULTS_DIR=""
UP_START_COMPLETED="false"

usage() {
  cat <<'EOF'
Uso:
  bash scripts/orchestrator/manage_pocs.sh <comando> [opcoes]

Comandos:
  up         Sobe Spring, Python ou ambos, com reset/seed opcionais.
  down       Derruba processos iniciados pelo manage_pocs.sh.
  reset-db   Reseta bancos sem subir servicos.
  status     Mostra o estado do manifest de processos.
  help       Exibe esta ajuda.

Opcoes comuns:
  --variant legacy|simple_py
  --services spring|python|both
  --non-interactive

Opcoes do comando up:
  --worker true|false
  --api-workers N
  --celery-workers N
  --wait-ready true|false
  --reset-databases true|false
  --reset-targets spring,python
  --reseed-data true|false
  --reseed-targets spring,python

Opcoes do comando reset-db:
  --reset-targets spring,python
  --yes

Opcoes do comando down:
  --services spring|python|both
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --variant)
        VARIANT="${2:-}"
        shift 2
        ;;
      --services)
        SERVICES="${2:-}"
        shift 2
        ;;
      --worker)
        START_WORKER="${2:-}"
        shift 2
        ;;
      --api-workers)
        API_WORKERS="${2:-}"
        shift 2
        ;;
      --celery-workers)
        CELERY_WORKERS="${2:-}"
        shift 2
        ;;
      --wait-ready)
        WAIT_READY="${2:-}"
        shift 2
        ;;
      --reset-databases)
        RESET_DATABASES="${2:-}"
        shift 2
        ;;
      --reset-targets)
        RESET_TARGETS="${2:-}"
        shift 2
        ;;
      --reseed-data)
        RESEED_DATA="${2:-}"
        shift 2
        ;;
      --reseed-targets)
        RESEED_TARGETS="${2:-}"
        shift 2
        ;;
      --non-interactive|--yes)
        NON_INTERACTIVE="true"
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        die "Argumento desconhecido: $1"
        ;;
    esac
  done
}

validate_common_inputs() {
  case "$VARIANT" in
    legacy|simple_py)
      ;;
    *)
      die "Variante invalida: $VARIANT"
      ;;
  esac

  case "$SERVICES" in
    spring|python|both)
      ;;
    *)
      die "Services invalido: $SERVICES"
      ;;
  esac

  [[ "$API_WORKERS" =~ ^[0-9]+$ ]] || die "API_WORKERS invalido: $API_WORKERS"
  [[ "$CELERY_WORKERS" =~ ^[0-9]+$ ]] || die "CELERY_WORKERS invalido: $CELERY_WORKERS"
  normalize_bool "$WAIT_READY" >/dev/null
  normalize_bool "$RESET_DATABASES" >/dev/null
  normalize_bool "$RESEED_DATA" >/dev/null
  normalize_bool "$START_WORKER" >/dev/null
}

ensure_state_dirs() {
  mkdir -p "$STATE_DIR" "$LOGS_DIR"
}

configure_service_switches() {
  case "$SERVICES" in
    spring)
      START_SPRING="true"
      START_PYTHON="false"
      ;;
    python)
      START_SPRING="false"
      START_PYTHON="true"
      ;;
    both)
      START_SPRING="true"
      START_PYTHON="true"
      ;;
  esac

  if is_true "$START_WORKER" && ! is_true "$START_PYTHON"; then
    die "Worker exige --services python ou --services both."
  fi
}

map_reset_target_token() {
  local token="$1"
  case "$token" in
    spring)
      printf "spring"
      ;;
    python)
      resolve_python_db_key
      ;;
    python_legacy|python_simple)
      printf "%s" "$token"
      ;;
    both)
      printf "spring,%s" "$(resolve_python_db_key)"
      ;;
    *)
      die "Reset target invalido: $token"
      ;;
  esac
}

map_reseed_target_token() {
  local token="$1"
  case "$token" in
    spring|python)
      printf "%s" "$token"
      ;;
    both)
      printf "spring,python"
      ;;
    *)
      die "Reseed target invalido: $token"
      ;;
  esac
}

normalize_target_csv() {
  local raw_csv="$1"
  local mapper="$2"
  local -a normalized=()
  local token mapped subtoken existing found

  IFS=',' read -r -a __items <<<"$raw_csv"
  for token in "${__items[@]}"; do
    token="$(trim "$token")"
    [[ -z "$token" ]] && continue
    mapped="$($mapper "$token")"
    IFS=',' read -r -a __mapped_parts <<<"$mapped"
    for subtoken in "${__mapped_parts[@]}"; do
      subtoken="$(trim "$subtoken")"
      [[ -z "$subtoken" ]] && continue
      found=0
      for existing in "${normalized[@]}"; do
        if [[ "$existing" == "$subtoken" ]]; then
          found=1
          break
        fi
      done
      if [[ $found -eq 0 ]]; then
        normalized+=("$subtoken")
      fi
    done
  done

  join_by "," "${normalized[@]}"
}

resolve_default_targets() {
  if [[ -z "$RESET_TARGETS" ]] && is_true "$RESET_DATABASES"; then
    case "$SERVICES" in
      spring)
        RESET_TARGETS="spring"
        ;;
      python)
        RESET_TARGETS="python"
        ;;
      both)
        RESET_TARGETS="spring,python"
        ;;
    esac
  fi

  if [[ -z "$RESEED_TARGETS" ]] && is_true "$RESEED_DATA"; then
    case "$SERVICES" in
      spring)
        RESEED_TARGETS="spring"
        ;;
      python)
        RESEED_TARGETS="python"
        ;;
      both)
        RESEED_TARGETS="spring,python"
        ;;
    esac
  fi

  if [[ -n "$RESET_TARGETS" ]]; then
    RESET_TARGETS="$(normalize_target_csv "$RESET_TARGETS" map_reset_target_token)"
  fi
  if [[ -n "$RESEED_TARGETS" ]]; then
    RESEED_TARGETS="$(normalize_target_csv "$RESEED_TARGETS" map_reseed_target_token)"
  fi
}

processes_are_running() {
  local path="${1:-$PROCESS_MANIFEST_PATH}"
  local label pid
  [[ -f "$path" ]] || return 1

  while IFS=$'\t' read -r label pid || [[ -n "${label:-}" ]]; do
    [[ -n "${label:-}" && -n "${pid:-}" ]] || continue
    if kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  done <"$path"

  return 1
}

write_state_file() {
  cat >"$STATE_FILE_PATH" <<EOF
VARIANT=$VARIANT
SERVICES=$SERVICES
API_WORKERS=$API_WORKERS
CELERY_WORKERS=$CELERY_WORKERS
START_WORKER=$(normalize_bool "$START_WORKER")
WAIT_READY=$(normalize_bool "$WAIT_READY")
EOF
}

log_current_config() {
  log_info "variant=$VARIANT services=$SERVICES worker=$(normalize_bool "$START_WORKER")"
  log_info "api_workers=$API_WORKERS celery_workers=$CELERY_WORKERS wait_ready=$(normalize_bool "$WAIT_READY")"
  log_info "reset_databases=$(normalize_bool "$RESET_DATABASES") reset_targets=${RESET_TARGETS:-<none>}"
  log_info "reseed_data=$(normalize_bool "$RESEED_DATA") reseed_targets=${RESEED_TARGETS:-<none>}"
}

cleanup_partial_startup() {
  local exit_code=$?
  if [[ "$UP_START_COMPLETED" == "true" ]]; then
    return 0
  fi
  if [[ $exit_code -ne 0 ]]; then
    log_warn "Falha durante startup. Encerrando processos iniciados nesta tentativa."
    stop_registered_processes || true
    rm -f "$PROCESS_MANIFEST_PATH" "$STATE_FILE_PATH"
  fi
}

reset_selected_databases() {
  local db_args=()
  local token

  [[ -n "$RESET_TARGETS" ]] || die "Reset de bancos exige --reset-targets valido."
  IFS=',' read -r -a __reset_items <<<"$RESET_TARGETS"
  for token in "${__reset_items[@]}"; do
    token="$(trim "$token")"
    [[ -z "$token" ]] && continue
    db_args+=(--db "$token")
  done

  if ! is_true "$NON_INTERACTIVE"; then
    if ! confirm_destructive_action "Os bancos selecionados serao apagados."; then
      die "Operacao cancelada pelo usuario."
    fi
  fi

  (
    cd "$JMETER_SUITE_DIR"
    bash "$RESET_DB_SCRIPT" "${db_args[@]}" --yes
  )
}

validate_up_environment() {
  require_command bash
  require_command curl
  require_dir "$JMETER_SUITE_DIR"
  require_file "$RESET_DB_SCRIPT"

  if is_true "$START_SPRING"; then
    require_dir "$SPRING_PROJECT_DIR"
  fi

  if is_true "$START_PYTHON"; then
    require_dir "$(resolve_python_project_dir)"
  fi

  if is_true "$RESET_DATABASES"; then
    require_command psql
    require_command dropdb
    require_command createdb
  fi

  if is_true "$RESEED_DATA"; then
    require_command python3
  fi

  PYTHON_BASE_URL="$(resolve_python_base_url)"
}

start_selected_services() {
  if is_true "$START_SPRING"; then
    maybe_rebuild_spring_db
    start_spring_service
  fi

  if is_true "$START_PYTHON"; then
    run_python_migrations
    maybe_start_redis
    start_python_api
    if is_true "$START_WORKER"; then
      start_python_worker
    else
      log_info "Worker Celery nao sera iniciado."
    fi
  fi
}

wait_selected_services() {
  if ! is_true "$WAIT_READY"; then
    log_info "Espera de readiness desabilitada."
    return 0
  fi

  if is_true "$START_SPRING"; then
    wait_for_spring_ready
  fi
  if is_true "$START_PYTHON"; then
    wait_for_python_ready
  fi
}

run_up() {
  parse_args "$@"
  validate_common_inputs
  configure_service_switches
  resolve_default_targets
  validate_up_environment
  ensure_state_dirs

  if processes_are_running; then
    die "Ja existe um manifest com processos ativos em $PROCESS_MANIFEST_PATH. Rode 'down' ou limpe o estado antes de subir novamente."
  fi

  RUN_RESULTS_DIR="${LOGS_DIR}/run-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$RUN_RESULTS_DIR"
  ORCHESTRATOR_LOG="${RUN_RESULTS_DIR}/manage_pocs.log"
  log_current_config

  trap cleanup_partial_startup EXIT
  clear_registered_processes

  if is_true "$RESET_DATABASES"; then
    reset_selected_databases
  else
    log_info "Reset de bancos desabilitado."
  fi

  start_selected_services
  wait_selected_services

  if is_true "$RESEED_DATA"; then
    maybe_seed_data
  else
    log_info "Seed desabilitada."
  fi

  write_process_manifest "$PROCESS_MANIFEST_PATH"
  write_state_file
  UP_START_COMPLETED="true"
  trap - EXIT

  log_info "Processos registrados em $PROCESS_MANIFEST_PATH"
  log_info "Logs da subida em $RUN_RESULTS_DIR"
}

service_matches_label() {
  local requested="$1"
  local label="$2"
  case "$requested" in
    spring)
      [[ "$label" == "spring" ]]
      ;;
    python)
      [[ "$label" == "python_api" || "$label" == "python_worker" || "$label" == "redis" ]]
      ;;
    both)
      [[ "$label" == "spring" || "$label" == "python_api" || "$label" == "python_worker" || "$label" == "redis" ]]
      ;;
    *)
      return 1
      ;;
  esac
}

run_down() {
  parse_args "$@"
  validate_common_inputs
  ensure_state_dirs

  if [[ ! -f "$PROCESS_MANIFEST_PATH" ]]; then
    log_info "Nenhum manifest encontrado em $PROCESS_MANIFEST_PATH"
    return 0
  fi

  load_process_manifest "$PROCESS_MANIFEST_PATH"

  local idx pid label stopped_any=false
  for (( idx=${#REGISTERED_PIDS[@]}-1; idx>=0; idx-- )); do
    pid="${REGISTERED_PIDS[$idx]}"
    label="${REGISTERED_LABELS[$idx]}"
    if ! service_matches_label "$SERVICES" "$label"; then
      continue
    fi
    if kill -0 "$pid" >/dev/null 2>&1; then
      log_info "Encerrando processo: $label (pid=$pid)"
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
      stopped_any=true
    fi
  done

  if [[ "$stopped_any" == "false" ]]; then
    log_info "Nenhum processo ativo correspondente a '$SERVICES' foi encontrado no manifest."
  fi

  if ! processes_are_running; then
    rm -f "$PROCESS_MANIFEST_PATH" "$STATE_FILE_PATH"
    log_info "Manifest limpo."
  fi
}

run_reset_db() {
  parse_args "$@"
  validate_common_inputs
  resolve_default_targets
  require_command psql
  require_command dropdb
  require_command createdb
  require_file "$RESET_DB_SCRIPT"

  if [[ -z "$RESET_TARGETS" ]]; then
    case "$SERVICES" in
      spring)
        RESET_TARGETS="spring"
        ;;
      python)
        RESET_TARGETS="python"
        ;;
      both)
        RESET_TARGETS="spring,python"
        ;;
    esac
    RESET_TARGETS="$(normalize_target_csv "$RESET_TARGETS" map_reset_target_token)"
  fi

  reset_selected_databases
}

run_status() {
  parse_args "$@"
  validate_common_inputs
  ensure_state_dirs

  if [[ -f "$STATE_FILE_PATH" ]]; then
    log_info "Estado salvo em $STATE_FILE_PATH"
    cat "$STATE_FILE_PATH"
  else
    log_info "Nenhum estado salvo encontrado."
  fi

  if [[ ! -f "$PROCESS_MANIFEST_PATH" ]]; then
    log_info "Nenhum manifest encontrado em $PROCESS_MANIFEST_PATH"
    return 0
  fi

  echo "label	pid	status"
  local label pid status
  while IFS=$'\t' read -r label pid || [[ -n "${label:-}" ]]; do
    [[ -n "${label:-}" && -n "${pid:-}" ]] || continue
    status="stopped"
    if kill -0 "$pid" >/dev/null 2>&1; then
      status="running"
    fi
    printf "%s\t%s\t%s\n" "$label" "$pid" "$status"
  done <"$PROCESS_MANIFEST_PATH"
}

main() {
  case "$COMMAND" in
    up)
      run_up "$@"
      ;;
    down)
      run_down "$@"
      ;;
    reset-db)
      run_reset_db "$@"
      ;;
    status)
      run_status "$@"
      ;;
    help|-h|--help|"")
      usage
      ;;
    *)
      die "Comando invalido: $COMMAND"
      ;;
  esac
}

main "$@"
