#!/usr/bin/env bash

run_smoke_flow() {
  log_info "Executando fluxo JMeter: smoke"
  (
    cd "$JMETER_SUITE_DIR"
    bash scripts/run_suite.sh "$VARIANT" --results-dir "$RUN_RESULTS_DIR" --target "$TARGET" --scenarios smoke
  )
}

run_suite_flow() {
  log_info "Executando fluxo JMeter: suite"
  (
    cd "$JMETER_SUITE_DIR"
    bash scripts/run_suite.sh "$VARIANT" --results-dir "$RUN_RESULTS_DIR" --target "$TARGET"
  )
}

run_load_flow() {
  log_info "Executando fluxo JMeter: load"
  (
    cd "$JMETER_SUITE_DIR"
    LOAD_THREADS="$JMETER_THREADS" \
    LOAD_LOOPS="$JMETER_LOOPS" \
    LOAD_RAMP_SECONDS="$JMETER_RAMP_SECONDS" \
    LOAD_DELAY_MS="$JMETER_DELAY_MS" \
    bash scripts/run_load.sh "$VARIANT" --results-dir "$RUN_RESULTS_DIR" --target "$TARGET"
  )
}

run_suite_plus_load_flow() {
  run_suite_flow
  run_load_flow
}

run_jmeter_flow() {
  case "$RUN_FLOW" in
    smoke)
      run_smoke_flow
      ;;
    suite)
      run_suite_flow
      ;;
    load)
      run_load_flow
      ;;
    suite+load)
      run_suite_plus_load_flow
      ;;
    *)
      die "Fluxo JMeter invalido: $RUN_FLOW"
      ;;
  esac
}
