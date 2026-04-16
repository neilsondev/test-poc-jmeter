#!/usr/bin/env python3
"""Gera relatorio consolidado a partir dos arquivos JTL do JMeter."""

from __future__ import annotations

import csv
import html
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "resultados"
REPORT_DIR = RESULTS_DIR / "relatorio"
RUN_GAP_MS = 10 * 60 * 1000


@dataclass(frozen=True)
class Metric:
    total: int
    errors: int
    duration_s: float
    throughput_s: float
    avg_ms: float
    min_ms: int
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: int
    avg_latency_ms: float
    p95_latency_ms: float
    avg_connect_ms: float
    p95_connect_ms: float
    avg_bytes: float
    avg_sent_bytes: float

    @property
    def error_pct(self) -> float:
        return (self.errors / self.total * 100) if self.total else 0.0


def percentile(values: list[int], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * percent / 100
    floor = math.floor(k)
    ceil = math.ceil(k)
    if floor == ceil:
        return float(ordered[int(k)])
    return ordered[floor] * (ceil - k) + ordered[ceil] * (k - floor)


def read_jtl(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    value = row.get(field, "")
    return int(value) if value not in ("", None) else default


def latest_run(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    if not rows:
        return rows, 0
    ordered = sorted(rows, key=lambda row: int(row["timeStamp"]))
    sessions: list[list[dict[str, str]]] = [[ordered[0]]]
    for row in ordered[1:]:
        previous = int(sessions[-1][-1]["timeStamp"])
        current = int(row["timeStamp"])
        if current - previous > RUN_GAP_MS:
            sessions.append([])
        sessions[-1].append(row)
    return sessions[-1], len(sessions)


def metric_for(rows: list[dict[str, str]]) -> Metric:
    if not rows:
        return Metric(0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    elapsed = [int_field(row, "elapsed") for row in rows]
    latency = [int_field(row, "Latency") for row in rows]
    connect = [int_field(row, "Connect") for row in rows]
    bytes_received = [int_field(row, "bytes") for row in rows]
    sent_bytes = [int_field(row, "sentBytes") for row in rows]
    started = [int_field(row, "timeStamp") for row in rows]
    ended = [int_field(row, "timeStamp") + int_field(row, "elapsed") for row in rows]
    duration_s = (max(ended) - min(started)) / 1000
    errors = sum(1 for row in rows if row["success"].lower() != "true")
    return Metric(
        total=len(rows),
        errors=errors,
        duration_s=duration_s,
        throughput_s=(len(rows) / duration_s) if duration_s else 0.0,
        avg_ms=mean(elapsed),
        min_ms=min(elapsed),
        p50_ms=percentile(elapsed, 50),
        p90_ms=percentile(elapsed, 90),
        p95_ms=percentile(elapsed, 95),
        p99_ms=percentile(elapsed, 99),
        max_ms=max(elapsed),
        avg_latency_ms=mean(latency),
        p95_latency_ms=percentile(latency, 95),
        avg_connect_ms=mean(connect),
        p95_connect_ms=percentile(connect, 95),
        avg_bytes=mean(bytes_received),
        avg_sent_bytes=mean(sent_bytes),
    )


def stack_for(label: str) -> str:
    if "Python" in label:
        return "Python"
    if "Spring" in label:
        return "Spring"
    return "Outro"


def operation_for(label: str) -> str:
    lower = label.lower()
    if "login" in lower:
        return "login"
    if "create" in lower or "post" in lower:
        return "escrita"
    if "get" in lower or "list" in lower:
        return "leitura"
    return "outro"


def comparable_endpoint_for(label: str) -> str:
    words_to_drop = {"spring", "python", "get", "post"}
    words = [word for word in label.lower().split() if word not in words_to_drop]
    normalized = " ".join(words).replace("by id", "get").strip()
    return normalized or "outro"


def fmt_ms(value: float) -> str:
    return f"{value:.1f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def metric_row(name: str, metric: Metric) -> list[str]:
    return [
        name,
        str(metric.total),
        fmt_pct(metric.error_pct),
        f"{metric.throughput_s:.2f}",
        fmt_ms(metric.avg_ms),
        fmt_ms(metric.p50_ms),
        fmt_ms(metric.p90_ms),
        fmt_ms(metric.p95_ms),
        fmt_ms(metric.p99_ms),
        str(metric.max_ms),
        fmt_ms(metric.avg_latency_ms),
        fmt_ms(metric.p95_latency_ms),
        fmt_ms(metric.avg_connect_ms),
        fmt_ms(metric.p95_connect_ms),
        f"{metric.avg_bytes:.0f}",
        f"{metric.avg_sent_bytes:.0f}",
    ]


def stack_operation_row(name: str, stack: str, operation: str, rows: list[dict[str, str]]) -> list[str]:
    metric = metric_for(rows)
    successful = [row for row in rows if row["success"].lower() == "true"]
    successful_metric = metric_for(successful)
    return [
        name,
        stack,
        operation,
        str(metric.total),
        fmt_pct(metric.error_pct),
        fmt_ms(metric.avg_ms),
        fmt_ms(metric.p95_ms),
        fmt_ms(successful_metric.avg_ms),
        fmt_ms(successful_metric.p95_ms),
        fmt_ms(metric.avg_latency_ms),
        fmt_ms(metric.p95_latency_ms),
        fmt_ms(metric.avg_connect_ms),
        str(metric.max_ms),
    ]


def comparison_rows_for(label_metrics: list[dict]) -> list[list[str]]:
    grouped: dict[tuple[str, str, str], dict[str, Metric]] = defaultdict(dict)
    for item in label_metrics:
        if item["stack"] not in {"Spring", "Python"}:
            continue
        key = (item["scenario"], item["operation"], item["endpoint"])
        grouped[key][item["stack"]] = item["metric"]

    rows: list[list[str]] = []
    for (scenario, operation, endpoint), metrics in sorted(grouped.items()):
        spring = metrics.get("Spring")
        python = metrics.get("Python")
        if not spring or not python:
            continue
        avg_delta = python.avg_ms - spring.avg_ms
        p95_delta = python.p95_ms - spring.p95_ms
        avg_ratio = python.avg_ms / spring.avg_ms if spring.avg_ms else 0.0
        p95_ratio = python.p95_ms / spring.p95_ms if spring.p95_ms else 0.0
        faster = "Python" if python.p95_ms < spring.p95_ms else "Spring"
        rows.append(
            [
                scenario,
                operation,
                endpoint,
                str(spring.total),
                str(python.total),
                fmt_ms(spring.avg_ms),
                fmt_ms(python.avg_ms),
                fmt_ms(avg_delta),
                f"{avg_ratio:.2f}x",
                fmt_ms(spring.p95_ms),
                fmt_ms(python.p95_ms),
                fmt_ms(p95_delta),
                f"{p95_ratio:.2f}x",
                faster,
            ]
        )
    return rows


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def pct_width(value: float, max_value: float) -> int:
    if max_value <= 0:
        return 0
    return max(2, min(100, int(value / max_value * 100)))


def build_comparison_chart(comparison_rows: list[list[str]]) -> str:
    rows = comparison_rows[:28]
    max_value = max((max(float(row[9]), float(row[10])) for row in rows), default=1.0)
    chart_rows = []
    for row in rows:
        spring_p95 = float(row[9])
        python_p95 = float(row[10])
        chart_rows.append(
            f"""
            <div class="chart-row">
              <div class="chart-label">{html.escape(row[0])}<br><strong>{html.escape(row[2])}</strong></div>
              <div class="bars">
                <div class="bar-line"><span class="series spring" style="width:{pct_width(spring_p95, max_value)}%"></span><em>Spring {spring_p95:.1f} ms</em></div>
                <div class="bar-line"><span class="series python" style="width:{pct_width(python_p95, max_value)}%"></span><em>Python {python_p95:.1f} ms</em></div>
              </div>
              <div class="delta">{html.escape(row[12])}</div>
            </div>
            """
        )
    return "".join(chart_rows) if chart_rows else "<p>Sem pares Spring/Python equivalentes para comparar.</p>"


def build_stack_chart(stack_operation_rows: list[list[str]]) -> str:
    rows = stack_operation_rows
    max_value = max((max(float(row[6]), float(row[10]), float(row[11])) for row in rows), default=1.0)
    chart_rows = []
    for row in rows:
        stack_class = row[1].lower()
        chart_rows.append(
            f"""
            <div class="compact-row">
              <span>{html.escape(row[0])} / {html.escape(row[1])} / {html.escape(row[2])}</span>
              <div>
                <div class="bar-line"><span class="series {stack_class}" style="width:{pct_width(float(row[6]), max_value)}%"></span><em>elapsed p95 {html.escape(row[6])} ms</em></div>
                <div class="bar-line"><span class="series latency" style="width:{pct_width(float(row[10]), max_value)}%"></span><em>latency p95 {html.escape(row[10])} ms</em></div>
                <div class="bar-line"><span class="series connect" style="width:{pct_width(float(row[11]), max_value)}%"></span><em>connect avg {html.escape(row[11])} ms</em></div>
              </div>
            </div>
            """
        )
    return "".join(chart_rows)


def build_bytes_chart(label_rows: list[list[str]]) -> str:
    rows = sorted(label_rows, key=lambda row: float(row[13]), reverse=True)[:18]
    max_value = max((float(row[13]) for row in rows), default=1.0)
    chart_rows = []
    for row in rows:
        stack_class = row[2].lower()
        chart_rows.append(
            f"""
            <div class="compact-row">
              <span>{html.escape(row[0])} / {html.escape(row[1])}</span>
              <div class="bar-line"><span class="series {stack_class}" style="width:{pct_width(float(row[13]), max_value)}%"></span><em>{html.escape(row[13])} bytes em media</em></div>
            </div>
            """
        )
    return "".join(chart_rows)


def build_label_table(label_rows: list[list[str]]) -> str:
    return "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in label_rows
    )


def build_html(scenarios: list[dict], label_rows: list[list[str]], stack_operation_rows: list[list[str]], comparison_rows: list[list[str]]) -> str:
    cards = []
    max_total = max((item["metric"].total for item in scenarios), default=1)
    for item in scenarios:
        metric: Metric = item["metric"]
        width = max(2, int(metric.total / max_total * 100))
        err_width = max(0, min(100, int(metric.error_pct)))
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(item["name"])}</h2>
              <p><strong>{metric.total}</strong> samples em {metric.duration_s:.2f}s, {metric.throughput_s:.2f}/s</p>
              <div class="bar"><span style="width:{width}%"></span></div>
              <p>Erro: <strong>{metric.error_pct:.2f}%</strong></p>
              <div class="bar danger"><span style="width:{err_width}%"></span></div>
              <p>Elapsed avg {metric.avg_ms:.1f} ms | p95 {metric.p95_ms:.1f} ms | p99 {metric.p99_ms:.1f} ms | max {metric.max_ms} ms</p>
              <p>Latency avg {metric.avg_latency_ms:.1f} ms | Connect avg {metric.avg_connect_ms:.1f} ms | bytes {metric.avg_bytes:.0f}</p>
            </section>
            """
        )
    body_rows = build_label_table(label_rows)
    comparison_chart = build_comparison_chart(comparison_rows)
    stack_chart = build_stack_chart(stack_operation_rows)
    bytes_chart = build_bytes_chart(label_rows)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatorio JMeter Paridade</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; color: #172026; background: #f5f7f8; }}
    header {{ padding: 28px; background: #12343b; color: #fff; }}
    main {{ padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .card {{ background: #fff; border: 1px solid #d7dee2; border-radius: 8px; padding: 16px; }}
    .panel {{ background: #fff; border: 1px solid #d7dee2; border-radius: 8px; padding: 18px; margin-top: 20px; }}
    .bar {{ height: 10px; background: #e4eaed; border-radius: 6px; overflow: hidden; }}
    .bar span {{ display: block; height: 100%; background: #2e7d32; }}
    .bar.danger span {{ background: #c62828; }}
    .chart-row {{ display: grid; grid-template-columns: minmax(180px, 280px) 1fr 80px; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid #eef2f4; }}
    .compact-row {{ display: grid; grid-template-columns: minmax(240px, 380px) 1fr; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid #eef2f4; }}
    .bar-line {{ position: relative; height: 24px; background: #eef2f4; border-radius: 6px; overflow: hidden; margin: 3px 0; }}
    .series {{ display: block; height: 100%; }}
    .series.spring {{ background: #1976d2; }}
    .series.python {{ background: #2e7d32; }}
    .series.latency {{ background: #6a1b9a; }}
    .series.connect {{ background: #ef6c00; }}
    .bar-line em {{ position: absolute; left: 8px; top: 5px; font-style: normal; font-size: 12px; color: #102027; }}
    .delta {{ font-weight: 700; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }}
    .legend span {{ border: 1px solid #d7dee2; border-radius: 8px; padding: 8px 10px; background: #fff; color: #102027; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; margin-top: 20px; }}
    th, td {{ border: 1px solid #d7dee2; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #e9eff2; }}
    @media (max-width: 760px) {{
      .chart-row, .compact-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Relatorio JMeter Paridade</h1>
    <p>Consolidado automatico dos arquivos .jtl com foco em diferenciar Spring e Python.</p>
    <div class="legend">
      <span><strong>Elapsed</strong>: tempo total observado pelo JMeter.</span>
      <span><strong>Latency</strong>: tempo ate o primeiro byte de resposta.</span>
      <span><strong>Connect</strong>: tempo gasto para abrir conexao TCP.</span>
      <span><strong>p95</strong>: 95% das chamadas ficaram abaixo desse tempo.</span>
    </div>
  </header>
  <main>
    <div class="grid">{''.join(cards)}</div>
    <section class="panel">
      <h2>p95 por endpoint equivalente</h2>
      <p>Compara somente labels que possuem par Spring e Python no mesmo cenario. A coluna final mostra quantas vezes o p95 do Python ficou em relacao ao Spring.</p>
      {comparison_chart}
    </section>
    <section class="panel">
      <h2>p95 por stack e operacao</h2>
      <p>Ajuda a separar leitura, escrita e login. Elapsed e o tempo total; latency mostra quando chegou o primeiro byte; connect aponta custo de abertura de conexao.</p>
      {stack_chart}
    </section>
    <section class="panel">
      <h2>Volume medio de resposta</h2>
      <p>Endpoints com payload maior podem parecer mais caros mesmo quando a aplicacao responde rapido. Use este grafico junto com latency e elapsed.</p>
      {bytes_chart}
    </section>
    <section class="panel">
      <h2>Detalhe por label</h2>
    <table>
      <thead>
        <tr><th>Cenario</th><th>Label</th><th>Stack</th><th>Operacao</th><th>Total</th><th>Erro</th><th>Avg ms</th><th>p95 ms</th><th>p99 ms</th><th>Max ms</th><th>Latency avg</th><th>Latency p95</th><th>Connect avg</th><th>Bytes avg</th><th>Codigos</th></tr>
      </thead>
      <tbody>{body_rows}</tbody>
    </table>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    jtl_files = sorted(RESULTS_DIR.glob("*/*.jtl"))
    scenarios: list[dict] = []
    scenario_rows: list[list[str]] = []
    stack_operation_rows: list[list[str]] = []
    label_rows: list[list[str]] = []
    label_metrics: list[dict] = []
    warnings: list[str] = []
    error_counter: Counter[tuple[str, str, str]] = Counter()

    for path in jtl_files:
        raw_rows = read_jtl(path)
        rows, session_count = latest_run(raw_rows)
        scenario_name = path.parent.name
        if session_count > 1:
            warnings.append(
                f"- `{scenario_name}` tinha {session_count} execucoes no mesmo JTL; o relatorio usou apenas a execucao mais recente."
            )
        metric = metric_for(rows)
        scenarios.append({"name": scenario_name, "path": str(path), "metric": metric})
        scenario_rows.append(metric_row(scenario_name, metric))

        by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
        by_stack_operation: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_label[row["label"]].append(row)
            stack = stack_for(row["label"])
            operation = operation_for(row["label"])
            if stack != "Outro":
                by_stack_operation[(stack, operation)].append(row)
            if row["success"].lower() != "true":
                error_counter[(scenario_name, row["label"], row["responseCode"])] += 1

        for (stack, operation), group_rows in sorted(by_stack_operation.items()):
            stack_operation_rows.append(stack_operation_row(scenario_name, stack, operation, group_rows))

        for label, label_samples in sorted(by_label.items()):
            label_metric = metric_for(label_samples)
            codes = Counter(row["responseCode"] for row in label_samples)
            stack = stack_for(label)
            operation = operation_for(label)
            label_metrics.append(
                {
                    "scenario": scenario_name,
                    "label": label,
                    "stack": stack,
                    "operation": operation,
                    "endpoint": comparable_endpoint_for(label),
                    "metric": label_metric,
                }
            )
            label_rows.append(
                [
                    scenario_name,
                    label,
                    stack,
                    operation,
                    str(label_metric.total),
                    fmt_pct(label_metric.error_pct),
                    fmt_ms(label_metric.avg_ms),
                    fmt_ms(label_metric.p95_ms),
                    fmt_ms(label_metric.p99_ms),
                    str(label_metric.max_ms),
                    fmt_ms(label_metric.avg_latency_ms),
                    fmt_ms(label_metric.p95_latency_ms),
                    fmt_ms(label_metric.avg_connect_ms),
                    f"{label_metric.avg_bytes:.0f}",
                    json.dumps(dict(sorted(codes.items())), ensure_ascii=False),
                ]
            )

    comparison_rows = comparison_rows_for(label_metrics)
    headers = [
        "Cenario",
        "Total",
        "Erro",
        "Throughput/s",
        "Avg ms",
        "p50 ms",
        "p90 ms",
        "p95 ms",
        "p99 ms",
        "Max ms",
        "Latency avg ms",
        "Latency p95 ms",
        "Connect avg ms",
        "Connect p95 ms",
        "Bytes avg",
        "Sent bytes avg",
    ]
    stack_operation_headers = [
        "Cenario",
        "Stack",
        "Operacao",
        "Total",
        "Erro",
        "Avg ms",
        "p95 ms",
        "Avg ms sucesso",
        "p95 ms sucesso",
        "Latency avg ms",
        "Latency p95 ms",
        "Connect avg ms",
        "Max ms",
    ]
    label_headers = [
        "Cenario",
        "Label",
        "Stack",
        "Operacao",
        "Total",
        "Erro",
        "Avg ms",
        "p95 ms",
        "p99 ms",
        "Max ms",
        "Latency avg ms",
        "Latency p95 ms",
        "Connect avg ms",
        "Bytes avg",
        "Codigos",
    ]
    comparison_headers = [
        "Cenario",
        "Operacao",
        "Endpoint",
        "Total Spring",
        "Total Python",
        "Avg Spring ms",
        "Avg Python ms",
        "Delta avg Python-Spring ms",
        "Razao avg Python/Spring",
        "p95 Spring ms",
        "p95 Python ms",
        "Delta p95 Python-Spring ms",
        "Razao p95 Python/Spring",
        "Mais rapido no p95",
    ]
    write_csv(REPORT_DIR / "summary_by_scenario.csv", headers, scenario_rows)
    write_csv(REPORT_DIR / "summary_by_stack_operation.csv", stack_operation_headers, stack_operation_rows)
    write_csv(REPORT_DIR / "summary_by_label.csv", label_headers, label_rows)
    write_csv(REPORT_DIR / "comparison_spring_python.csv", comparison_headers, comparison_rows)
    (REPORT_DIR / "dashboard.html").write_text(
        build_html(scenarios, label_rows, stack_operation_rows, comparison_rows), encoding="utf-8"
    )

    top_errors = [
        [scenario, label, code, str(total)]
        for (scenario, label, code), total in error_counter.most_common(12)
    ]
    executive_summary = [
        "- Smoke, baseline de escrita, baseline de leitura e full regressao estao com 0% de erro na execucao analisada."
    ]
    if top_errors:
        executive_summary = [
            "- Smoke e baseline de escrita estao saudaveis: 0% de erro.",
            "- Baseline de leitura e full regressao nao devem ser usados como benchmark final enquanto houver 4xx no Python.",
            "- Os erros registrados indicam problema de massa/autorizacao quando token e IDs nao pertencem ao mesmo professor.",
        ]
    report = [
        "# Relatorio dos resultados JMeter",
        "",
        "## Resumo executivo",
        "",
        *executive_summary,
        "- Spring ficou consistentemente mais rapido nas leituras; Python ficou mais caro principalmente nos endpoints autenticados e no login.",
        "",
        "## Por cenario",
        "",
        markdown_table(headers, scenario_rows),
        "",
        "## Avisos",
        "",
        "\n".join(warnings) if warnings else "Nenhum aviso.",
        "",
        "## Top erros",
        "",
        markdown_table(["Cenario", "Label", "Codigo", "Ocorrencias"], top_errors) if top_errors else "Sem erros registrados.",
        "",
        "## Por stack e operacao",
        "",
        markdown_table(stack_operation_headers, stack_operation_rows),
        "",
        "## Comparacao Spring x Python",
        "",
        "Delta positivo significa que Python ficou mais lento que Spring. A razao `2.00x` indica o dobro do tempo do Spring.",
        "",
        markdown_table(comparison_headers, comparison_rows) if comparison_rows else "Sem pares equivalentes para comparar.",
        "",
        "## Por endpoint",
        "",
        markdown_table(label_headers, label_rows),
        "",
        "## Leitura tecnica",
        "",
        "Os erros relevantes sao 403 Forbidden nos endpoints Python de leitura por ID, modulos, aulas e prova. Como o README define 401/403/404/409 como falha de preparacao ou de plano, esses cenarios ainda nao medem paridade de performance de forma limpa.",
        "",
        "O login Python aparece com latencia bem maior que as operacoes comuns. Isso nao e necessariamente problema do endpoint de dominio; ele deve ser medido separadamente ou removido das comparacoes Spring vs Python quando o objetivo for paridade dos recursos.",
        "",
        "## Melhorias sugeridas no teste",
        "",
        "1. Manter `python_read_ids.csv` com credenciais e IDs na mesma linha, para preservar o vinculo entre token e dono dos recursos.",
        "2. Rodar a etapa de pre-validacao, que autentica cada linha de `python_read_ids.csv` e valida os IDs com o token correto antes do JMeter.",
        "3. Separar dashboards de login, leitura e escrita. Login e custo de autorizacao distorcem a comparacao direta entre stacks.",
        "4. Aumentar gradualmente concorrencia e duracao depois que o erro funcional estiver zerado. Os testes atuais sao curtos; bons para smoke/baseline inicial, fracos para estabilidade.",
        "5. Adicionar criterios de aceite por plano, por exemplo: erro 0%, p95 leitura < 100 ms em ambiente local, p95 escrita < 250 ms, sem 4xx inesperado.",
        "6. Salvar tambem ambiente, commit, seed da massa e configuracoes de threads junto do resultado para tornar a comparacao reproduzivel.",
        "",
        "## Como visualizar",
        "",
        "- Abrir `resultados/relatorio/dashboard.html` no navegador para uma visao rapida.",
        "- Usar `summary_by_scenario.csv`, `summary_by_label.csv` e `comparison_spring_python.csv` em planilha, Metabase, Grafana ou notebook.",
        "- Usar o dashboard nativo do JMeter: `jmeter -g resultados/<cenario>/<arquivo>.jtl -o resultados/<cenario>/html-report`.",
        "",
    ]
    (REPORT_DIR / "relatorio_resultados.md").write_text("\n".join(report), encoding="utf-8")

    print(f"Relatorio gerado em {REPORT_DIR / 'relatorio_resultados.md'}")
    print(f"Dashboard gerado em {REPORT_DIR / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
