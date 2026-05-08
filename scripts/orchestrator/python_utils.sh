#!/usr/bin/env bash

resolve_python_project_dir() {
  case "$VARIANT" in
    legacy)
      printf "%s" "$LEGACY_PROJECT_DIR"
      ;;
    simple_py)
      printf "%s" "$SIMPLE_PY_PROJECT_DIR"
      ;;
    *)
      return 1
      ;;
  esac
}

dotenv_loader_command() {
  cat <<'EOF'
if [[ -f .env ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line#"${line%%[![:space:]]*}"}" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${line#*=}"
    value="${value%$'\r'}"
    if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < .env
fi
EOF
}

resolve_python_bin_dir() {
  local project_dir
  project_dir="$(resolve_python_project_dir)"
  if [[ -d "$project_dir/.venv/bin" ]]; then
    printf "%s" "$project_dir/.venv/bin"
    return 0
  fi
  if [[ -d "$project_dir/venv/bin" ]]; then
    printf "%s" "$project_dir/venv/bin"
    return 0
  fi
  return 1
}

resolve_python_tool() {
  local tool="$1"
  local bin_dir
  if bin_dir="$(resolve_python_bin_dir)" && [[ -x "$bin_dir/$tool" ]]; then
    printf "%s" "$bin_dir/$tool"
    return 0
  fi
  if command -v "$tool" >/dev/null 2>&1; then
    command -v "$tool"
    return 0
  fi
  return 1
}

resolve_python_interpreter() {
  local bin_dir
  if bin_dir="$(resolve_python_bin_dir)"; then
    if [[ -x "$bin_dir/python" ]]; then
      printf "%s" "$bin_dir/python"
      return 0
    fi
    if [[ -x "$bin_dir/python3" ]]; then
      printf "%s" "$bin_dir/python3"
      return 0
    fi
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

resolve_python_ready_url() {
  case "$VARIANT" in
    legacy)
      printf "%s" "$LEGACY_READY_URL"
      ;;
    simple_py)
      printf "%s" "$SIMPLE_PY_READY_URL"
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_python_base_url() {
  case "$VARIANT" in
    legacy)
      printf "%s" "$LEGACY_BOOTSTRAP_BASE_URL"
      ;;
    simple_py)
      printf "%s" "$SIMPLE_PY_BOOTSTRAP_BASE_URL"
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_python_db_key() {
  case "$VARIANT" in
    legacy)
      printf "%s" "python_legacy"
      ;;
    simple_py)
      printf "%s" "python_simple"
      ;;
    *)
      return 1
      ;;
  esac
}

run_python_migrations() {
  local project_dir alembic_cmd
  project_dir="$(resolve_python_project_dir)"
  if ! csv_contains "$RESET_TARGETS" "$(resolve_python_db_key)"; then
    log_info "Migrations Python nao necessarias para esta rodada."
    return 0
  fi
  if ! alembic_cmd="$(resolve_python_tool alembic)"; then
    die "Nao encontrei o executavel 'alembic' no ambiente da variante $VARIANT."
  fi
  log_info "Executando migrations da variante $VARIANT"
  (
    cd "$project_dir"
    load_dotenv_file .env
    "$alembic_cmd" upgrade head
  )
}

build_legacy_api_command() {
  local uvicorn_cmd
  if ! uvicorn_cmd="$(resolve_python_tool uvicorn)"; then
    die "Nao encontrei o executavel 'uvicorn' no ambiente legacy."
  fi
  if (( API_WORKERS > 1 )); then
    if [[ -n "${LEGACY_API_MULTIWORKER_CMD:-}" ]]; then
      printf "%s" "$LEGACY_API_MULTIWORKER_CMD"
      return 0
    fi
    cat <<EOF
$(dotenv_loader_command)
export LOAD_TEST_MODE=${LEGACY_LOAD_TEST_MODE}
export LOAD_TEST_PROFESSOR_ID=${LEGACY_LOAD_TEST_PROFESSOR_ID}
exec "$uvicorn_cmd" main:app --host ${PYTHON_HOST} --port ${PYTHON_PORT} --workers ${API_WORKERS}
EOF
    return 0
  fi
  cat <<EOF
$(dotenv_loader_command)
export LOAD_TEST_MODE=${LEGACY_LOAD_TEST_MODE}
export LOAD_TEST_PROFESSOR_ID=${LEGACY_LOAD_TEST_PROFESSOR_ID}
exec "$uvicorn_cmd" main:app --host ${PYTHON_HOST} --port ${PYTHON_PORT}
EOF
}

