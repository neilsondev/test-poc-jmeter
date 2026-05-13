#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/benchmark_env.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/lib.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/process_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/result_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/prompt_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/jmeter_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/bootstrap_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/spring_utils.sh"
source "$JMETER_SUITE_DIR/scripts/orchestrator/python_utils.sh"

VARIANT="${VARIANT:-}"
RUN_FLOW="${RUN_FLOW:-$DEFAULT_RUN_FLOW}"
API_WORKERS="${API_WORKERS:-$DEFAULT_API_WORKERS}"
CELERY_WORKERS="${CELERY_WORKERS:-$DEFAULT_CELERY_WORKERS}"
RESET_DATABASES="${RESET_DATABASES:-false}"
RESEED_DATA="${RESEED_DATA:-false}"
RESEED_TARGETS="${RESEED_TARGETS:-}"
RESET_TARGETS="${RESET_TARGETS:-}"
START_SPRING="${START_SPRING:-true}"
START_PYTHON="${START_PYTHON:-true}"
START_WORKER="${START_WORKER:-true}"
VALIDATE_EXISTING_DATA="${VALIDATE_EXISTING_DATA:-true}"
SKIP_VALIDATION="${SKIP_VALIDATION:-false}"
NON_INTERACTIVE="${NON_INTERACTIVE:-false}"
LABEL="${LABEL:-}"
JMETER_THREADS="${JMETER_THREADS:-$DEFAULT_JMETER_THREADS}"
JMETER_LOOPS="${JMETER_LOOPS:-$DEFAULT_JMETER_LOOPS}"
JMETER_RAMP_SECONDS="${JMETER_RAMP_SECONDS:-$DEFAULT_JMETER_RAMP_SECONDS}"
JMETER_DELAY_MS="${JMETER_DELAY_MS:-$DEFAULT_JMETER_DELAY_MS}"
TARGET="${TARGET:-both}"
TARGET_ENABLES_SPRING="true"
TARGET_ENABLES_PYTHON="true"
START_SPRING_EXPLICIT="false"
START_PYTHON_EXPLICIT="false"
START_WORKER_EXPLICIT="false"

RUN_STATUS="error"
RUN_ID=""
RUN_RESULTS_DIR=""
STARTED_AT="$(timestamp_now)"
ENDED_AT=""
ORCHESTRATOR_LOG=""
METADATA_PATH=""
SUMMARY_PATH=""
METRICS_DIR=""
PROCESS_TARGETS_PATH=""
METRICS_LOG=""
METRICS_MONITOR_PID=""
METRICS_ENABLED="${METRICS_ENABLED:-true}"
SPRING_STARTED_BY_SCRIPT=false
PYTHON_STARTED_BY_SCRIPT=false
WORKER_STARTED_BY_SCRIPT=false
REDIS_STARTED_BY_SCRIPT=false
PYTHON_BASE_URL=""

usage() {
  cat <<'EOF'
Uso:
  bash run_benchmark_cycle.sh --variant legacy --run-flow suite

Opcoes:
  --variant legacy|simple_py
  --run-flow smoke|suite|load|suite+load
  --target spring|python|both
  --api-workers N
  --celery-workers N
  --reset-databases true|false
  --reset-targets spring,python
  --reseed-data true|false
  --reseed-targets spring,python
  --start-spring true|false
  --start-python true|false
  --start-worker true|false
  --validate-existing-data true|false
  --skip-validation
  --jmeter-threads N
  --jmeter-loops N
  --jmeter-ramp-seconds N
  --jmeter-delay-ms N
  --label TEXTO
  --non-interactive
  --help
EOF
}

