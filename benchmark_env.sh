#!/usr/bin/env bash

SUITE_ROOT="${SUITE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SUITE_ROOT/.." && pwd)}"

load_local_env_file() {
  local path="$1"
  local line key value
  [[ -f "$path" ]] || return 0

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
  done <"$path"
}

LOCAL_BENCHMARK_ENV="${LOCAL_BENCHMARK_ENV:-$SUITE_ROOT/local/benchmark.env}"
load_local_env_file "$LOCAL_BENCHMARK_ENV"

JMETER_SUITE_DIR="${JMETER_SUITE_DIR:-$SUITE_ROOT}"
METRICS_TOOL_DIR="${METRICS_TOOL_DIR:-$SUITE_ROOT/tools/metrics}"
METRICS_PYTHON_BIN="${METRICS_PYTHON_BIN:-python3}"
RESET_DB_SCRIPT="${RESET_DB_SCRIPT:-$SUITE_ROOT/scripts/tools/reset_poc_database.sh}"

LEGACY_PROJECT_DIR="${LEGACY_PROJECT_DIR:-$WORKSPACE_ROOT/agentico_poc_fastapi}"
SIMPLE_PY_PROJECT_DIR="${SIMPLE_PY_PROJECT_DIR:-$WORKSPACE_ROOT/poc-llm-ufc-simple-py-}"
SPRING_PROJECT_DIR="${SPRING_PROJECT_DIR:-$WORKSPACE_ROOT/poc-llm-ufc-simples}"

SPRING_START_CMD="${SPRING_START_CMD:-if [[ -f .env ]]; then set -a; source .env; set +a; fi; exec ./mvnw spring-boot:run}"
SPRING_REBUILD_CMD="${SPRING_REBUILD_CMD:-}"
SPRING_READY_URL="${SPRING_READY_URL:-http://localhost:8080/swagger-ui.html}"
SPRING_BASE_URL="${SPRING_BASE_URL:-http://localhost:8080}"

PYTHON_HOST="${PYTHON_HOST:-0.0.0.0}"
PYTHON_PORT="${PYTHON_PORT:-8000}"
LEGACY_READY_URL="${LEGACY_READY_URL:-http://localhost:${PYTHON_PORT}/health}"
SIMPLE_PY_READY_URL="${SIMPLE_PY_READY_URL:-http://localhost:${PYTHON_PORT}/docs}"
LEGACY_BOOTSTRAP_BASE_URL="${LEGACY_BOOTSTRAP_BASE_URL:-http://localhost:${PYTHON_PORT}}"
SIMPLE_PY_BOOTSTRAP_BASE_URL="${SIMPLE_PY_BOOTSTRAP_BASE_URL:-http://localhost:${PYTHON_PORT}}"

REDIS_REQUIRED="${REDIS_REQUIRED:-true}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_START_CMD="${REDIS_START_CMD:-}"

DEFAULT_RUN_FLOW="${DEFAULT_RUN_FLOW:-suite}"
DEFAULT_API_WORKERS="${DEFAULT_API_WORKERS:-1}"
DEFAULT_CELERY_WORKERS="${DEFAULT_CELERY_WORKERS:-1}"
DEFAULT_JMETER_THREADS="${DEFAULT_JMETER_THREADS:-30}"
DEFAULT_JMETER_LOOPS="${DEFAULT_JMETER_LOOPS:-30}"
DEFAULT_JMETER_RAMP_SECONDS="${DEFAULT_JMETER_RAMP_SECONDS:-60}"
DEFAULT_JMETER_DELAY_MS="${DEFAULT_JMETER_DELAY_MS:-50}"

LEGACY_LOAD_TEST_MODE="${LEGACY_LOAD_TEST_MODE:-true}"
LEGACY_LOAD_TEST_PROFESSOR_ID="${LEGACY_LOAD_TEST_PROFESSOR_ID:-1}"

LEGACY_DB_HOST="${LEGACY_DB_HOST:-localhost}"
LEGACY_DB_PORT="${LEGACY_DB_PORT:-5432}"
LEGACY_DB_NAME="${LEGACY_DB_NAME:-${PYTHON_LEGACY_DB_NAME:-llm_ufc}}"
LEGACY_DB_USER="${LEGACY_DB_USER:-${PYTHON_LEGACY_DB_OWNER:-${USER}}}"
LEGACY_DB_PASSWORD="${LEGACY_DB_PASSWORD:-${DB_PASSWORD:-${PGPASSWORD:-}}}"
