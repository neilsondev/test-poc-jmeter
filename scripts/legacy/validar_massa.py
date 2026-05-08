#!/usr/bin/env python3
"""Valida IDs básicos da suíte no mesmo modo sem JWT usado pelo JMeter."""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "legacy"
SPRING_CSV = DATA_DIR / "spring_read_ids.csv"
PYTHON_CSV = DATA_DIR / "python_read_ids.csv"
SPRING_BASE_URL = os.getenv("SPRING_VALIDATION_BASE_URL", "http://localhost:8080").rstrip("/")
PYTHON_BASE_URL = os.getenv("PYTHON_VALIDATION_BASE_URL", "http://localhost:8000").rstrip("/")


def request_json(method: str, url: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
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
                status, payload = request_json("GET", url)
                assert_status(status, payload, url, 200)
    print("[ok] massa spring")


def validate_python() -> None:
    with PYTHON_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            urls = [
                f"{PYTHON_BASE_URL}/api/v1/cursos",
                f"{PYTHON_BASE_URL}/api/v1/cursos/{row['curso_id']}",
                f"{PYTHON_BASE_URL}/api/v1/cursos/{row['curso_id']}/modulos",
                f"{PYTHON_BASE_URL}/api/v1/cursos/{row['curso_id']}/modulos/{row['modulo_id']}",
                f"{PYTHON_BASE_URL}/api/v1/modulos/{row['modulo_id']}/aulas",
                f"{PYTHON_BASE_URL}/api/v1/modulos/{row['modulo_id']}/aulas/{row['aula_id']}",
                f"{PYTHON_BASE_URL}/api/v1/modulos/{row['prova_modulo_id']}/prova",
            ]
            for url in urls:
                status, payload = request_json("GET", url)
                assert_status(status, payload, url, 200)
    print("[ok] massa python")


def main() -> int:
    validate_spring()
    validate_python()
    print("Validacao concluida.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