cleanup() {
  local exit_code=$?
  ENDED_AT="$(timestamp_now)"
  if [[ $exit_code -eq 0 && "$RUN_STATUS" != "error" ]]; then
    RUN_STATUS="success"
  elif [[ "$RUN_STATUS" != "success" ]]; then
    RUN_STATUS="error"
  fi

  stop_metrics_collection || true
  stop_registered_processes || true

  if [[ -n "$RUN_RESULTS_DIR" ]]; then
    METADATA_PATH="${RUN_RESULTS_DIR}/metadata.json"
    SUMMARY_PATH="${RUN_RESULTS_DIR}/summary.txt"
    write_metadata_json "$METADATA_PATH" || true
    write_summary_txt "$SUMMARY_PATH" || true
  fi

  exit "$exit_code"
}
trap cleanup EXIT INT TERM

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --variant)
        VARIANT="${2:-}"
        shift 2
        ;;
      --run-flow)
        RUN_FLOW="${2:-}"
        shift 2
        ;;
      --target)
        TARGET="${2:-}"
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
      --start-spring)
        START_SPRING="${2:-}"
        START_SPRING_EXPLICIT="true"
        shift 2
        ;;
      --start-python)
        START_PYTHON="${2:-}"
        START_PYTHON_EXPLICIT="true"
        shift 2
        ;;
      --start-worker)
        START_WORKER="${2:-}"
        START_WORKER_EXPLICIT="true"
        shift 2
        ;;
      --validate-existing-data)
        VALIDATE_EXISTING_DATA="${2:-}"
        shift 2
        ;;
      --skip-validation)
        SKIP_VALIDATION="true"
        shift
        ;;
      --jmeter-threads)
        JMETER_THREADS="${2:-}"
        shift 2
        ;;
      --jmeter-loops)
        JMETER_LOOPS="${2:-}"
        shift 2
        ;;
      --jmeter-ramp-seconds)
        JMETER_RAMP_SECONDS="${2:-}"
        shift 2
        ;;
      --jmeter-delay-ms)
        JMETER_DELAY_MS="${2:-}"
        shift 2
        ;;
      --label)
        LABEL="${2:-}"
        shift 2
        ;;
      --non-interactive)
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

collect_missing_inputs() {
  local start_spring_default start_python_default start_worker_default
  if is_true "$NON_INTERACTIVE"; then
    [[ -n "$VARIANT" ]] || die "--variant e obrigatorio com --non-interactive"
    [[ -n "$RUN_FLOW" ]] || die "--run-flow e obrigatorio com --non-interactive"
    return 0
  fi

  VARIANT="$(ask_choice "Escolha a variante Python" "${VARIANT:-legacy}" "legacy" "simple_py")"
  RUN_FLOW="$(ask_choice "Escolha o fluxo JMeter" "${RUN_FLOW:-$DEFAULT_RUN_FLOW}" "smoke" "suite" "load" "suite+load")"
  TARGET="$(ask_choice "Escolha o target do JMeter" "${TARGET:-both}" "both" "spring" "python")"
  case "$TARGET" in
    spring)
      start_spring_default="true"
      start_python_default="false"
      start_worker_default="false"
      ;;
    python)
      start_spring_default="false"
      start_python_default="true"
      start_worker_default="true"
      ;;
    both)
      start_spring_default="true"
      start_python_default="true"
      start_worker_default="true"
      ;;
  esac
  API_WORKERS="$(ask_int "Quantidade de processos da API Python" "${API_WORKERS:-$DEFAULT_API_WORKERS}")"
  CELERY_WORKERS="$(ask_int "Concorrencia do Celery" "${CELERY_WORKERS:-$DEFAULT_CELERY_WORKERS}")"
  RESET_DATABASES="$(ask_bool "Deseja resetar bancos nesta rodada?" "$(normalize_bool "$RESET_DATABASES")")"
  RESEED_DATA="$(ask_bool "Deseja refazer a seed de massa?" "$(normalize_bool "$RESEED_DATA")")"
  START_SPRING="$(ask_bool "Deseja subir o Spring nesta rodada?" "$start_spring_default")"
  START_PYTHON="$(ask_bool "Deseja subir a API Python nesta rodada?" "$start_python_default")"
  START_WORKER="$(ask_bool "Deseja subir o worker Celery?" "$start_worker_default")"
  START_SPRING_EXPLICIT="true"
  START_PYTHON_EXPLICIT="true"
  START_WORKER_EXPLICIT="true"
  if [[ "$RUN_FLOW" == "load" || "$RUN_FLOW" == "suite+load" ]]; then
    JMETER_THREADS="$(ask_int "Quantidade de threads do JMeter" "${JMETER_THREADS:-$DEFAULT_JMETER_THREADS}")"
    JMETER_LOOPS="$(ask_int "Quantidade de loops do JMeter" "${JMETER_LOOPS:-$DEFAULT_JMETER_LOOPS}")"
    JMETER_RAMP_SECONDS="$(ask_int "Ramp-up do JMeter em segundos" "${JMETER_RAMP_SECONDS:-$DEFAULT_JMETER_RAMP_SECONDS}")"
    JMETER_DELAY_MS="$(ask_int "Delay do JMeter em ms" "${JMETER_DELAY_MS:-$DEFAULT_JMETER_DELAY_MS}")"
  fi
}

