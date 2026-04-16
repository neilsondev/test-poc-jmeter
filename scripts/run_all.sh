#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p resultados/smoke resultados/baseline_leitura resultados/baseline_escrita resultados/full_regressao

jmeter -n \
  -f \
  -t planos/paridade_smoke.jmx \
  -q config/ambientes.properties \
  -q config/jmeter-user.properties \
  -l resultados/smoke/paridade_smoke.jtl \
  -j resultados/smoke/paridade_smoke.log

jmeter -n \
  -f \
  -t planos/paridade_baseline_leitura.jmx \
  -q config/ambientes.properties \
  -q config/jmeter-user.properties \
  -l resultados/baseline_leitura/paridade_baseline_leitura.jtl \
  -j resultados/baseline_leitura/paridade_baseline_leitura.log

jmeter -n \
  -f \
  -t planos/paridade_baseline_escrita.jmx \
  -q config/ambientes.properties \
  -q config/jmeter-user.properties \
  -l resultados/baseline_escrita/paridade_baseline_escrita.jtl \
  -j resultados/baseline_escrita/paridade_baseline_escrita.log

jmeter -n \
  -f \
  -t planos/paridade_full_regressao.jmx \
  -q config/ambientes.properties \
  -q config/jmeter-user.properties \
  -l resultados/full_regressao/paridade_full_regressao.jtl \
  -j resultados/full_regressao/paridade_full_regressao.log
