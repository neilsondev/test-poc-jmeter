#!/usr/bin/env bash

seed_spring_data() {
  log_info "Executando seed Spring"
  (
    cd "$JMETER_SUITE_DIR"
    BOOTSTRAP_BASE_URL="$SPRING_BASE_URL" \
    python3 scripts/spring/bootstrap_spring_read_data.py
  )
}

seed_legacy_data() {
  log_info "Executando seed Python legacy"
  local legacy_python_bin
  if ! legacy_python_bin="$(resolve_python_interpreter)"; then
    die "Nao encontrei interpretador Python para a variante legacy."
  fi
  (
    cd "$JMETER_SUITE_DIR"
    DB_HOST="$LEGACY_DB_HOST" \
    DB_PORT="$LEGACY_DB_PORT" \
    DB_NAME="$LEGACY_DB_NAME" \
    DB_USER="$LEGACY_DB_USER" \
    DB_PASSWORD="$LEGACY_DB_PASSWORD" \
    PYTHON_BIN="$legacy_python_bin" \
    bash scripts/legacy/bootstrap_python_admin_insert.sh
  )
  (
    cd "$JMETER_SUITE_DIR"
    BOOTSTRAP_BASE_URL="$LEGACY_BOOTSTRAP_BASE_URL" \
    "$legacy_python_bin" scripts/legacy/bootstrap_python_test_users.py
  )
  (
    cd "$JMETER_SUITE_DIR"
    BOOTSTRAP_BASE_URL="$LEGACY_BOOTSTRAP_BASE_URL" \
    "$legacy_python_bin" scripts/legacy/bootstrap_python_read_data.py
  )
}

seed_simple_py_data() {
  log_info "Executando seed Python simple_py"
  local simple_python_bin
  if ! simple_python_bin="$(resolve_python_interpreter)"; then
    die "Nao encontrei interpretador Python para a variante simple_py."
  fi
  (
    cd "$JMETER_SUITE_DIR"
    BOOTSTRAP_BASE_URL="$SIMPLE_PY_BOOTSTRAP_BASE_URL" \
    "$simple_python_bin" scripts/simple_py/bootstrap_python_read_data.py
  )
}

validate_spring_data() {
  log_info "Validando massa Spring"
  local validator
  validator="scripts/${VARIANT}/validar_massa.py"
  local python_bin
  if ! python_bin="$(resolve_python_interpreter)"; then
    die "Nao encontrei interpretador Python para validar a variante $VARIANT."
  fi
  (
    cd "$JMETER_SUITE_DIR"
    SPRING_VALIDATION_BASE_URL="$SPRING_BASE_URL" \
    PYTHON_VALIDATION_BASE_URL="$PYTHON_BASE_URL" \
    "$python_bin" "$validator"
  )
}

seed_python_variant_data() {
  case "$VARIANT" in
    legacy)
      seed_legacy_data
      ;;
    simple_py)
      seed_simple_py_data
      ;;
    *)
      die "Variante invalida para seed: $VARIANT"
      ;;
  esac
}

maybe_seed_data() {
  if ! is_true "$RESEED_DATA"; then
    log_info "Seed desabilitada para esta rodada."
    return 0
  fi
  if csv_contains "$RESEED_TARGETS" "spring"; then
    seed_spring_data
  fi
  if csv_contains "$RESEED_TARGETS" "python"; then
    seed_python_variant_data
  fi
}

maybe_validate_data() {
  if is_true "${SKIP_VALIDATION:-false}"; then
    log_warn "Validacao de massa ignorada por configuracao."
    return 0
  fi
  if is_true "$RESEED_DATA" || is_true "${VALIDATE_EXISTING_DATA:-false}"; then
    validate_spring_data
  else
    log_info "Validacao de massa nao executada."
  fi
}
