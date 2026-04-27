#!/usr/bin/env python3
"""Cria massa fixa de leitura para a PoC Python simple_py."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent.parent
OUT_CSV = ROOT / "data" / "simple_py" / "python_read_ids.csv"


def request_json(method: str, url: str, payload: dict | None = None, multipart_field: str | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        if multipart_field:
            boundary = "----jmeter-suite-simple-py"
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            body = [
                f"--{boundary}",
                f'Content-Disposition: form-data; name="{multipart_field}"',
                "Content-Type: application/json",
                "",
                json.dumps(payload, ensure_ascii=False),
                f"--{boundary}--",
                "",
            ]
            data = "\r\n".join(body).encode("utf-8")
        else:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
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


def assert_status(status: int, payload: dict, expected: int, context: str) -> None:
    if status != expected:
        raise RuntimeError(f"{context}: esperado {expected}, recebido {status}, payload={payload}")


def extract_id(payload: dict, context: str) -> int:
    try:
        return int(payload["dados"]["id"])
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{context}: resposta sem dados.id: {payload}") from exc


def create_course(idx: int) -> int:
    payload = {
        "title": f"Curso Read Python {idx}",
        "category": "Tecnologia",
        "description": f"Curso de leitura simple_py {idx}",
    }
    status, body = request_json("POST", f"{BASE_URL}/courses", payload, multipart_field="dados")
    assert_status(status, body, 201, "Falha ao criar curso")
    return extract_id(body, "Curso criado")


def create_module(course_id: int, idx: int) -> int:
    payload = {"name": f"Modulo Read Python {idx}"}
    status, body = request_json("POST", f"{BASE_URL}/courses/{course_id}/modules", payload, multipart_field="dados")
    assert_status(status, body, 201, "Falha ao criar modulo")
    return extract_id(body, "Modulo criado")


def create_lesson(module_id: int, idx: int) -> int:
    payload = {
        "name": f"Aula Read Python {idx}",
        "content_editor": "Conteudo fixo para massa de leitura.",
    }
    status, body = request_json("POST", f"{BASE_URL}/modules/{module_id}/lessons", payload, multipart_field="dados")
    assert_status(status, body, 201, "Falha ao criar aula")
    return extract_id(body, "Aula criada")


def create_quiz(module_id: int, idx: int) -> None:
    payload = {
        "questions": [
            {
                "statement": f"Pergunta {idx}?",
                "points": 1,
                "alternatives": [
                    {"text": "A", "correct": False},
                    {"text": "B", "correct": True},
                    {"text": "C", "correct": False},
                    {"text": "D", "correct": False},
                ],
            }
        ]
    }
    status, body = request_json("POST", f"{BASE_URL}/modules/{module_id}/quiz", payload)
    assert_status(status, body, 201, "Falha ao criar quiz")


def main() -> int:
    rows: list[dict[str, int]] = []
    for idx in range(1, 13):
        course_id = create_course(idx)
        module_id = create_module(course_id, idx)
        lesson_id = create_lesson(module_id, idx)
        create_quiz(module_id, idx)
        rows.append(
            {
                "course_id": course_id,
                "module_id": module_id,
                "lesson_id": lesson_id,
                "quiz_module_id": module_id,
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["course_id", "module_id", "lesson_id", "quiz_module_id"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Massa Python simple_py gerada em {OUT_CSV}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