validate_environment() {
  require_command bash
  require_command psql
  require_command dropdb
  require_command createdb
  require_command python3
  require_command curl
  require_command jmeter
  require_dir "$JMETER_SUITE_DIR"
  require_dir "$LEGACY_PROJECT_DIR"
  require_dir "$SIMPLE_PY_PROJECT_DIR"
  require_file "$RESET_DB_SCRIPT"
  require_file "$METRICS_TOOL_DIR/metrics_runner.py"
  require_file "$JMETER_SUITE_DIR/scripts/run_suite.sh"
  require_file "$JMETER_SUITE_DIR/scripts/run_load.sh"

  case "$VARIANT" in
    legacy|simple_py)
      ;;
    *)
      die "Variante invalida: $VARIANT"
      ;;
  esac

  case "$RUN_FLOW" in
    smoke|suite|load|suite+load)
      ;;
    *)
      die "Fluxo invalido: $RUN_FLOW"
      ;;
  esac

  case "$TARGET" in
    spring)
      TARGET_ENABLES_SPRING="true"
      TARGET_ENABLES_PYTHON="false"
      ;;
    python)
      TARGET_ENABLES_SPRING="false"
      TARGET_ENABLES_PYTHON="true"
      ;;
    both)
      TARGET_ENABLES_SPRING="true"
      TARGET_ENABLES_PYTHON="true"
      ;;
    *)
      die "Target invalido: $TARGET"
      ;;
  esac

  [[ "$API_WORKERS" =~ ^[0-9]+$ ]] || die "API_WORKERS invalido: $API_WORKERS"
  [[ "$CELERY_WORKERS" =~ ^[0-9]+$ ]] || die "CELERY_WORKERS invalido: $CELERY_WORKERS"
  [[ "$JMETER_THREADS" =~ ^[0-9]+$ ]] || die "JMETER_THREADS invalido: $JMETER_THREADS"
  [[ "$JMETER_LOOPS" =~ ^[0-9]+$ ]] || die "JMETER_LOOPS invalido: $JMETER_LOOPS"
  [[ "$JMETER_RAMP_SECONDS" =~ ^[0-9]+$ ]] || die "JMETER_RAMP_SECONDS invalido: $JMETER_RAMP_SECONDS"
  [[ "$JMETER_DELAY_MS" =~ ^[0-9]+$ ]] || die "JMETER_DELAY_MS invalido: $JMETER_DELAY_MS"

  PYTHON_BASE_URL="$(resolve_python_base_url)"
  validate_metrics_runtime
}

apply_target_defaults() {
  if ! is_true "$START_SPRING_EXPLICIT"; then
    START_SPRING="$TARGET_ENABLES_SPRING"
  fi

  if ! is_true "$START_PYTHON_EXPLICIT"; then
    START_PYTHON="$TARGET_ENABLES_PYTHON"
  fi

  if ! is_true "$START_WORKER_EXPLICIT"; then
    START_WORKER="$TARGET_ENABLES_PYTHON"
  fi
}

validate_metrics_runtime() {
  if ! is_true "$METRICS_ENABLED"; then
    log_info "Coleta de metricas desabilitada por configuracao."
    return 0
  fi

  require_command "$METRICS_PYTHON_BIN"
  require_file "$METRICS_TOOL_DIR/metrics_runner.py"

  if ! "$METRICS_PYTHON_BIN" -c "import psutil" >/dev/null 2>&1; then
    log_warn "Coleta de metricas desabilitada: $METRICS_PYTHON_BIN nao possui psutil."
    log_warn "Instale com '$METRICS_PYTHON_BIN -m pip install psutil' ou ajuste METRICS_PYTHON_BIN em config/benchmark.env."
    METRICS_ENABLED="false"
  fi
}

build_run_context() {
  local python_db_key
  python_db_key="$(resolve_python_db_key)"
  apply_target_defaults

  if [[ -z "$RESET_TARGETS" && "$(normalize_bool "$RESET_DATABASES")" == "true" ]]; then
    if is_true "$TARGET_ENABLES_SPRING" && is_true "$TARGET_ENABLES_PYTHON"; then
      RESET_TARGETS="spring,${python_db_key}"
    elif is_true "$TARGET_ENABLES_SPRING"; then
      RESET_TARGETS="spring"
    else
      RESET_TARGETS="${python_db_key}"
    fi
  fi

  if [[ -z "$RESEED_TARGETS" && "$(normalize_bool "$RESEED_DATA")" == "true" ]]; then
    if is_true "$TARGET_ENABLES_SPRING" && is_true "$TARGET_ENABLES_PYTHON"; then
      RESEED_TARGETS="spring,python"
    elif is_true "$TARGET_ENABLES_SPRING"; then
      RESEED_TARGETS="spring"
    else
      RESEED_TARGETS="python"
    fi
  fi

  RUN_ID="$(build_run_id "$VARIANT" "$RUN_FLOW" "$API_WORKERS" "$RESET_DATABASES" "$TARGET" "$LABEL")"
  prepare_run_directory "$JMETER_SUITE_DIR" "$VARIANT" "$RUN_ID"
  ORCHESTRATOR_LOG="$RUN_RESULTS_DIR/orchestrator.log"
  touch "$ORCHESTRATOR_LOG"
  log_info "Run id: $RUN_ID"
}

