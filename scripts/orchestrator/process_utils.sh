#!/usr/bin/env bash

REGISTERED_PIDS=()
REGISTERED_LABELS=()

register_process() {
  local label="$1"
  local pid="$2"
  REGISTERED_LABELS+=("$label")
  REGISTERED_PIDS+=("$pid")
}

write_process_manifest() {
  local path="$1"
  local idx
  : >"$path"
  for idx in "${!REGISTERED_PIDS[@]}"; do
    printf "%s\t%s\n" "${REGISTERED_LABELS[$idx]}" "${REGISTERED_PIDS[$idx]}" >>"$path"
  done
}

start_background_process() {
  local label="$1"
  local cwd="$2"
  local logfile="$3"
  local command="$4"
  (
    cd "$cwd"
    exec bash -lc "$command"
  ) >>"$logfile" 2>&1 &
  local pid=$!
  register_process "$label" "$pid"
  log_info "Processo iniciado: $label (pid=$pid)"
}

stop_registered_processes() {
  local idx pid label
  for (( idx=${#REGISTERED_PIDS[@]}-1; idx>=0; idx-- )); do
    pid="${REGISTERED_PIDS[$idx]}"
    label="${REGISTERED_LABELS[$idx]}"
    if kill -0 "$pid" >/dev/null 2>&1; then
      log_info "Encerrando processo: $label (pid=$pid)"
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  done
}

is_port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$port )" | grep -q ":$port"
    return $?
  fi
  return 1
}

ensure_port_free() {
  local port="$1"
  local label="$2"
  if is_port_in_use "$port"; then
    die "Porta $port ja esta em uso antes de subir $label."
  fi
}

wait_for_http() {
  local url="$1"
  local timeout_s="${2:-90}"
  local started_at
  started_at="$(date +%s)"
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_s )); then
      return 1
    fi
    sleep 2
  done
}

wait_for_tcp_port() {
  local host="$1"
  local port="$2"
  local timeout_s="${3:-30}"
  local started_at
  started_at="$(date +%s)"
  while true; do
    if (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_s )); then
      return 1
    fi
    sleep 1
  done
}