build_simple_py_api_command() {
  local uvicorn_cmd
  if ! uvicorn_cmd="$(resolve_python_tool uvicorn)"; then
    die "Nao encontrei o executavel 'uvicorn' no ambiente simple_py."
  fi
  if (( API_WORKERS > 1 )); then
    if [[ -n "${SIMPLE_PY_API_MULTIWORKER_CMD:-}" ]]; then
      printf "%s" "$SIMPLE_PY_API_MULTIWORKER_CMD"
      return 0
    fi
    cat <<EOF
$(dotenv_loader_command)
exec "$uvicorn_cmd" app.main:app --host ${PYTHON_HOST} --port ${PYTHON_PORT} --workers ${API_WORKERS}
EOF
    return 0
  fi
  cat <<EOF
$(dotenv_loader_command)
exec "$uvicorn_cmd" app.main:app --host ${PYTHON_HOST} --port ${PYTHON_PORT}
EOF
}

build_python_worker_command() {
  local celery_cmd
  if ! celery_cmd="$(resolve_python_tool celery)"; then
    die "Nao encontrei o executavel 'celery' no ambiente da variante $VARIANT."
  fi
  case "$VARIANT" in
    legacy)
      cat <<EOF
$(dotenv_loader_command)
export LOAD_TEST_MODE=${LEGACY_LOAD_TEST_MODE}
export LOAD_TEST_PROFESSOR_ID=${LEGACY_LOAD_TEST_PROFESSOR_ID}
exec "$celery_cmd" -A br.ufc.llm.shared.service.celery_app.celery_app worker --loglevel=info --concurrency=${CELERY_WORKERS}
EOF
      ;;
    simple_py)
      cat <<EOF
$(dotenv_loader_command)
exec "$celery_cmd" -A app.worker.celery_app worker --loglevel=info --concurrency=${CELERY_WORKERS}
EOF
      ;;
    *)
      die "Variante invalida para worker: $VARIANT"
      ;;
  esac
}

start_python_api() {
  if ! is_true "$START_PYTHON"; then
    log_info "API Python sera reutilizada em execucao ja existente."
    return 0
  fi
  local project_dir api_log command
  project_dir="$(resolve_python_project_dir)"
  api_log="$RUN_RESULTS_DIR/python_api.log"
  ensure_port_free "$PYTHON_PORT" "API Python"
  case "$VARIANT" in
    legacy)
      command="$(build_legacy_api_command)"
      ;;
    simple_py)
      command="$(build_simple_py_api_command)"
      ;;
    *)
      die "Variante invalida: $VARIANT"
      ;;
  esac
  start_background_process "python_api" "$project_dir" "$api_log" "$command"
  PYTHON_STARTED_BY_SCRIPT=true
}

start_python_worker() {
  if ! is_true "$START_WORKER"; then
    log_info "Worker Celery nao sera iniciado nesta rodada."
    return 0
  fi
  local project_dir worker_log command
  project_dir="$(resolve_python_project_dir)"
  worker_log="$RUN_RESULTS_DIR/python_worker.log"
  command="$(build_python_worker_command)"
  start_background_process "python_worker" "$project_dir" "$worker_log" "$command"
  WORKER_STARTED_BY_SCRIPT=true
}

wait_for_python_ready() {
  local ready_url
  ready_url="$(resolve_python_ready_url)"
  log_info "Aguardando API Python em $ready_url"
  if ! wait_for_http "$ready_url" "${PYTHON_READY_TIMEOUT_SECONDS:-120}"; then
    die "API Python nao ficou pronta em tempo habil."
  fi
}

maybe_start_redis() {
  if ! is_true "$REDIS_REQUIRED"; then
    log_info "Redis marcado como nao obrigatorio para esta rodada."
    return 0
  fi
  if wait_for_tcp_port "$REDIS_HOST" "$REDIS_PORT" 2; then
    log_info "Redis ja esta disponivel em ${REDIS_HOST}:${REDIS_PORT}"
    return 0
  fi
  if [[ -z "${REDIS_START_CMD:-}" ]]; then
    die "Redis nao esta disponivel e REDIS_START_CMD nao foi configurado."
  fi
  local redis_log="$RUN_RESULTS_DIR/redis.log"
  start_background_process "redis" "$WORKSPACE_ROOT" "$redis_log" "$REDIS_START_CMD"
  REDIS_STARTED_BY_SCRIPT=true
  if ! wait_for_tcp_port "$REDIS_HOST" "$REDIS_PORT" "${REDIS_READY_TIMEOUT_SECONDS:-30}"; then
    die "Redis nao ficou pronto em tempo habil."
  fi
}
