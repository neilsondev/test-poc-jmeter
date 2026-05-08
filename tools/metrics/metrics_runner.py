import argparse
import csv
import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev

import psutil


stop_event = threading.Event()
metrics = []
cpu_snapshots = {}


def now():
    return datetime.now().isoformat(timespec="seconds")


def mb(bytes_value):
    return round(bytes_value / 1024 / 1024, 2)


def process_matches(proc, terms):
    try:
        cmdline = " ".join(proc.cmdline())
        name = proc.name()
        full_text = f"{name} {cmdline}".lower()
        return all(term.lower() in full_text for term in terms)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def find_matching_processes(match_terms):
    found = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        if process_matches(proc, match_terms):
            found.append(proc)
    return found


def find_process_tree(root_pid):
    try:
        root = psutil.Process(root_pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return processes


def resolve_target_processes(target):
    pid = target.get("pid")
    if pid is not None:
        return find_process_tree(int(pid))
    return find_matching_processes(target["match"])


def cpu_snapshot_key(target):
    return target["name"]


def process_identity(proc):
    try:
        return (proc.pid, proc.create_time())
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def process_cpu_seconds(proc):
    cpu_times = proc.cpu_times()
    return cpu_times.user + cpu_times.system


def compute_cpu_percent(target, procs):
    snapshot_key = cpu_snapshot_key(target)
    current_wall = time.time()
    current_cpu = {}

    for proc in procs:
        try:
            identity = process_identity(proc)
            if identity is None:
                continue
            current_cpu[identity] = process_cpu_seconds(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    previous = cpu_snapshots.get(snapshot_key)
    cpu_snapshots[snapshot_key] = {
        "wall_time": current_wall,
        "cpu_seconds": current_cpu,
    }

    if not previous:
        return 0.0

    elapsed_wall = current_wall - previous["wall_time"]
    if elapsed_wall <= 0:
        return 0.0

    total_delta_cpu = 0.0
    for identity, cpu_seconds in current_cpu.items():
        previous_cpu = previous["cpu_seconds"].get(identity)
        if previous_cpu is None:
            continue
        total_delta_cpu += max(0.0, cpu_seconds - previous_cpu)

    return round((total_delta_cpu / elapsed_wall) * 100, 2)


def collect_metrics_for_target(target):
    procs = resolve_target_processes(target)

    total_rss = 0
    total_vms = 0
    total_threads = 0
    pids = []

    cpu_percent = compute_cpu_percent(target, procs)

    for proc in procs:
        try:
            mem = proc.memory_info()
            total_rss += mem.rss
            total_vms += mem.vms
            total_threads += proc.num_threads()
            pids.append(str(proc.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return {
        "timestamp": now(),
        "target": target["name"],
        "match": target_descriptor(target),
        "pids": "|".join(sorted(pids, key=int)),
        "process_count": len(pids),
        "cpu_percent": cpu_percent,
        "rss_mb": mb(total_rss),
        "vms_mb": mb(total_vms),
        "threads": total_threads,
    }


def target_descriptor(target):
    if "pid" in target:
        return f"pid_tree:{target['pid']}"
    return " ".join(target["match"])


def prime_cpu_counters(process_targets):
    cpu_snapshots.clear()
    for target in process_targets:
        compute_cpu_percent(target, resolve_target_processes(target))


def monitor_loop(scenario_name, process_targets, interval_seconds):
    prime_cpu_counters(process_targets)
    time.sleep(interval_seconds)

    while not stop_event.is_set():
        for target in process_targets:
            row = collect_metrics_for_target(target)
            row["scenario"] = scenario_name
            metrics.append(row)

        time.sleep(interval_seconds)


def run_command(command, output_log_path):
    with open(output_log_path, "w", encoding="utf-8") as log:
        log.write(f"Command: {command}\n")
        log.write(f"Started at: {now()}\n\n")
        log.flush()

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid,
        )

        try:
            return_code = process.wait()
        except KeyboardInterrupt:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            raise

        log.write(f"\nFinished at: {now()}\n")
        log.write(f"Exit code: {return_code}\n")

    return return_code


def write_csv(csv_path):
    fieldnames = [
        "timestamp",
        "scenario",
        "target",
        "match",
        "pids",
        "process_count",
        "cpu_percent",
        "rss_mb",
        "vms_mb",
        "threads",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics)


def percentile(values, pct):
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 2)

    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    result = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(result, 2)


def safe_stdev(values):
    if len(values) < 2:
        return 0.0
    return round(stdev(values), 2)


def coeff_var(values):
    if not values:
        return 0.0
    avg = mean(values)
    if avg == 0:
        return 0.0
    spread = stdev(values) if len(values) >= 2 else 0.0
    return round((spread / avg) * 100, 2)


def summarize():
    grouped = {}

    for row in metrics:
        key = (row["scenario"], row["target"])
        if key not in grouped:
            grouped[key] = {
                "cpu": [],
                "rss": [],
                "vms": [],
                "threads": [],
                "process_count": [],
            }

        grouped[key]["cpu"].append(row["cpu_percent"])
        grouped[key]["rss"].append(row["rss_mb"])
        grouped[key]["vms"].append(row["vms_mb"])
        grouped[key]["threads"].append(row["threads"])
        grouped[key]["process_count"].append(row["process_count"])

    rows = []
    for (scenario, target), values in grouped.items():
        rows.append(
            {
                "scenario": scenario,
                "target": target,
                "samples": len(values["cpu"]),
                "min_cpu_percent": round(min(values["cpu"]), 2),
                "avg_cpu_percent": round(mean(values["cpu"]), 2),
                "median_cpu_percent": round(median(values["cpu"]), 2),
                "p95_cpu_percent": percentile(values["cpu"], 0.95),
                "p99_cpu_percent": percentile(values["cpu"], 0.99),
                "max_cpu_percent": round(max(values["cpu"]), 2),
                "stdev_cpu_percent": safe_stdev(values["cpu"]),
                "cv_cpu_percent": coeff_var(values["cpu"]),
                "min_rss_mb": round(min(values["rss"]), 2),
                "avg_rss_mb": round(mean(values["rss"]), 2),
                "median_rss_mb": round(median(values["rss"]), 2),
                "p95_rss_mb": percentile(values["rss"], 0.95),
                "p99_rss_mb": percentile(values["rss"], 0.99),
                "max_rss_mb": round(max(values["rss"]), 2),
                "rss_range_mb": round(max(values["rss"]) - min(values["rss"]), 2),
                "stdev_rss_mb": safe_stdev(values["rss"]),
                "cv_rss_mb": coeff_var(values["rss"]),
                "min_vms_mb": round(min(values["vms"]), 2),
                "median_vms_mb": round(median(values["vms"]), 2),
                "p95_vms_mb": percentile(values["vms"], 0.95),
                "avg_vms_mb": round(mean(values["vms"]), 2),
                "max_vms_mb": round(max(values["vms"]), 2),
                "vms_range_mb": round(max(values["vms"]) - min(values["vms"]), 2),
                "stdev_vms_mb": safe_stdev(values["vms"]),
                "min_threads": min(values["threads"]),
                "avg_threads": round(mean(values["threads"]), 2),
                "median_threads": round(median(values["threads"]), 2),
                "max_threads": max(values["threads"]),
                "min_process_count": min(values["process_count"]),
                "avg_process_count": round(mean(values["process_count"]), 2),
                "max_process_count": max(values["process_count"]),
            }
        )

    return rows


def write_report(report_path, scenario, command, return_code):
    summary_rows = summarize()

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"# Relatório de Consumo - {scenario}\n\n")
        file.write(f"Gerado em: `{now()}`\n\n")
        file.write("Comando monitorado:\n\n")
        file.write(f"```bash\n{command}\n```\n\n")
        file.write(f"Código de saída: `{return_code}`\n\n")

        file.write("## Resumo\n\n")
        file.write("| Cenário | Alvo | Amostras | CPU média % | CPU dp | CPU CV % | CPU p95 | CPU pico % | RSS média MB | RSS dp | RSS CV % | RSS p95 | RSS pico MB |\n")
        file.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

        for row in summary_rows:
            file.write(
                f"| {row['scenario']} "
                f"| {row['target']} "
                f"| {row['samples']} "
                f"| {row['avg_cpu_percent']} "
                f"| {row['stdev_cpu_percent']} "
                f"| {row['cv_cpu_percent']} "
                f"| {row['p95_cpu_percent']} "
                f"| {row['max_cpu_percent']} "
                f"| {row['avg_rss_mb']} "
                f"| {row['stdev_rss_mb']} "
                f"| {row['cv_rss_mb']} "
                f"| {row['p95_rss_mb']} "
                f"| {row['max_rss_mb']} "
                "|\n"
            )

        if not summary_rows:
            file.write("| - | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |\n")

        file.write("\n## Leitura focada em memória\n\n")
        for row in summary_rows:
            file.write(
                f"- `{row['target']}`: RSS médio `{row['avg_rss_mb']}` MB, p95 `{row['p95_rss_mb']}` MB, pico `{row['max_rss_mb']}` MB, faixa `{row['rss_range_mb']}` MB.\n"
            )
            file.write(
                f"- `{row['target']}`: VMS médio `{row['avg_vms_mb']}` MB, pico `{row['max_vms_mb']}` MB, faixa `{row['vms_range_mb']}` MB, threads pico `{row['max_threads']}`.\n"
            )

        file.write("\n## Explicação simples dos termos\n\n")
        file.write("- **RSS**: é a memória que o processo realmente manteve ocupada na RAM. Se você quer entender consumo real de memória, este é o número mais importante.\n")
        file.write("- **VMS**: é a memória virtual reservada pelo processo. Ela pode parecer alta, principalmente em Java, sem significar que tudo isso está sendo usado de verdade na RAM.\n")
        file.write("- **CPU %**: mostra o quanto o processo usou do processador entre uma coleta e outra. Pode passar de 100% quando o programa usa mais de um núcleo ao mesmo tempo.\n")
        file.write("- **p95**: indica um valor que quase sempre foi respeitado durante a execução. Exemplo: se o RSS p95 foi 500 MB, significa que em 95% das amostras a memória ficou até esse valor.\n")
        file.write("- **Pico**: é o maior valor observado durante toda a rodada.\n")
        file.write("- **Faixa**: é a diferença entre o menor e o maior valor coletado. Ajuda a enxergar se o consumo ficou estável ou cresceu muito ao longo do teste.\n")
        file.write("- **Threads**: são linhas de execução internas do processo. Em aplicações Java isso costuma ser útil para observar aumento de atividade interna.\n")
        file.write("- **Processos**: quantidade de processos ativos somados naquele alvo, incluindo filhos do processo principal.\n")

        file.write("\n## Detalhamento estatístico\n\n")
        for row in summary_rows:
            file.write(f"### {row['target']}\n\n")
            file.write("| Métrica | Mín | Média | Mediana | p95 | p99 | Máx | DP | CV % |\n")
            file.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
            file.write(
                f"| CPU % | {row['min_cpu_percent']} | {row['avg_cpu_percent']} | {row['median_cpu_percent']} | {row['p95_cpu_percent']} | {row['p99_cpu_percent']} | {row['max_cpu_percent']} | {row['stdev_cpu_percent']} | {row['cv_cpu_percent']} |\n"
            )
            file.write(
                f"| RSS MB | {row['min_rss_mb']} | {row['avg_rss_mb']} | {row['median_rss_mb']} | {row['p95_rss_mb']} | {row['p99_rss_mb']} | {row['max_rss_mb']} | {row['stdev_rss_mb']} | {row['cv_rss_mb']} |\n"
            )
            file.write(
                f"| VMS MB | {row['min_vms_mb']} | {row['avg_vms_mb']} | {row['median_vms_mb']} | {row['p95_vms_mb']} | - | {row['max_vms_mb']} | {row['stdev_vms_mb']} | - |\n"
            )
            file.write(
                f"| Threads | {row['min_threads']} | {row['avg_threads']} | {row['median_threads']} | - | - | {row['max_threads']} | - | - |\n"
            )
            file.write(
                f"| Processos | {row['min_process_count']} | {row['avg_process_count']} | - | - | - | {row['max_process_count']} | - | - |\n\n"
            )

        file.write("\n## Interpretação rápida\n\n")
        file.write("- Para avaliar **consumo real de memória**, priorize `RSS médio`, `RSS p95` e `RSS pico`.\n")
        file.write("- Se a **faixa de RSS** for pequena, o consumo ficou mais estável ao longo da execução.\n")
        file.write("- Se o **VMS** estiver muito alto, isso não significa sozinho problema de memória; confirme sempre com o RSS.\n")
        file.write("- `DP` e `CV %` ajudam a entender se o comportamento foi estável ou oscilou bastante durante a rodada.\n")
        file.write("- `p95` e `p99` ajudam a enxergar valores altos recorrentes, sem depender apenas de um pico isolado.\n")


def load_targets_from_tsv(path):
    targets = []
    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue
            name, pid = line.split("\t", 1)
            targets.append({"name": name, "pid": int(pid)})
    return targets


def load_scenario_from_config(config_path, scenario_name):
    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    all_scenarios = config["scenarios"]
    scenario = next((item for item in all_scenarios if item["name"] == scenario_name), None)
    if not scenario:
        raise ValueError(f"Cenário não encontrado: {scenario_name}")

    return {
        "interval": config.get("monitor_interval_seconds", 1),
        "command": scenario["command"],
        "targets": scenario["processes"],
    }


def install_signal_handlers():
    def handle_stop(signum, _frame):
        print(f"[{now()}] Sinal recebido: {signum}. Encerrando monitoramento...")
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)