setup_metrics_context() {
  METRICS_DIR="$RUN_RESULTS_DIR/metricas"
  PROCESS_TARGETS_PATH="$METRICS_DIR/process_targets.tsv"
  METRICS_LOG="$METRICS_DIR/metrics_runner.log"
  mkdir -p "$METRICS_DIR"
}

start_metrics_collection() {
  if ! is_true "$METRICS_ENABLED"; then
    log_info "Coleta de metricas desabilitada."
    return 0
  fi

  write_process_manifest "$PROCESS_TARGETS_PATH"
  if [[ ! -s "$PROCESS_TARGETS_PATH" ]]; then
    log_warn "Nenhum processo iniciado pela rodada foi registrado para metricas."
    return 0
  fi

  log_info "Iniciando coleta de metricas em $METRICS_DIR"
  (
    cd "$JMETER_SUITE_DIR"
    exec "$METRICS_PYTHON_BIN" tools/metrics/metrics_runner.py \
      --scenario "$RUN_FLOW" \
      --targets-file "$PROCESS_TARGETS_PATH" \
      --results-dir "$METRICS_DIR" \
      --command "bash run_benchmark_cycle.sh --variant $VARIANT --run-flow $RUN_FLOW --target $TARGET"
  ) >>"$METRICS_LOG" 2>&1 &
  METRICS_MONITOR_PID=$!

  sleep 1
  if ! kill -0 "$METRICS_MONITOR_PID" >/dev/null 2>&1; then
    log_error "metrics_runner.py falhou ao iniciar. Verifique $METRICS_LOG"
    METRICS_MONITOR_PID=""
    return 0
  fi
}

stop_metrics_collection() {
  if [[ -z "$METRICS_MONITOR_PID" ]]; then
    return 0
  fi
  if kill -0 "$METRICS_MONITOR_PID" >/dev/null 2>&1; then
    log_info "Encerrando coleta de metricas (pid=$METRICS_MONITOR_PID)"
    kill -TERM "$METRICS_MONITOR_PID" >/dev/null 2>&1 || true
    wait "$METRICS_MONITOR_PID" >/dev/null 2>&1 || true
  fi
}

maybe_reset_databases() {
  if ! is_true "$RESET_DATABASES"; then
    log_info "Reset de bancos desabilitado."
    return 0
  fi
  if ! is_true "$NON_INTERACTIVE"; then
    if ! confirm_destructive_action "Os bancos selecionados serao apagados."; then
      die "Operacao cancelada pelo usuario."
    fi
  fi

  local db_args=()
  local token
  IFS=',' read -r -a __reset_items <<<"$RESET_TARGETS"
  for token in "${__reset_items[@]}"; do
    token="$(trim "$token")"
    [[ -z "$token" ]] && continue
    db_args+=(--db "$token")
  done
  [[ "${#db_args[@]}" -gt 0 ]] || die "RESET_DATABASES=true exige RESET_TARGETS valido."

  log_info "Resetando bancos: $RESET_TARGETS"
  (
    cd "$JMETER_SUITE_DIR"
    bash "$RESET_DB_SCRIPT" "${db_args[@]}" --yes
  )
}

maybe_start_services() {
  maybe_rebuild_spring_db
  run_python_migrations
  maybe_start_redis
  start_spring_service
  start_python_api
  start_python_worker
}

wait_for_services() {
  wait_for_spring_ready
  wait_for_python_ready
}

print_summary() {
  log_info "Rodada concluida com status=$RUN_STATUS"
  log_info "Resultados: $RUN_RESULTS_DIR"
}

main() {
  parse_args "$@"
  collect_missing_inputs
  validate_environment
  build_run_context
  maybe_reset_databases
  maybe_start_services
  wait_for_services
  setup_metrics_context
  start_metrics_collection
  maybe_seed_data
  maybe_validate_data
  run_jmeter_flow
  RUN_STATUS="success"
  print_summary
}

main "$@"
