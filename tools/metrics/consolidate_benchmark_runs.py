#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_ROOT = ROOT / "resultados"
DEFAULT_OUTPUT_ROOT = ROOT / "tools" / "metrics" / "campaign_reports"
Z_95 = 1.96


def slugify(value: str) -> str:
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {" ", "_", "-"}:
            cleaned.append("-")
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolida rodadas do run_benchmark_cycle.sh agrupadas por label."
    )
    parser.add_argument("--label", required=True, help="Label da campanha, por exemplo suite-load-maio-2026.")
    parser.add_argument("--run-flow", default="suite+load", help="Fluxo esperado das rodadas. Default: suite+load.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def label_matches(metadata: dict, run_dir: Path, expected_label: str) -> bool:
    expected_slug = slugify(expected_label)
    metadata_label = str(metadata.get("label", "")).strip()
    if metadata_label:
        return slugify(metadata_label) == expected_slug
    return run_dir.name.endswith(expected_slug)


def find_campaign_runs(results_root: Path, label: str, run_flow: str) -> list[dict]:
    runs = []
    for variant_dir in sorted(path for path in results_root.iterdir() if path.is_dir()):
        for run_dir in sorted(path for path in variant_dir.iterdir() if path.is_dir()):
            metadata_path = run_dir / "metadata.json"
            if not metadata_path.exists():
                continue

            metadata = read_json(metadata_path)
            if metadata.get("run_flow") != run_flow:
                continue
            if not label_matches(metadata, run_dir, label):
                continue

            runs.append(
                {
                    "variant": metadata.get("variant", variant_dir.name),
                    "run_id": metadata.get("run_id", run_dir.name),
                    "label": metadata.get("label", label),
                    "status": metadata.get("status", "unknown"),
                    "started_at": metadata.get("started_at", ""),
                    "ended_at": metadata.get("ended_at", ""),
                    "api_workers": metadata.get("api_workers", 0),
                    "results_dir": run_dir,
                    "metadata": metadata,
                }
            )
    return runs


def to_float(value: str) -> float:
    normalized = value.strip().replace("%", "")
    return float(normalized) if normalized else 0.0


def safe_stdev(values: list[float]) -> float:
    return stdev(values) if len(values) >= 2 else 0.0


def confidence_interval_95(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    avg = mean(values)
    if len(values) < 2:
        return avg, avg
    margin = Z_95 * safe_stdev(values) / math.sqrt(len(values))
    return avg - margin, avg + margin


def summarize_numeric(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "n": 0,
            "min": 0.0,
            "avg": 0.0,
            "median": 0.0,
            "max": 0.0,
            "stdev": 0.0,
            "cv_pct": 0.0,
            "ci95_low": 0.0,
            "ci95_high": 0.0,
        }

    avg = mean(values)
    spread = safe_stdev(values)
    ci_low, ci_high = confidence_interval_95(values)
    return {
        "n": len(values),
        "min": min(values),
        "avg": avg,
        "median": median(values),
        "max": max(values),
        "stdev": spread,
        "cv_pct": (spread / avg * 100) if avg else 0.0,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
    }


def load_jmeter_rows(run: dict) -> list[dict]:
    summary_path = run["results_dir"] / "relatorio" / "summary_by_label.csv"
    if not summary_path.exists():
        return []

    rows = []
    for row in read_csv(summary_path):
        item = dict(row)
        item["variant"] = run["variant"]
        item["run_id"] = run["run_id"]
        item["campaign_label"] = run["label"]
        rows.append(item)
    return rows


def load_metrics_rows(run: dict) -> list[dict]:
    metrics_path = run["results_dir"] / "metricas" / "metrics.csv"
    if not metrics_path.exists():
        return []

    rows = []
    for row in read_csv(metrics_path):
        item = dict(row)
        item["variant"] = run["variant"]
        item["run_id"] = run["run_id"]
        item["campaign_label"] = run["label"]
        rows.append(item)
    return rows


def aggregate_jmeter(runs: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for run in runs:
        for row in load_jmeter_rows(run):
            key = (
                row["variant"],
                row["cenario"],
                row["stack"],
                row["operacao"],
                row["label"],
            )
            grouped[key].append(row)

    aggregated = []
    for key, rows in sorted(grouped.items()):
        variant, scenario, stack, operation, label = key
        metrics_map = {
            "total": [to_float(row["total"]) for row in rows],
            "erro_pct": [to_float(row["erro"]) for row in rows],
            "avg_ms": [to_float(row["avg_ms"]) for row in rows],
            "p95_ms": [to_float(row["p95_ms"]) for row in rows],
            "p99_ms": [to_float(row["p99_ms"]) for row in rows],
            "max_ms": [to_float(row["max_ms"]) for row in rows],
            "latency_avg_ms": [to_float(row["latency_avg_ms"]) for row in rows],
            "connect_avg_ms": [to_float(row["connect_avg_ms"]) for row in rows],
            "bytes_avg": [to_float(row["bytes_avg"]) for row in rows],
        }

        summary = {
            "variant": variant,
            "scenario": scenario,
            "stack": stack,
            "operation": operation,
            "label": label,
            "runs": len(rows),
        }

        for field, values in metrics_map.items():
            stats = summarize_numeric(values)
            summary[f"{field}_avg"] = stats["avg"]
            summary[f"{field}_median"] = stats["median"]
            summary[f"{field}_min"] = stats["min"]
            summary[f"{field}_max"] = stats["max"]
            summary[f"{field}_stdev"] = stats["stdev"]
            summary[f"{field}_cv_pct"] = stats["cv_pct"]
            summary[f"{field}_ci95_low"] = stats["ci95_low"]
            summary[f"{field}_ci95_high"] = stats["ci95_high"]

        aggregated.append(summary)

    return aggregated


def summarize_metrics_run(rows: list[dict]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        target = row["target"]
        grouped[target]["cpu_percent"].append(to_float(row["cpu_percent"]))
        grouped[target]["rss_mb"].append(to_float(row["rss_mb"]))
        grouped[target]["vms_mb"].append(to_float(row["vms_mb"]))
        grouped[target]["threads"].append(to_float(row["threads"]))
        grouped[target]["process_count"].append(to_float(row["process_count"]))

    run_summary = {}
    for target, metrics in grouped.items():
        run_summary[target] = {
            "avg_cpu_percent": mean(metrics["cpu_percent"]) if metrics["cpu_percent"] else 0.0,
            "max_cpu_percent": max(metrics["cpu_percent"], default=0.0),
            "avg_rss_mb": mean(metrics["rss_mb"]) if metrics["rss_mb"] else 0.0,
            "max_rss_mb": max(metrics["rss_mb"], default=0.0),
            "avg_vms_mb": mean(metrics["vms_mb"]) if metrics["vms_mb"] else 0.0,
            "max_vms_mb": max(metrics["vms_mb"], default=0.0),
            "avg_threads": mean(metrics["threads"]) if metrics["threads"] else 0.0,
            "max_threads": max(metrics["threads"], default=0.0),
            "avg_process_count": mean(metrics["process_count"]) if metrics["process_count"] else 0.0,
            "max_process_count": max(metrics["process_count"], default=0.0),
        }
    return run_summary


def aggregate_process_metrics(runs: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)
    for run in runs:
        metrics_rows = load_metrics_rows(run)
        if not metrics_rows:
            continue
        per_target = summarize_metrics_run(metrics_rows)
        for target, summary in per_target.items():
            grouped[(run["variant"], target)].append(summary)

    aggregated = []
    for key, rows in sorted(grouped.items()):
        variant, target = key
        summary = {"variant": variant, "target": target, "runs": len(rows)}
        fields = [
            "avg_cpu_percent",
            "max_cpu_percent",
            "avg_rss_mb",
            "max_rss_mb",
            "avg_vms_mb",
            "max_vms_mb",
            "avg_threads",
            "max_threads",
            "avg_process_count",
            "max_process_count",
        ]
        for field in fields:
            values = [row[field] for row in rows]
            stats = summarize_numeric(values)
            summary[f"{field}_avg"] = stats["avg"]
            summary[f"{field}_median"] = stats["median"]
            summary[f"{field}_min"] = stats["min"]
            summary[f"{field}_max"] = stats["max"]
            summary[f"{field}_stdev"] = stats["stdev"]
            summary[f"{field}_cv_pct"] = stats["cv_pct"]
            summary[f"{field}_ci95_low"] = stats["ci95_low"]
            summary[f"{field}_ci95_high"] = stats["ci95_high"]
        aggregated.append(summary)

    return aggregated


def write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    return f"{value:.2f}"


def build_report(
    path: Path,
    campaign_label: str,
    run_flow: str,
    runs: list[dict],
    jmeter_summary: list[dict],
    process_summary: list[dict],
) -> None:
    variants = sorted({run["variant"] for run in runs})
    lines = [
        f"# Consolidado da campanha `{campaign_label}`",
        "",
        f"- Fluxo esperado: `{run_flow}`",
        f"- Total de rodadas encontradas: `{len(runs)}`",
        f"- Variantes encontradas: `{', '.join(variants) if variants else 'nenhuma'}`",
        "",
        "## Rodadas incluídas",
        "",
        "| Variante | Run ID | Status | API workers | Início | Fim |",
        "|---|---|---|---:|---|---|",
    ]

    for run in runs:
        lines.append(
            f"| {run['variant']} | {run['run_id']} | {run['status']} | {run['api_workers']} | {run['started_at']} | {run['ended_at']} |"
        )

    lines.extend(
        [
            "",
            "## Como ler",
            "",
            "- As estatísticas abaixo são calculadas entre rodadas completas da mesma campanha, não entre amostras internas de uma única execução.",
            "- `DP` é o desvio padrão entre rodadas.",
            "- `CV %` mostra a variabilidade relativa; valores menores indicam maior estabilidade entre execuções.",
            "- `IC95%` é o intervalo de confiança aproximado da média entre rodadas.",
            "",
            "## JMeter consolidado",
            "",
            "| Variante | Cenário | Stack | Label | Rodadas | p95 médio | p95 DP | p95 CV % | p95 IC95% | erro médio % | total médio |",
            "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|",
        ]
    )

    for row in jmeter_summary:
        lines.append(
            f"| {row['variant']} | {row['scenario']} | {row['stack']} | {row['label']} | {row['runs']} | "
            f"{fmt(row['p95_ms_avg'])} | {fmt(row['p95_ms_stdev'])} | {fmt(row['p95_ms_cv_pct'])} | "
            f"{fmt(row['p95_ms_ci95_low'])} a {fmt(row['p95_ms_ci95_high'])} | "
            f"{fmt(row['erro_pct_avg'])} | {fmt(row['total_avg'])} |"
        )

    if not jmeter_summary:
        lines.append("| - | - | - | - | 0 | 0.00 | 0.00 | 0.00 | 0.00 a 0.00 | 0.00 | 0.00 |")

    lines.extend(
        [
            "",
            "## Métricas de processo consolidadas",
            "",
            "| Variante | Alvo | Rodadas | RSS médio das rodadas | RSS pico médio | CPU média das rodadas | CPU pico médio | RSS CV % | CPU CV % |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for row in process_summary:
        lines.append(
            f"| {row['variant']} | {row['target']} | {row['runs']} | "
            f"{fmt(row['avg_rss_mb_avg'])} | {fmt(row['max_rss_mb_avg'])} | "
            f"{fmt(row['avg_cpu_percent_avg'])} | {fmt(row['max_cpu_percent_avg'])} | "
            f"{fmt(row['avg_rss_mb_cv_pct'])} | {fmt(row['avg_cpu_percent_cv_pct'])} |"
        )

    if not process_summary:
        lines.append("| - | - | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |")

    lines.extend(
        [
            "",
            "## Observações",
            "",
            "- Para campanha `suite+load`, compare as rodadas apenas quando os parâmetros operacionais forem equivalentes: workers, reset, seed e carga JMeter.",
            "- Se alguma rodada não tiver pasta `metricas/`, ela ainda entra no consolidado de JMeter, mas fica fora do consolidado de processo.",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    campaign_label = args.label
    runs = find_campaign_runs(args.results_root, campaign_label, args.run_flow)
    if not runs:
        raise SystemExit(
            f"Nenhuma rodada encontrada para label '{campaign_label}' com run_flow '{args.run_flow}'."
        )

    output_dir = args.output_root / slugify(campaign_label)
    output_dir.mkdir(parents=True, exist_ok=True)

    runs_index_headers = [
        "variant",
        "run_id",
        "label",
        "status",
        "started_at",
        "ended_at",
        "api_workers",
        "results_dir",
    ]
    runs_index_rows = [
        {
            "variant": run["variant"],
            "run_id": run["run_id"],
            "label": run["label"],
            "status": run["status"],
            "started_at": run["started_at"],
            "ended_at": run["ended_at"],
            "api_workers": run["api_workers"],
            "results_dir": str(run["results_dir"]),
        }
        for run in runs
    ]

    jmeter_summary = aggregate_jmeter(runs)
    process_summary = aggregate_process_metrics(runs)

    write_csv(output_dir / "runs_index.csv", runs_index_headers, runs_index_rows)
    if jmeter_summary:
        write_csv(output_dir / "jmeter_campaign_summary.csv", list(jmeter_summary[0].keys()), jmeter_summary)
    if process_summary:
        write_csv(output_dir / "process_metrics_campaign_summary.csv", list(process_summary[0].keys()), process_summary)

    build_report(
        output_dir / "campaign_report.md",
        campaign_label=campaign_label,
        run_flow=args.run_flow,
        runs=runs,
        jmeter_summary=jmeter_summary,
        process_summary=process_summary,
    )

    print(f"Campanha consolidada em: {output_dir}")


if __name__ == "__main__":
    main()