def monitor_targets(scenario_name, process_targets, interval_seconds, results_dir, command, run_command_mode):
    global metrics

    results_dir.mkdir(parents=True, exist_ok=True)
    metrics = []
    stop_event.clear()
    install_signal_handlers()

    print(f"[{now()}] Iniciando monitoramento do cenário: {scenario_name}")
    monitor_thread = threading.Thread(
        target=monitor_loop,
        args=(scenario_name, process_targets, interval_seconds),
        daemon=True,
    )
    monitor_thread.start()

    return_code = 0
    log_path = results_dir / "test_command.log"

    try:
        if run_command_mode:
            print(f"[{now()}] Executando comando do teste...")
            return_code = run_command(command, log_path)
        else:
            with open(log_path, "w", encoding="utf-8") as log:
                log.write(f"Command: {command}\n")
                log.write(f"Started at: {now()}\n\n")
            while not stop_event.is_set():
                time.sleep(interval_seconds)
    finally:
        print(f"[{now()}] Parando monitoramento...")
        stop_event.set()
        monitor_thread.join(timeout=interval_seconds + 2)
        if not run_command_mode:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(f"Finished at: {now()}\n")
                log.write(f"Exit code: {return_code}\n")

    csv_path = results_dir / "metrics.csv"
    report_path = results_dir / "report.md"
    write_csv(csv_path)
    write_report(report_path, scenario_name, command, return_code)

    print()
    print("Finalizado.")
    print(f"CSV: {csv_path}")
    print(f"Relatório: {report_path}")
    print(f"Log do comando: {log_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--interval", type=int, default=1)
    parser.add_argument("--command", default="monitor-only")
    parser.add_argument("--config")
    parser.add_argument("--targets-file")
    args = parser.parse_args()

    if not args.config and not args.targets_file:
        parser.error("Informe --config ou --targets-file.")
    if args.config and args.targets_file:
        parser.error("Use apenas um entre --config e --targets-file.")

    return args


def main():
    args = parse_args()
    results_dir = Path(args.results_dir)

    if args.targets_file:
        targets = load_targets_from_tsv(args.targets_file)
        monitor_targets(
            scenario_name=args.scenario,
            process_targets=targets,
            interval_seconds=args.interval,
            results_dir=results_dir,
            command=args.command,
            run_command_mode=False,
        )
        return

    scenario_data = load_scenario_from_config(args.config, args.scenario)
    monitor_targets(
        scenario_name=args.scenario,
        process_targets=scenario_data["targets"],
        interval_seconds=scenario_data["interval"],
        results_dir=results_dir,
        command=scenario_data["command"],
        run_command_mode=True,
    )


if __name__ == "__main__":
    main()
