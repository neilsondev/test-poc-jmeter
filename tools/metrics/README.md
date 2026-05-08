# Ferramentas de métricas

Este diretório reúne as ferramentas auxiliares de métricas e consolidação usadas pela suíte:

- `metrics_runner.py`: monitora CPU, RSS, VMS, threads e processos durante a rodada
- `consolidate_benchmark_runs.py`: consolida múltiplas rodadas por `label`
- `simulate_p99_sensitivity.py`: simula impacto de mudanças hipotéticas no `p99` sem alterar o `.jtl`

Uso comum:

```bash
python3 tools/metrics/consolidate_benchmark_runs.py --label suite-load-maio-2026
```

Saída padrão do consolidado:

```text
tools/metrics/campaign_reports/<label>/
```
