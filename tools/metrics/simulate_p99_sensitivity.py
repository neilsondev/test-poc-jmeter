#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sample:
    row_number: int
    elapsed: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simula mudanças hipotéticas no elapsed de um label do JTL para analisar o impacto no p99, sem alterar o arquivo original."
    )
    parser.add_argument("--jtl", required=True, type=Path, help="Caminho do arquivo .jtl")
    parser.add_argument("--label", required=True, help="Label exato a analisar")
    parser.add_argument(
        "--change",
        action="append",
        default=[],
        help="Mudança hipotética no formato row_number=new_elapsed. Pode repetir.",
    )
    parser.add_argument(
        "--show-tail",
        type=int,
        default=12,
        help="Quantidade de maiores elapsed para mostrar. Default: 12.",
    )
    return parser.parse_args()


def read_label_samples(jtl_path: Path, label: str) -> list[Sample]:
    samples: list[Sample] = []
    with jtl_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            if row.get("label") != label:
                continue
            samples.append(Sample(row_number=row_number, elapsed=int(row["elapsed"])))
    return samples


def percentile_interpolated(values: list[int], pct: float) -> tuple[float, int, int, int, int]:
    ordered = sorted(values)
    n = len(ordered)
    rank = (n - 1) * pct
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    lower_val = ordered[lower_idx]
    upper_val = ordered[upper_idx]
    weight = rank - lower_idx
    result = lower_val * (1 - weight) + upper_val * weight
    return result, lower_idx, upper_idx, lower_val, upper_val


def parse_changes(change_args: list[str]) -> dict[int, int]:
    changes: dict[int, int] = {}
    for item in change_args:
        if "=" not in item:
            raise SystemExit(f"Formato inválido em --change: {item}. Use row_number=new_elapsed")
        raw_row, raw_elapsed = item.split("=", 1)
        row_number = int(raw_row.strip())
        new_elapsed = int(raw_elapsed.strip())
        if new_elapsed < 0:
            raise SystemExit(f"Novo elapsed não pode ser negativo: {item}")
        changes[row_number] = new_elapsed
    return changes


def apply_changes(samples: list[Sample], changes: dict[int, int]) -> list[Sample]:
    changed_rows = set(changes)
    sample_rows = {sample.row_number for sample in samples}
    missing = sorted(changed_rows - sample_rows)
    if missing:
        missing_text = ", ".join(str(row) for row in missing)
        raise SystemExit(f"As linhas não pertencem ao label informado: {missing_text}")

    updated = []
    for sample in samples:
        if sample.row_number in changes:
            updated.append(Sample(row_number=sample.row_number, elapsed=changes[sample.row_number]))
        else:
            updated.append(sample)
    return updated


def print_summary(title: str, samples: list[Sample], tail_size: int) -> None:
    values = [sample.elapsed for sample in samples]
    p99, lower_idx, upper_idx, lower_val, upper_val = percentile_interpolated(values, 0.99)
    ordered = sorted(samples, key=lambda sample: sample.elapsed)
    tail = ordered[-tail_size:]

    print(title)
    print(f"amostras={len(samples)}")
    print(f"p99_interpolado={p99:.2f}")
    print(
        f"fronteira_p99=idx[{lower_idx},{upper_idx}] valores[{lower_val},{upper_val}]"
    )
    print("maiores_elapsed:")
    for sample in tail:
        print(f"  linha={sample.row_number} elapsed={sample.elapsed}")
    print()


def main() -> None:
    args = parse_args()
    samples = read_label_samples(args.jtl, args.label)
    if not samples:
        raise SystemExit(f"Nenhuma amostra encontrada para o label: {args.label}")

    print_summary("original", samples, args.show_tail)

    changes = parse_changes(args.change)
    if not changes:
        return

    updated_samples = apply_changes(samples, changes)
    print("mudancas_aplicadas:")
    for row_number, new_elapsed in sorted(changes.items()):
        old_elapsed = next(sample.elapsed for sample in samples if sample.row_number == row_number)
        print(f"  linha={row_number} {old_elapsed}->{new_elapsed}")
    print()

    print_summary("simulado", updated_samples, args.show_tail)


if __name__ == "__main__":
    main()
