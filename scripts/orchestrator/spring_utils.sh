#!/usr/bin/env bash

maybe_rebuild_spring_db() {
  if ! csv_contains "$RESET_TARGETS" "spring"; then
    return 0
  fi
  if [[ -z "${SPRING_REBUILD_CMD:-}" ]]; then
    if is_true "${START_SPRING:-false}"; then
      log_info "SPRING_REBUILD_CMD nao configurado. O Spring aplicara Flyway no startup."
    else
      log_warn "SPRING_REBUILD_CMD nao configurado e o Spring nao sera iniciado pela rodada."
    fi
    return 0
  fi
  if [[ -z "${SPRING_PROJECT_DIR:-}" ]]; then
    die "SPRING_PROJECT_DIR nao configurado para rebuild do Spring."
  fi
  log_info "Executando rebuild estrutural do Spring"
  (
    cd "$SPRING_PROJECT_DIR"
    bash -lc "$SPRING_REBUILD_CMD"
  )
}

start_spring_service() {
  if ! is_true "$START_SPRING"; then
    log_info "Spring sera reutilizado em execucao ja existente."
    return 0
  fi
  [[ -n "${SPRING_PROJECT_DIR:-}" ]] || die "SPRING_PROJECT_DIR nao configurado."
  [[ -n "${SPRING_START_CMD:-}" ]] || die "SPRING_START_CMD nao configurado."
  local spring_log="$RUN_RESULTS_DIR/spring.log"
  start_background_process "spring" "$SPRING_PROJECT_DIR" "$spring_log" "$SPRING_START_CMD"
  SPRING_STARTED_BY_SCRIPT=true
}

wait_for_spring_ready() {
  log_info "Aguardando Spring em $SPRING_READY_URL"
  if ! wait_for_http "$SPRING_READY_URL" "${SPRING_READY_TIMEOUT_SECONDS:-180}"; then
    die "Spring nao ficou pronto em tempo habil."
  fi
}
