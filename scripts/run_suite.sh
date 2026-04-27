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
    ;;
  simple_py)
    PLAN_DIR="planos/simple_py"
    CONFIG_DIR="config/simple_py"
    RESULTS_DIR="resultados/simple_py"
    ;;
  *)
    echo "Variante invalida: $VARIANT" >&2
    echo "Use: legacy ou simple_py" >&2
    exit 1
    ;;
esac

mkdir -p \
  "$RESULTS_DIR/smoke" \
  "$RESULTS_DIR/baseline_leitura" \
  "$RESULTS_DIR/baseline_escrita" \
  "$RESULTS_DIR/full_regressao"

run_plan() {
  local scenario="$1"
  local plan_name="$2"

  jmeter -n \
    -f \
    -t "$PLAN_DIR/$plan_name" \
    -q "$CONFIG_DIR/ambientes.properties" \
    -q "$CONFIG_DIR/python.properties" \
    -q "$CONFIG_DIR/jmeter-user.properties" \
    -l "$RESULTS_DIR/$scenario/${plan_name%.jmx}.jtl" \
    -j "$RESULTS_DIR/$scenario/${plan_name%.jmx}.log"
}

run_plan smoke paridade_smoke.jmx
run_plan baseline_leitura paridade_baseline_leitura.jmx
run_plan baseline_escrita paridade_baseline_escrita.jmx
run_plan full_regressao paridade_full_regressao.jmx

python3 scripts/gerar_relatorio_variantes.py --variant "$VARIANT"
