#!/usr/bin/env python3
"""Cria massa fixa de leitura para a API Spring."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "http://localhost:8080"
ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "spring_read_ids.csv"


def request_json(method: str, url: str, payload: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
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


def encode_multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----JMeterParitySpringBoundary"
    parts: list[str] = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n")
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n')
        if key == "dados":
            parts.append("Content-Type: application/json\r\n")
        parts.append("\r\n")
        parts.append(value)
        parts.append("\r\n")
    parts.append(f"--{boundary}--\r\n")
    body = "".join(parts).encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


def create_course(idx: int) -> int:
    dados = json.dumps(
        {
            "title": f"Curso Read Spring {idx}",
            "category": "Tecnologia",
            "description": f"Curso de leitura spring {idx}",
        }
    )
    body, content_type = encode_multipart({"dados": dados})
    status, payload = request_json("POST", f"{BASE_URL}/courses", body, {"Content-Type": content_type})
    if status != 201:
        raise RuntimeError(f"Falha ao criar curso spring ({status}): {payload}")
    return int(payload["dados"]["id"])


def create_module(course_id: int, idx: int) -> int:
    dados = json.dumps({"name": f"Modulo Read Spring {idx}"})
    body, content_type = encode_multipart({"dados": dados})
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/courses/{course_id}/modules",
        body,
        {"Content-Type": content_type},
    )
    if status != 201:
        raise RuntimeError(f"Falha ao criar modulo spring ({status}): {payload}")
    return int(payload["dados"]["id"])


def create_lesson(module_id: int, idx: int) -> int:
    dados = json.dumps(
        {
            "name": f"Aula Read Spring {idx}",
            "contentEditor": "Conteudo fixo de leitura spring.",
        }
    )
    body, content_type = encode_multipart({"dados": dados})
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/modules/{module_id}/lessons",
        body,
        {"Content-Type": content_type},
    )
    if status != 201:
        raise RuntimeError(f"Falha ao criar aula spring ({status}): {payload}")
    return int(payload["dados"]["id"])


def create_assessment(module_id: int) -> None:
    body = {
        "questions": [
            {
                "statement": "Pergunta de benchmark spring?",
                "points": 1,
                "alternatives": [
                    {"text": "Opcao A", "correct": False},
                    {"text": "Opcao B", "correct": True},
                    {"text": "Opcao C", "correct": False},
                    {"text": "Opcao D", "correct": False},
                ],
            }
        ]
    }
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/modules/{module_id}/quiz",
        json.dumps(body).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    if status != 201:
        raise RuntimeError(f"Falha ao criar quiz spring ({status}): {payload}")


def main() -> int:
    rows: list[dict[str, int]] = []
    for idx in range(1, 4):
        course_id = create_course(idx)
        module_id = create_module(course_id, idx)
        lesson_id = create_lesson(module_id, idx)
        create_assessment(module_id)
        rows.append({"course_id": course_id, "module_id": module_id, "lesson_id": lesson_id})
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["course_id", "module_id", "lesson_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Massa Spring gerada em {OUT_CSV}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
