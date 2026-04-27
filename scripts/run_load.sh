#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VARIANT="${1:-legacy}"

case "$VARIANT" in
  legacy)
    PLAN_DIR="planos/legacy"
    CONFIG_DIR="config/legacy"
    RESULTS_DIR="resultados/legacy"
    PLAN_FILE="paridade_load_sem_jwt.jmx"
    SCENARIO="load_sem_jwt"
    ;;
  simple_py)
    PLAN_DIR="planos/simple_py"
    CONFIG_DIR="config/simple_py"
    RESULTS_DIR="resultados/simple_py"
    PLAN_FILE="paridade_load_simple_py.jmx"
    SCENARIO="load_simple_py"
    ;;
  *)
    echo "Variante invalida: $VARIANT" >&2
    echo "Use: legacy ou simple_py" >&2
    exit 1
    ;;
esac

mkdir -p "$RESULTS_DIR/$SCENARIO"

jmeter -n \
  -f \
  -t "$PLAN_DIR/$PLAN_FILE" \
  -q "$CONFIG_DIR/ambientes.properties" \
  -q "$CONFIG_DIR/python.properties" \
  -q "$CONFIG_DIR/jmeter-user.properties" \
  -l "$RESULTS_DIR/$SCENARIO/${PLAN_FILE%.jmx}.jtl" \
  -j "$RESULTS_DIR/$SCENARIO/${PLAN_FILE%.jmx}.log" \
  -Jload.threads="${LOAD_THREADS:-30}" \
  -Jload.loops="${LOAD_LOOPS:-30}" \
  -Jload.ramp.seconds="${LOAD_RAMP_SECONDS:-60}" \
  -Jload.delay.ms="${LOAD_DELAY_MS:-50}"

python3 scripts/gerar_relatorio_variantes.py --variant "$VARIANT"
