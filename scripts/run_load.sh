#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VARIANT="${1:-legacy}"
shift || true

RESULTS_DIR_OVERRIDE=""

usage() {
  cat <<'EOF'
Uso:
  bash scripts/run_load.sh legacy
  bash scripts/run_load.sh simple_py --results-dir /caminho/resultado

Opcoes:
  --results-dir <dir>   Diretorio raiz da rodada para gravar carga e relatorio.
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

python3 scripts/gerar_relatorio_variantes.py --variant "$VARIANT" --results-dir "$RESULTS_DIR"
