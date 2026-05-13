#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/scripts/tools/jmeter_target_utils.sh"

VARIANT="${1:-legacy}"
shift || true

RESULTS_DIR_OVERRIDE=""
SCENARIOS_FILTER=""
TARGET="both"

usage() {
  cat <<'EOF'
Uso:
  bash scripts/run_suite.sh legacy
  bash scripts/run_suite.sh simple_py --results-dir /caminho/resultado
  bash scripts/run_suite.sh legacy --scenarios smoke,baseline_leitura
  bash scripts/run_suite.sh simple_py --target spring --scenarios smoke

Opcoes:
  --results-dir <dir>   Diretorio raiz da rodada para gravar cenarios e relatorio.
  --scenarios <lista>   Lista separada por virgula: smoke,baseline_leitura,baseline_escrita,full_regressao
  --target <stack>      spring, python ou both (padrao).
  --help                Exibe esta ajuda.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --results-dir)
        RESULTS_DIR_OVERRIDE="${2:-}"
        if [[ -z "$RESULTS_DIR_OVERRIDE" ]]; then
          echo "Erro: --results-dir exige um diretorio." >&2
          exit 1
        fi
        shift 2
        ;;
      --scenarios)
        SCENARIOS_FILTER="${2:-}"
        if [[ -z "$SCENARIOS_FILTER" ]]; then
          echo "Erro: --scenarios exige uma lista." >&2
          exit 1
        fi
        shift 2
        ;;
      --target)
        TARGET="${2:-}"
        if [[ -z "$TARGET" ]]; then
          echo "Erro: --target exige spring, python ou both." >&2
          exit 1
        fi
        validate_target "$TARGET" || exit 1
        shift 2
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Erro: argumento desconhecido '$1'." >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

parse_args "$@"

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

if [[ -n "$RESULTS_DIR_OVERRIDE" ]]; then
  RESULTS_DIR="$RESULTS_DIR_OVERRIDE"
fi

validate_target "$TARGET" || exit 1

mkdir -p \
  "$RESULTS_DIR/smoke" \
  "$RESULTS_DIR/baseline_leitura" \
  "$RESULTS_DIR/baseline_escrita" \
  "$RESULTS_DIR/full_regressao"

run_plan() {
  local scenario="$1"
  local plan_name="$2"
  local plan_path filtered_plan

  plan_path="$PLAN_DIR/$plan_name"
  filtered_plan="$(prepare_target_plan "$TARGET" "$plan_path" "$RESULTS_DIR/$scenario")"

  jmeter -n \
    -f \
    -t "$filtered_plan" \
    -q "$CONFIG_DIR/ambientes.properties" \
    -q "$CONFIG_DIR/python.properties" \
    -q "$CONFIG_DIR/jmeter-user.properties" \
    -l "$RESULTS_DIR/$scenario/${plan_name%.jmx}.jtl" \
    -j "$RESULTS_DIR/$scenario/${plan_name%.jmx}.log"
}

run_selected_scenarios() {
  local item
  if [[ -z "$SCENARIOS_FILTER" ]]; then
    run_plan smoke paridade_smoke.jmx
    run_plan baseline_leitura paridade_baseline_leitura.jmx
    run_plan baseline_escrita paridade_baseline_escrita.jmx
    run_plan full_regressao paridade_full_regressao.jmx
    return 0
  fi

  IFS=',' read -r -a items <<<"$SCENARIOS_FILTER"
  for item in "${items[@]}"; do
    case "$item" in
      smoke)
        run_plan smoke paridade_smoke.jmx
        ;;
      baseline_leitura)
        run_plan baseline_leitura paridade_baseline_leitura.jmx
        ;;
      baseline_escrita)
        run_plan baseline_escrita paridade_baseline_escrita.jmx
        ;;
      full_regressao)
        run_plan full_regressao paridade_full_regressao.jmx
        ;;
      *)
        echo "Erro: cenario invalido '$item'." >&2
        exit 1
        ;;
    esac
  done
}

run_selected_scenarios

python3 scripts/gerar_relatorio_variantes.py --variant "$VARIANT" --results-dir "$RESULTS_DIR" --target "$TARGET"
