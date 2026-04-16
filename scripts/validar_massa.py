#!/usr/bin/env python3
"""Valida credenciais e IDs básicos da suíte."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPRING_CSV = ROOT / "data" / "spring_read_ids.csv"
PYTHON_CSV = ROOT / "data" / "python_read_ids.csv"


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


def validate_python_login(email: str, senha: str) -> str:
    url = "http://localhost:8000/api/v1/auth/login"
    status, payload = request_json("POST", url, {"email_ou_usuario": email, "senha": senha})
    assert_status(status, payload, url, 200)
    token = payload["data"]["access_token"]
    print(f"[ok] login python {email}")
    return token


def validate_spring() -> None:
    with SPRING_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            urls = [
                "http://localhost:8080/courses",
                f"http://localhost:8080/courses/{row['course_id']}",
                f"http://localhost:8080/courses/{row['course_id']}/modules",
                f"http://localhost:8080/modules/{row['module_id']}",
                f"http://localhost:8080/modules/{row['module_id']}/lessons",
                f"http://localhost:8080/lessons/{row['lesson_id']}",
                f"http://localhost:8080/modules/{row['module_id']}/quiz",
            ]
            for url in urls:
                status, payload = request_json("GET", url)
                assert_status(status, payload, url, 200)
    print("[ok] massa spring")


def validate_python() -> None:
    with PYTHON_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            email = row["email"].strip()
            senha = row["senha"].strip()
            token = validate_python_login(email, senha)
            urls = [
                "http://localhost:8000/api/v1/cursos",
                f"http://localhost:8000/api/v1/cursos/{row['curso_id']}",
                f"http://localhost:8000/api/v1/cursos/{row['curso_id']}/modulos",
                f"http://localhost:8000/api/v1/cursos/{row['curso_id']}/modulos/{row['modulo_id']}",
                f"http://localhost:8000/api/v1/modulos/{row['modulo_id']}/aulas",
                f"http://localhost:8000/api/v1/modulos/{row['modulo_id']}/aulas/{row['aula_id']}",
                f"http://localhost:8000/api/v1/modulos/{row['prova_modulo_id']}/prova",
            ]
            for url in urls:
                status, payload = request_json("GET", url, token=token)
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
