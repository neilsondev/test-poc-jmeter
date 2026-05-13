#!/usr/bin/env python3
"""Valida a massa da variante simple_py usada pelo JMeter."""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
SPRING_CSV = ROOT / "data" / "simple_py" / "spring_read_ids.csv"
PYTHON_CSV = ROOT / "data" / "simple_py" / "python_read_ids.csv"
SPRING_BASE_URL = os.getenv("SPRING_VALIDATION_BASE_URL", "http://localhost:8080").rstrip("/")
PYTHON_BASE_URL = os.getenv("PYTHON_VALIDATION_BASE_URL", "http://localhost:8000").rstrip("/")
VALIDATION_TARGET = os.getenv("VALIDATION_TARGET", "both").strip().lower()


def request_json(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def assert_status(status: int, payload: dict, url: str, expected: int) -> None:
    if status != expected:
        raise RuntimeError(f"Falha em {url}: esperado {expected}, recebido {status}, payload={payload}")


def validate_spring() -> None:
    with SPRING_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            urls = [
                f"{SPRING_BASE_URL}/courses",
                f"{SPRING_BASE_URL}/courses/{row['course_id']}",
                f"{SPRING_BASE_URL}/courses/{row['course_id']}/modules",
                f"{SPRING_BASE_URL}/modules/{row['module_id']}",
                f"{SPRING_BASE_URL}/modules/{row['module_id']}/lessons",
                f"{SPRING_BASE_URL}/lessons/{row['lesson_id']}",
                f"{SPRING_BASE_URL}/modules/{row['module_id']}/quiz",
            ]
            for url in urls:
                status, payload = request_json(url)
                assert_status(status, payload, url, 200)
    print("[ok] massa spring")


def validate_python() -> None:
    with PYTHON_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            urls = [
                f"{PYTHON_BASE_URL}/courses",
                f"{PYTHON_BASE_URL}/courses/{row['course_id']}",
                f"{PYTHON_BASE_URL}/courses/{row['course_id']}/modules",
                f"{PYTHON_BASE_URL}/modules/{row['module_id']}",
                f"{PYTHON_BASE_URL}/modules/{row['module_id']}/lessons",
                f"{PYTHON_BASE_URL}/lessons/{row['lesson_id']}",
                f"{PYTHON_BASE_URL}/modules/{row['quiz_module_id']}/quiz",
            ]
            for url in urls:
                status, payload = request_json(url)
                assert_status(status, payload, url, 200)
    print("[ok] massa python simple_py")


def main() -> int:
    if VALIDATION_TARGET not in {"spring", "python", "both"}:
        raise RuntimeError(f"VALIDATION_TARGET invalido: {VALIDATION_TARGET}")
    if VALIDATION_TARGET in {"spring", "both"}:
        validate_spring()
    if VALIDATION_TARGET in {"python", "both"}:
        validate_python()
    print("Validacao concluida.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
