#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/scripts/tools/jmeter_target_utils.sh"

VARIANT="${1:-legacy}"
shift || true

RESULTS_DIR_OVERRIDE=""
TARGET="both"

usage() {
  cat <<'EOF'
Uso:
  bash scripts/run_load.sh legacy
  bash scripts/run_load.sh simple_py --results-dir /caminho/resultado
  bash scripts/run_load.sh simple_py --target python

Opcoes:
  --results-dir <dir>   Diretorio raiz da rodada para gravar carga e relatorio.
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

if [[ -n "$RESULTS_DIR_OVERRIDE" ]]; then
  RESULTS_DIR="$RESULTS_DIR_OVERRIDE"
fi

validate_target "$TARGET" || exit 1

mkdir -p "$RESULTS_DIR/$SCENARIO"

FILTERED_PLAN="$(prepare_target_plan "$TARGET" "$PLAN_DIR/$PLAN_FILE" "$RESULTS_DIR/$SCENARIO")"

jmeter -n \
  -f \
  -t "$FILTERED_PLAN" \
  -q "$CONFIG_DIR/ambientes.properties" \
  -q "$CONFIG_DIR/python.properties" \
  -q "$CONFIG_DIR/jmeter-user.properties" \
  -l "$RESULTS_DIR/$SCENARIO/${PLAN_FILE%.jmx}.jtl" \
  -j "$RESULTS_DIR/$SCENARIO/${PLAN_FILE%.jmx}.log" \
  -Jload.threads="${LOAD_THREADS:-30}" \
  -Jload.loops="${LOAD_LOOPS:-30}" \
  -Jload.ramp.seconds="${LOAD_RAMP_SECONDS:-60}" \
  -Jload.delay.ms="${LOAD_DELAY_MS:-50}"

python3 scripts/gerar_relatorio_variantes.py --variant "$VARIANT" --results-dir "$RESULTS_DIR" --target "$TARGET"
