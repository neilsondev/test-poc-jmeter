#!/usr/bin/env python3
"""Gera uma copia temporaria de um plano JMeter filtrando Thread Groups por stack."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


STACK_PREFIXES = {
    "spring": "TG_SPRING_",
    "python": "TG_PYTHON_",
}


def target_matches_group(target: str, testname: str) -> bool:
    if target == "both":
        return True
    prefix = STACK_PREFIXES[target]
    if testname.startswith(prefix):
        return True
    other_prefix = STACK_PREFIXES["python" if target == "spring" else "spring"]
    if testname.startswith(other_prefix):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", required=True, choices=["spring", "python", "both"])
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree = ET.parse(input_path)
    root = tree.getroot()

    for element in root.iter():
        if element.get("testclass") != "ThreadGroup":
            continue
        testname = element.get("testname", "")
        if not testname.startswith(("TG_SPRING_", "TG_PYTHON_")):
            continue
        element.set("enabled", "true" if target_matches_group(args.target, testname) else "false")

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Erro ao filtrar JMX: {exc}", file=sys.stderr)
        raise SystemExit(1)
