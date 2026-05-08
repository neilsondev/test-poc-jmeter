#!/usr/bin/env bash

build_run_id() {
  local variant="$1"
  local run_flow="$2"
  local api_workers="$3"
  local reset_databases="$4"
  local label="${5:-}"
  local stamp suffix
  stamp="$(date +%Y-%m-%d_%H-%M-%S)"
  if is_true "$reset_databases"; then
    suffix="reset"
  else
    suffix="noreset"
  fi
  printf "%s_%s_%s_apiw%s_%s" \
    "$stamp" \
    "$(sanitize_slug "$variant")" \
    "$(sanitize_slug "$run_flow")" \
    "$api_workers" \
    "$suffix"
  if [[ -n "$label" ]]; then
    printf "_%s" "$(sanitize_slug "$label")"
  fi
}

prepare_run_directory() {
  local root="$1"
  local variant="$2"
  local run_id="$3"
  RUN_RESULTS_DIR="$root/resultados/$variant/$run_id"
  mkdir -p "$RUN_RESULTS_DIR"
}

write_metadata_json() {
  local path="$1"
  cat >"$path" <<EOF
{
  "run_id": "${RUN_ID}",
  "variant": "${VARIANT}",
  "run_flow": "${RUN_FLOW}",
  "label": "${LABEL}",
  "api_workers": ${API_WORKERS},
  "celery_workers": ${CELERY_WORKERS},
  "spring_started_by_script": $(normalize_bool "${SPRING_STARTED_BY_SCRIPT:-false}"),
  "python_started_by_script": $(normalize_bool "${PYTHON_STARTED_BY_SCRIPT:-false}"),
  "worker_started_by_script": $(normalize_bool "${WORKER_STARTED_BY_SCRIPT:-false}"),
  "redis_started_by_script": $(normalize_bool "${REDIS_STARTED_BY_SCRIPT:-false}"),
  "reset_databases": $(normalize_bool "${RESET_DATABASES}"),
  "reseed_data": $(normalize_bool "${RESEED_DATA}"),
  "reseed_targets": $(json_array_from_csv "${RESEED_TARGETS:-}"),
  "started_at": "${STARTED_AT}",
  "ended_at": "${ENDED_AT}",
  "spring_base_url": "${SPRING_BASE_URL}",
  "python_base_url": "${PYTHON_BASE_URL}",
  "load_test_mode": $(normalize_bool "${LEGACY_LOAD_TEST_MODE:-false}"),
  "load_test_professor_id": ${LEGACY_LOAD_TEST_PROFESSOR_ID:-0},
  "jmeter_threads": ${JMETER_THREADS},
  "jmeter_loops": ${JMETER_LOOPS},
  "jmeter_ramp_seconds": ${JMETER_RAMP_SECONDS},
  "jmeter_delay_ms": ${JMETER_DELAY_MS},
  "status": "${RUN_STATUS}"
}
EOF
}

write_summary_txt() {
  local path="$1"
  cat >"$path" <<EOF
run_id=${RUN_ID}
variant=${VARIANT}
run_flow=${RUN_FLOW}
status=${RUN_STATUS}
results_dir=${RUN_RESULTS_DIR}
started_at=${STARTED_AT}
ended_at=${ENDED_AT}
EOF
}
