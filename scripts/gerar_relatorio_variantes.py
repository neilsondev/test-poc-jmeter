#!/usr/bin/env python3
"""Gera relatório consolidado por variante da suíte JMeter."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent.parent
RUN_GAP_MS = 10 * 60 * 1000
SCENARIO_DESCRIPTIONS = {
    "smoke": "Validação mínima de disponibilidade, massa e endpoints essenciais.",
    "baseline_leitura": "Comparação controlada de operações GET equivalentes entre as stacks.",
    "baseline_escrita": "Criação encadeada de curso, módulo, aula e quiz/avaliação.",
    "full_regressao": "Subconjunto misto para detectar regressão funcional ampla sem custo de execução alto.",
    "load_sem_jwt": "Carga mista histórica da API Python legacy sem autenticação JWT.",
    "load_simple_py": "Carga mista da PoC Python simple_py com quatro leituras e uma criação por iteração.",
}
STACK_COLORS = {
    "Spring": "#1d4ed8",
    "Python": "#15803d",
    "Outro": "#6b7280",
}


@dataclass(frozen=True)
class Metric:
    total: int
    errors: int
    duration_s: float
    throughput_s: float
    avg_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: int
    avg_latency_ms: float
    avg_connect_ms: float
    avg_bytes: float

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


def int_field(row: dict[str, str], field: str) -> int:
    value = row.get(field, "")
    return int(value) if value else 0


def latest_run(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    if not rows:
        return rows, 0
    ordered = sorted(rows, key=lambda row: int(row["timeStamp"]))
    sessions = [[ordered[0]]]
    for row in ordered[1:]:
        if int(row["timeStamp"]) - int(sessions[-1][-1]["timeStamp"]) > RUN_GAP_MS:
            sessions.append([])
        sessions[-1].append(row)
    return sessions[-1], len(sessions)


def metric_for(rows: list[dict[str, str]]) -> Metric:
    if not rows:
        return Metric(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0)
    elapsed = [int_field(row, "elapsed") for row in rows]
    latency = [int_field(row, "Latency") for row in rows]
    connect = [int_field(row, "Connect") for row in rows]
    bytes_received = [int_field(row, "bytes") for row in rows]
    started = [int_field(row, "timeStamp") for row in rows]
    ended = [int_field(row, "timeStamp") + int_field(row, "elapsed") for row in rows]
    duration_s = (max(ended) - min(started)) / 1000 if rows else 0.0
    errors = sum(1 for row in rows if row["success"].lower() != "true")
    return Metric(
        total=len(rows),
        errors=errors,
        duration_s=duration_s,
        throughput_s=(len(rows) / duration_s) if duration_s else 0.0,
        avg_ms=mean(elapsed),
        p95_ms=percentile(elapsed, 95),
        p99_ms=percentile(elapsed, 99),
        max_ms=max(elapsed),
        avg_latency_ms=mean(latency),
        avg_connect_ms=mean(connect),
        avg_bytes=mean(bytes_received),
    )


def stack_for(label: str) -> str:
    if "Python" in label:
        return "Python"
    if "Spring" in label:
        return "Spring"
    return "Outro"


def operation_for(label: str) -> str:
    lower = label.lower()
    if "create" in lower or "post" in lower:
        return "escrita"
    if "get" in lower or "list" in lower:
        return "leitura"
    return "outro"


def comparable_endpoint_for(label: str) -> str:
    words_to_drop = {"spring", "python", "get", "post", "load"}
    words = [word for word in label.lower().split() if word not in words_to_drop]
    return " ".join(words).strip() or "outro"


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def fmt_ms(value: float) -> str:
    return f"{value:.1f} ms"


def fmt_ms_compact(value: float) -> str:
    return f"{value:.1f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def fmt_throughput(value: float) -> str:
    return f"{value:.2f}/s"


def fmt_bytes(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} MB"
    if value >= 1_000:
        return f"{value / 1_000:.1f} KB"
    return f"{value:.0f} B"


def truncate(value: str, size: int = 52) -> str:
    return value if len(value) <= size else f"{value[: size - 1]}…"


def pct_width(value: float, max_value: float, floor: int = 4) -> int:
    if max_value <= 0:
        return 0
    return max(floor, min(100, int(value / max_value * 100)))


def severity_for_delta(delta_ms: float) -> str:
    abs_delta = abs(delta_ms)
    if abs_delta >= 25:
        return "critical"
    if abs_delta >= 8:
        return "warning"
    return "ok"


def severity_for_error(error_pct: float) -> str:
    if error_pct >= 5:
        return "critical"
    if error_pct > 0:
        return "warning"
    return "ok"


def build_variant_summary(variant: str, scenario_metrics: list[dict]) -> dict[str, object]:
    metrics = [item["metric"] for item in scenario_metrics]
    total_samples = sum(metric.total for metric in metrics)
    total_errors = sum(metric.errors for metric in metrics)
    total_duration = sum(metric.duration_s for metric in metrics)
    weighted_throughput = (total_samples / total_duration) if total_duration else 0.0
    worst_p95 = max(scenario_metrics, key=lambda item: item["metric"].p95_ms, default=None)
    slowest_duration = max(scenario_metrics, key=lambda item: item["metric"].duration_s, default=None)
    highest_volume = max(scenario_metrics, key=lambda item: item["metric"].total, default=None)
    largest_payload = max(scenario_metrics, key=lambda item: item["metric"].avg_bytes, default=None)
    return {
        "variant": variant,
        "total_samples": total_samples,
        "error_pct": (total_errors / total_samples * 100) if total_samples else 0.0,
        "weighted_throughput": weighted_throughput,
        "scenario_count": len(scenario_metrics),
        "worst_p95": worst_p95,
        "slowest_duration": slowest_duration,
        "highest_volume": highest_volume,
        "largest_payload": largest_payload,
    }


def build_comparison_entries(label_metrics: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict[str, dict]] = defaultdict(dict)
    for item in label_metrics:
        if item["stack"] in {"Spring", "Python"}:
            grouped[(item["scenario"], item["operation"], item["endpoint"])][item["stack"]] = item

    entries: list[dict] = []
    for (scenario, operation, endpoint), metrics in sorted(grouped.items()):
        spring_item = metrics.get("Spring")
        python_item = metrics.get("Python")
        if not spring_item or not python_item:
            continue
        spring = spring_item["metric"]
        python = python_item["metric"]
        delta_p95 = python.p95_ms - spring.p95_ms
        faster = "Python" if delta_p95 < 0 else "Spring"
        entries.append(
            {
                "scenario": scenario,
                "operation": operation,
                "endpoint": endpoint,
                "spring": spring,
                "python": python,
                "delta_p95": delta_p95,
                "delta_avg": python.avg_ms - spring.avg_ms,
                "ratio_p95": (python.p95_ms / spring.p95_ms) if spring.p95_ms else 0.0,
                "faster": faster,
                "severity": severity_for_delta(delta_p95),
                "abs_delta": abs(delta_p95),
            }
        )
    return entries


def build_dashboard_insights(
    comparison_entries: list[dict],
    label_metrics: list[dict],
    scenario_metrics: list[dict],
) -> dict[str, object]:
    best_python = [item for item in comparison_entries if item["delta_p95"] < 0]
    best_spring = [item for item in comparison_entries if item["delta_p95"] > 0]
    ties = [item for item in comparison_entries if abs(item["delta_p95"]) < 0.5]
    missing_pairs = sorted(
        item["name"]
        for item in scenario_metrics
        if item["name"] not in {entry["scenario"] for entry in comparison_entries}
    )
    payload_leaders = sorted(label_metrics, key=lambda item: item["metric"].avg_bytes, reverse=True)[:5]
    p95_leaders = sorted(label_metrics, key=lambda item: item["metric"].p95_ms, reverse=True)[:5]
    return {
        "best_python": sorted(best_python, key=lambda item: item["delta_p95"])[:3],
        "best_spring": sorted(best_spring, key=lambda item: item["delta_p95"], reverse=True)[:3],
        "ties": ties[:3],
        "missing_pairs": missing_pairs,
        "payload_leaders": payload_leaders,
        "p95_leaders": p95_leaders,
    }


def comparison_csv_rows(comparison_entries: list[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in comparison_entries:
        rows.append(
            [
                item["scenario"],
                item["operation"],
                item["endpoint"],
                fmt_ms_compact(item["spring"].p95_ms),
                fmt_ms_compact(item["python"].p95_ms),
                fmt_ms_compact(item["delta_p95"]),
                item["faster"],
            ]
        )
    return rows


def build_hero(summary: dict[str, object]) -> str:
    worst = summary["worst_p95"]
    slowest = summary["slowest_duration"]
    volume = summary["highest_volume"]
    payload = summary["largest_payload"]
    return f"""
    <header class="hero">
      <div>
        <p class="eyebrow">JMeter Paridade</p>
        <h1>Relatório visual da variante {html.escape(str(summary["variant"]))}</h1>
        <p class="hero-copy">A leitura principal prioriza a comparação Spring x Python, destacando diferenças de p95 antes do detalhamento operacional.</p>
      </div>
      <div class="hero-grid">
        <article class="hero-stat">
          <span>Total de amostras</span>
          <strong>{summary["total_samples"]}</strong>
          <small>{summary["scenario_count"]} cenários processados</small>
        </article>
        <article class="hero-stat">
          <span>Erro consolidado</span>
          <strong>{fmt_pct(float(summary["error_pct"]))}</strong>
          <small>throughput ponderado {fmt_throughput(float(summary["weighted_throughput"]))}</small>
        </article>
        <article class="hero-stat">
          <span>Pior p95</span>
          <strong>{fmt_ms(worst["metric"].p95_ms) if worst else "n/d"}</strong>
          <small>{html.escape(worst["name"]) if worst else "Sem cenários"}</small>
        </article>
        <article class="hero-stat">
          <span>Maior volume</span>
          <strong>{volume["metric"].total if volume else 0}</strong>
          <small>{html.escape(volume["name"]) if volume else "Sem cenários"}</small>
        </article>
        <article class="hero-stat">
          <span>Maior duração</span>
          <strong>{slowest["metric"].duration_s:.2f}s</strong>
          <small>{html.escape(slowest["name"]) if slowest else "Sem cenários"}</small>
        </article>
        <article class="hero-stat">
          <span>Maior payload médio</span>
          <strong>{fmt_bytes(payload["metric"].avg_bytes) if payload else "n/d"}</strong>
          <small>{html.escape(payload["name"]) if payload else "Sem cenários"}</small>
        </article>
      </div>
    </header>
    """


def build_plain_language_section() -> str:
    return """
    <section class="panel explainer">
      <h2>Como ler este relatório</h2>
      <p>Este painel resume tempo, volume e estabilidade das chamadas feitas pelo JMeter. A ideia é mostrar rapidamente onde a API respondeu bem, onde houve lentidão e em quais pontos Spring e Python se comportaram de forma diferente.</p>
      <div class="explain-list">
        <p><strong>Total de amostras</strong>: quantidade de requisições medidas naquele cenário ou endpoint.</p>
        <p><strong>Erro</strong>: percentual de requisições que falharam. Quanto mais perto de 0%, melhor.</p>
        <p><strong>Throughput</strong>: quantas requisições por segundo o cenário conseguiu sustentar.</p>
        <p><strong>Avg</strong>: tempo médio de resposta. Dá uma noção geral, mas pode esconder picos.</p>
        <p><strong>p95</strong>: tempo abaixo do qual ficaram 95% das respostas. É um bom indicador de experiência real.</p>
        <p><strong>p99</strong>: mostra caudas de lentidão mais raras, úteis para identificar picos.</p>
        <p><strong>Max</strong>: maior tempo observado. Serve como alerta, mas isoladamente pode ser ruído.</p>
        <p><strong>Latency</strong>: tempo até começar a receber a resposta.</p>
        <p><strong>Connect</strong>: custo médio para abrir a conexão com o banco ou serviço HTTP.</p>
        <p><strong>Payload</strong>: volume médio de dados trafegados na resposta. Payload maior pode aumentar o tempo.</p>
        <p><strong>Delta</strong>: diferença entre Python e Spring no mesmo endpoint. Valor positivo indica Python mais lento; negativo indica Python mais rápido.</p>
      </div>
    </section>
    """


def build_scenario_cards(scenario_metrics: list[dict]) -> str:
    max_total = max((item["metric"].total for item in scenario_metrics), default=1)
    cards = []
    for item in scenario_metrics:
        metric: Metric = item["metric"]
        error_class = severity_for_error(metric.error_pct)
        volume_width = pct_width(metric.total, max_total)
        description = SCENARIO_DESCRIPTIONS.get(item["name"], "Cenário sem descrição catalogada.")
        cards.append(
            f"""
            <article class="card scenario-card">
              <div class="card-head">
                <div>
                  <p class="kicker">{html.escape(item["name"])}</p>
                  <h2>{html.escape(description)}</h2>
                </div>
                <span class="badge {error_class}">erro {fmt_pct(metric.error_pct)}</span>
              </div>
              <div class="stat-strip">
                <div><strong>{metric.total}</strong><span>amostras</span></div>
                <div><strong>{fmt_throughput(metric.throughput_s)}</strong><span>throughput</span></div>
                <div><strong>{metric.duration_s:.2f}s</strong><span>duração</span></div>
              </div>
              <div class="meter">
                <span style="width:{volume_width}%"></span>
              </div>
              <div class="mini-grid">
                <div><span>avg</span><strong>{fmt_ms(metric.avg_ms)}</strong></div>
                <div><span>p95</span><strong>{fmt_ms(metric.p95_ms)}</strong></div>
                <div><span>p99</span><strong>{fmt_ms(metric.p99_ms)}</strong></div>
                <div><span>max</span><strong>{fmt_ms(metric.max_ms)}</strong></div>
                <div><span>latency</span><strong>{fmt_ms(metric.avg_latency_ms)}</strong></div>
                <div><span>connect</span><strong>{fmt_ms(metric.avg_connect_ms)}</strong></div>
              </div>
              <p class="footnote">Payload médio {fmt_bytes(metric.avg_bytes)}. A barra representa o volume relativo de amostras dentro da variante.</p>
            </article>
            """
        )
    return "".join(cards)


def build_winner_panel(comparison_entries: list[dict]) -> str:
    if not comparison_entries:
        return "<p class=\"empty-state\">Nenhum endpoint equivalente Spring/Python foi encontrado nesta variante.</p>"
    wins = Counter(item["faster"] for item in comparison_entries)
    ranked = sorted(comparison_entries, key=lambda item: item["abs_delta"], reverse=True)[:8]
    rows = []
    for item in ranked:
        delta_class = "python-win" if item["delta_p95"] < 0 else "spring-win"
        rows.append(
            f"""
            <div class="winner-row">
              <div>
                <strong>{html.escape(item["scenario"])}</strong>
                <span>{html.escape(truncate(item["endpoint"]))} · {html.escape(item["operation"])}</span>
              </div>
              <div class="winner-meta">
                <span class="stack-pill spring">Spring {fmt_ms(item["spring"].p95_ms)}</span>
                <span class="stack-pill python">Python {fmt_ms(item["python"].p95_ms)}</span>
                <span class="delta-pill {delta_class}">{item["delta_p95"]:+.1f} ms</span>
              </div>
            </div>
            """
        )
    return f"""
    <div class="winner-summary">
      <article><strong>{wins.get("Spring", 0)}</strong><span>vitórias Spring</span></article>
      <article><strong>{wins.get("Python", 0)}</strong><span>vitórias Python</span></article>
      <article><strong>{len(comparison_entries)}</strong><span>pares comparáveis</span></article>
    </div>
    {''.join(rows)}
    """


def build_comparison_bars(comparison_entries: list[dict]) -> str:
    if not comparison_entries:
        return "<p class=\"empty-state\">Sem pares suficientes para montar o comparativo visual.</p>"
    rows = sorted(comparison_entries, key=lambda item: item["abs_delta"], reverse=True)[:10]
    max_value = max(max(item["spring"].p95_ms, item["python"].p95_ms) for item in rows)
    rendered = []
    for item in rows:
        rendered.append(
            f"""
            <div class="chart-row">
              <div class="chart-label">
                <strong>{html.escape(item["scenario"])}</strong>
                <span>{html.escape(truncate(item["endpoint"]))}</span>
              </div>
              <div class="chart-bars">
                <div class="bar-line">
                  <span class="series spring" style="width:{pct_width(item["spring"].p95_ms, max_value)}%"></span>
                  <em>Spring {fmt_ms(item["spring"].p95_ms)}</em>
                </div>
                <div class="bar-line">
                  <span class="series python" style="width:{pct_width(item["python"].p95_ms, max_value)}%"></span>
                  <em>Python {fmt_ms(item["python"].p95_ms)}</em>
                </div>
              </div>
              <div class="chart-delta {severity_for_delta(item["delta_p95"])}">{item["delta_p95"]:+.1f} ms</div>
            </div>
            """
        )
    return "".join(rendered)


def build_insight_list(insights: dict[str, object]) -> str:
    items: list[str] = []
    for entry in insights["best_spring"]:
        items.append(
            f"Python ficou {entry['delta_p95']:.1f} ms mais lento em <strong>{html.escape(entry['scenario'])}</strong> / {html.escape(truncate(entry['endpoint']))}."
        )
    for entry in insights["best_python"]:
        items.append(
            f"Python venceu por {abs(entry['delta_p95']):.1f} ms em <strong>{html.escape(entry['scenario'])}</strong> / {html.escape(truncate(entry['endpoint']))}."
        )
    for entry in insights["ties"]:
        items.append(
            f"Empate técnico em <strong>{html.escape(entry['scenario'])}</strong> / {html.escape(truncate(entry['endpoint']))}, com delta de {entry['delta_p95']:+.1f} ms."
        )
    for item in insights["p95_leaders"][:2]:
        items.append(
            f"O label <strong>{html.escape(truncate(item['label']))}</strong> concentrou um dos maiores p95: {fmt_ms(item['metric'].p95_ms)}."
        )
    if not items:
        items.append("Não houve pares comparáveis suficientes para produzir insights automáticos.")
    return "".join(f"<li>{item}</li>" for item in items[:8])


def build_payload_rows(insights: dict[str, object]) -> str:
    rows = insights["payload_leaders"]
    if not rows:
        return "<p class=\"empty-state\">Sem dados de payload para destacar.</p>"
    max_value = max(item["metric"].avg_bytes for item in rows)
    rendered = []
    for item in rows:
        stack_class = item["stack"].lower()
        rendered.append(
            f"""
            <div class="compact-row">
              <span>{html.escape(item["scenario"])} / {html.escape(truncate(item["label"]))}</span>
              <div class="bar-line">
                <span class="series {stack_class}" style="width:{pct_width(item["metric"].avg_bytes, max_value)}%"></span>
                <em>{fmt_bytes(item["metric"].avg_bytes)} em média</em>
              </div>
            </div>
            """
        )
    return "".join(rendered)


def build_p95_rows(insights: dict[str, object]) -> str:
    rows = insights["p95_leaders"]
    if not rows:
        return "<p class=\"empty-state\">Sem dados de p95 para destacar.</p>"
    max_value = max(item["metric"].p95_ms for item in rows)
    rendered = []
    for item in rows:
        stack_class = item["stack"].lower()
        rendered.append(
            f"""
            <div class="compact-row">
              <span>{html.escape(item["scenario"])} / {html.escape(truncate(item["label"]))}</span>
              <div class="bar-line">
                <span class="series {stack_class}" style="width:{pct_width(item["metric"].p95_ms, max_value)}%"></span>
                <em>{fmt_ms(item["metric"].p95_ms)}</em>
              </div>
            </div>
            """
        )
    return "".join(rendered)


def build_label_table(label_rows: list[list[str]]) -> str:
    return "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in label_rows
    )


def build_dashboard(
    variant: str,
    scenario_metrics: list[dict],
    label_metrics: list[dict],
    comparison_entries: list[dict],
    label_rows: list[list[str]],
) -> str:
    summary = build_variant_summary(variant, scenario_metrics)
    insights = build_dashboard_insights(comparison_entries, label_metrics, scenario_metrics)
    missing_pairs = insights["missing_pairs"]
    legend = """
    <div class="legend">
      <span><strong>p95</strong>: 95% das chamadas ficaram abaixo desse tempo.</span>
      <span><strong>Delta</strong>: positivo indica Python mais lento; negativo indica Python mais rápido.</span>
      <span><strong>Latency</strong>: tempo até o primeiro byte.</span>
      <span><strong>Connect</strong>: custo médio de abertura de conexão.</span>
    </div>
    """
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório JMeter {html.escape(variant)}</title>
  <style>
    :root {{
      --bg: #f3f6f8;
      --surface: #ffffff;
      --surface-alt: #e8eef2;
      --text: #13222b;
      --muted: #566771;
      --line: #d5dde3;
      --hero: linear-gradient(135deg, #0f2d3a 0%, #18465b 48%, #0d766e 100%);
      --spring: {STACK_COLORS["Spring"]};
      --python: {STACK_COLORS["Python"]};
      --other: {STACK_COLORS["Outro"]};
      --ok: #166534;
      --ok-soft: #dcfce7;
      --warning: #b45309;
      --warning-soft: #fef3c7;
      --critical: #b91c1c;
      --critical-soft: #fee2e2;
      --shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: radial-gradient(circle at top, #f9fbfc 0, var(--bg) 45%, #edf2f5 100%); color: var(--text); }}
    main {{ padding: 24px; max-width: 1440px; margin: 0 auto; }}
    .hero {{ padding: 32px 24px; background: var(--hero); color: #fff; }}
    .eyebrow {{ margin: 0 0 10px; text-transform: uppercase; letter-spacing: 0.18em; font-size: 12px; opacity: 0.8; }}
    h1 {{ margin: 0; font-size: clamp(28px, 5vw, 44px); line-height: 1.05; max-width: 900px; }}
    .hero-copy {{ max-width: 760px; color: rgba(255,255,255,0.84); font-size: 17px; line-height: 1.5; }}
    .hero-grid, .grid, .two-up, .mini-grid, .stat-strip {{ display: grid; gap: 16px; }}
    .hero-grid {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin-top: 24px; }}
    .hero-stat, .card, .panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); }}
    .hero-stat {{ padding: 18px; color: var(--text); }}
    .hero-stat span, .hero-stat small {{ display: block; color: var(--muted); }}
    .hero-stat strong {{ display: block; margin: 6px 0; font-size: 28px; color: #0b1720; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0 0; }}
    .legend span {{ background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 10px 12px; border-radius: 999px; font-size: 13px; }}
    .grid {{ grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); margin-top: 22px; }}
    .two-up {{ grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); margin-top: 22px; }}
    .card, .panel {{ padding: 22px; }}
    .panel {{ margin-top: 22px; }}
    .panel h2, .card h2 {{ margin: 0; font-size: 22px; line-height: 1.2; }}
    .panel p, .card p {{ color: var(--muted); }}
    .card-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }}
    .kicker {{ margin: 0 0 8px; color: #0d766e; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .badge, .stack-pill, .delta-pill {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 8px 12px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
    .badge.ok, .chart-delta.ok {{ background: var(--ok-soft); color: var(--ok); }}
    .badge.warning, .chart-delta.warning {{ background: var(--warning-soft); color: var(--warning); }}
    .badge.critical, .chart-delta.critical {{ background: var(--critical-soft); color: var(--critical); }}
    .stack-pill.spring {{ background: rgba(29, 78, 216, 0.12); color: var(--spring); }}
    .stack-pill.python {{ background: rgba(21, 128, 61, 0.12); color: var(--python); }}
    .delta-pill.spring-win {{ background: rgba(185, 28, 28, 0.12); color: var(--critical); }}
    .delta-pill.python-win {{ background: rgba(22, 101, 52, 0.12); color: var(--ok); }}
    .stat-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 18px 0 14px; }}
    .stat-strip div, .mini-grid div {{ background: var(--surface-alt); border-radius: 14px; padding: 12px; }}
    .stat-strip strong, .mini-grid strong {{ display: block; font-size: 20px; color: #0b1720; }}
    .stat-strip span, .mini-grid span {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }}
    .mini-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 14px; }}
    .meter {{ height: 12px; background: #dce5ea; border-radius: 999px; overflow: hidden; }}
    .meter span {{ display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, #0891b2, #22c55e); }}
    .footnote {{ margin: 12px 0 0; font-size: 13px; }}
    .winner-summary {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .winner-summary article {{ background: var(--surface-alt); border-radius: 16px; padding: 14px; }}
    .winner-summary strong {{ display: block; font-size: 28px; }}
    .winner-summary span {{ color: var(--muted); font-size: 13px; }}
    .winner-row, .chart-row, .compact-row {{ display: grid; gap: 14px; padding: 14px 0; border-bottom: 1px solid #edf2f5; }}
    .winner-row {{ grid-template-columns: minmax(180px, 1fr) minmax(320px, auto); align-items: center; }}
    .winner-row strong, .chart-label strong {{ display: block; margin-bottom: 4px; }}
    .winner-row span, .chart-label span {{ color: var(--muted); font-size: 14px; }}
    .winner-meta {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .chart-row {{ grid-template-columns: minmax(200px, 260px) 1fr 92px; align-items: center; }}
    .chart-bars {{ display: grid; gap: 8px; }}
    .bar-line {{ position: relative; height: 28px; background: #ebf1f4; border-radius: 999px; overflow: hidden; }}
    .series {{ display: block; height: 100%; }}
    .series.spring {{ background: linear-gradient(90deg, #60a5fa, var(--spring)); }}
    .series.python {{ background: linear-gradient(90deg, #4ade80, var(--python)); }}
    .series.outro {{ background: linear-gradient(90deg, #cbd5e1, var(--other)); }}
    .bar-line em {{ position: absolute; inset: 0 auto 0 12px; display: flex; align-items: center; font-style: normal; font-size: 13px; color: #102027; }}
    .chart-delta {{ justify-self: end; padding: 10px 12px; border-radius: 12px; font-weight: 700; }}
    .insight-list {{ margin: 16px 0 0; padding-left: 20px; }}
    .insight-list li {{ margin-bottom: 12px; color: var(--text); line-height: 1.45; }}
    .empty-state {{ margin: 8px 0 0; padding: 18px; background: var(--surface-alt); border-radius: 14px; }}
    .missing-pairs {{ margin-top: 14px; color: var(--muted); font-size: 14px; }}
    .explainer p {{ margin: 0 0 12px; color: var(--text); line-height: 1.55; }}
    .explain-list {{ margin-top: 14px; }}
    .explain-list p:last-child {{ margin-bottom: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; background: var(--surface); }}
    th, td {{ border: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; }}
    th {{ background: #e8eef2; position: sticky; top: 0; }}
    .table-wrap {{ overflow: auto; border-radius: 16px; border: 1px solid var(--line); }}
    @media (max-width: 960px) {{
      .winner-row, .chart-row {{ grid-template-columns: 1fr; }}
      .winner-meta {{ justify-content: flex-start; }}
      .chart-delta {{ justify-self: start; }}
      .mini-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 680px) {{
      main {{ padding: 18px; }}
      .hero {{ padding: 26px 18px; }}
      .stat-strip, .mini-grid, .winner-summary {{ grid-template-columns: 1fr; }}
      .grid, .two-up {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  {build_hero(summary)}
  <main>
    {legend}
    {build_plain_language_section()}
    <section class="grid">
      {build_scenario_cards(scenario_metrics)}
    </section>
    <section class="two-up">
      <section class="panel">
        <h2>Quem ganhou onde</h2>
        <p>Ranking dos endpoints comparáveis com maior diferença absoluta de p95.</p>
        {build_winner_panel(comparison_entries)}
      </section>
      <section class="panel">
        <h2>Insights automáticos</h2>
        <p>Leitura executiva dos sinais mais relevantes antes do detalhamento tabular.</p>
        <ul class="insight-list">{build_insight_list(insights)}</ul>
        <p class="missing-pairs">Cenários sem par comparável: {html.escape(", ".join(missing_pairs)) if missing_pairs else "nenhum"}.</p>
      </section>
    </section>
    <section class="panel">
      <h2>Comparativo visual de p95</h2>
      <p>Cada linha mostra Spring e Python lado a lado para o mesmo endpoint equivalente. Delta positivo indica Python mais lento.</p>
      {build_comparison_bars(comparison_entries)}
    </section>
    <section class="two-up">
      <section class="panel">
        <h2>Top payloads médios</h2>
        <p>Payload alto pode explicar parte do custo percebido em elapsed e latency.</p>
        {build_payload_rows(insights)}
      </section>
      <section class="panel">
        <h2>Top p95 por label</h2>
        <p>Ajuda a localizar rapidamente os labels mais caros da variante.</p>
        {build_p95_rows(insights)}
      </section>
    </section>
    <section class="panel">
      <h2>Detalhe por label</h2>
      <p>A tabela foi mantida como apoio operacional, com menor prioridade visual que os painéis de comparação e insights.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Cenário</th><th>Label</th><th>Stack</th><th>Operação</th><th>Total</th><th>Erro</th><th>Avg ms</th><th>p95 ms</th><th>p99 ms</th><th>Max ms</th><th>Latency avg</th><th>Connect avg</th><th>Bytes avg</th><th>Códigos</th></tr>
          </thead>
          <tbody>{build_label_table(label_rows)}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True, choices=["legacy", "simple_py"])
    args = parser.parse_args()

    results_dir = ROOT / "resultados" / args.variant
    report_dir = results_dir / "relatorio"
    report_dir.mkdir(parents=True, exist_ok=True)

    jtl_files = sorted(results_dir.glob("*/*.jtl"))
    if not jtl_files:
        raise SystemExit(f"Nenhum JTL encontrado em {results_dir}")

    scenario_metrics: list[dict] = []
    label_metrics: list[dict] = []
    label_rows: list[list[str]] = []
    warnings: list[str] = []
    error_counter: Counter[tuple[str, str, str]] = Counter()

    for path in jtl_files:
        rows, session_count = latest_run(read_jtl(path))
        scenario = path.parent.name
        metric = metric_for(rows)
        scenario_metrics.append({"name": scenario, "metric": metric})
        if session_count > 1:
            warnings.append(f"{scenario}: {session_count} execuções no mesmo JTL; somente a mais recente foi usada.")

        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[row["label"]].append(row)
            if row["success"].lower() != "true":
                error_counter[(scenario, row["label"], row["responseCode"])] += 1

        for label, samples in sorted(grouped.items()):
            metric_label = metric_for(samples)
            stack = stack_for(label)
            operation = operation_for(label)
            codes = Counter(sample["responseCode"] for sample in samples)
            label_metrics.append(
                {
                    "scenario": scenario,
                    "label": label,
                    "stack": stack,
                    "operation": operation,
                    "endpoint": comparable_endpoint_for(label),
                    "metric": metric_label,
                }
            )
            label_rows.append(
                [
                    scenario,
                    label,
                    stack,
                    operation,
                    str(metric_label.total),
                    fmt_pct(metric_label.error_pct),
                    fmt_ms_compact(metric_label.avg_ms),
                    fmt_ms_compact(metric_label.p95_ms),
                    fmt_ms_compact(metric_label.p99_ms),
                    str(metric_label.max_ms),
                    fmt_ms_compact(metric_label.avg_latency_ms),
                    fmt_ms_compact(metric_label.avg_connect_ms),
                    f"{metric_label.avg_bytes:.0f}",
                    json.dumps(dict(sorted(codes.items())), ensure_ascii=False),
                ]
            )

    comparison_entries = build_comparison_entries(label_metrics)
    comparison_rows = comparison_csv_rows(comparison_entries)

    write_csv(
        report_dir / "summary_by_label.csv",
        ["cenario", "label", "stack", "operacao", "total", "erro", "avg_ms", "p95_ms", "p99_ms", "max_ms", "latency_avg_ms", "connect_avg_ms", "bytes_avg", "codigos"],
        label_rows,
    )
    write_csv(
        report_dir / "comparison_spring_python.csv",
        ["cenario", "operacao", "endpoint", "p95_spring", "p95_python", "delta_p95", "mais_rapido"],
        comparison_rows,
    )
    (report_dir / "dashboard.html").write_text(
        build_dashboard(args.variant, scenario_metrics, label_metrics, comparison_entries, label_rows),
        encoding="utf-8",
    )

    summary_lines = [
        f"# Relatório JMeter da variante {args.variant}",
        "",
        "## Cenários processados",
        "",
    ]
    for item in scenario_metrics:
        metric = item["metric"]
        summary_lines.append(
            f"- `{item['name']}`: {SCENARIO_DESCRIPTIONS.get(item['name'], 'Sem descrição')}"
            f" Total={metric.total}, erro={metric.error_pct:.2f}%, p95={metric.p95_ms:.1f} ms."
        )

    summary_lines.extend(["", "## Avisos", ""])
    if warnings:
        summary_lines.extend(f"- {warning}" for warning in warnings)
    else:
        summary_lines.append("Nenhum aviso.")
    summary_lines.extend(["", "## Top erros", ""])
    if error_counter:
        for (scenario, label, code), total in error_counter.most_common(12):
            summary_lines.append(f"- `{scenario}` / `{label}` / `{code}`: {total} ocorrências")
    else:
        summary_lines.append("Sem erros registrados.")

    (report_dir / "relatorio_resultados.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Relatório gerado em {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
