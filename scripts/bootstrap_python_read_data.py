#!/usr/bin/env python3
"""Cria massa fixa de leitura para a API Python."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
LOGIN_CSV = ROOT / "data" / "professores_login.csv"
OUT_CSV = ROOT / "data" / "python_read_ids.csv"


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


def login(email: str, senha: str) -> str:
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/api/v1/auth/login",
        {"email_ou_usuario": email, "senha": senha},
    )
    if status != 200:
        raise RuntimeError(f"Falha no login professor {email} ({status}): {payload}")
    return payload["data"]["access_token"]


def create_course(token: str, email: str, idx: int) -> int:
    body = {
        "titulo": f"Curso Read Python {email} {idx}",
        "categoria": "Tecnologia",
        "descricao": f"Curso de leitura python {email} {idx}",
        "carga_horaria": "20h",
        "requer_endereco": False,
        "requer_genero": False,
        "requer_idade": False,
    }
    status, payload = request_json("POST", f"{BASE_URL}/api/v1/cursos", body, token)
    if status != 201:
        raise RuntimeError(f"Falha ao criar curso python ({status}): {payload}")
    return int(payload["data"]["id"])


def create_module(token: str, course_id: int) -> int:
    status, payload = request_json("POST", f"{BASE_URL}/api/v1/cursos/{course_id}/modulos", {}, token)
    if status != 201:
        raise RuntimeError(f"Falha ao criar modulo python ({status}): {payload}")
    return int(payload["data"]["id"])


def create_lesson(token: str, module_id: int, email: str, idx: int) -> int:
    body = {
        "nome": f"Aula Read Python {email} {idx}",
        "conteudo_ck_editor": "<p>Conteudo fixo de leitura python.</p>",
    }
    status, payload = request_json("POST", f"{BASE_URL}/api/v1/modulos/{module_id}/aulas", body, token)
    if status != 201:
        raise RuntimeError(f"Falha ao criar aula python ({status}): {payload}")
    return int(payload["data"]["id"])


def create_assessment(token: str, module_id: int) -> None:
    body = {
        "mostrar_respostas_erradas": False,
        "mostrar_respostas_corretas": False,
        "mostrar_valores": True,
        "perguntas": [
            {
                "enunciado": "Pergunta de benchmark python?",
                "pontos": 1,
                "alternativas": [
                    {"texto": "Opcao A", "correta": False},
                    {"texto": "Opcao B", "correta": True},
                    {"texto": "Opcao C", "correta": False},
                    {"texto": "Opcao D", "correta": False},
                ],
            }
        ],
    }
    status, payload = request_json("POST", f"{BASE_URL}/api/v1/modulos/{module_id}/prova/manual", body, token)
    if status != 201:
        raise RuntimeError(f"Falha ao criar prova manual python ({status}): {payload}")


def main() -> int:
    rows: list[dict[str, str | int]] = []
    with LOGIN_CSV.open("r", encoding="utf-8", newline="") as handle:
        professores = list(csv.DictReader(handle))
    if not professores:
        raise RuntimeError(f"Nenhum professor encontrado em {LOGIN_CSV}")

    for professor_index, professor in enumerate(professores, start=1):
        email = professor["email"].strip()
        senha = professor["senha"].strip()
        token = login(email, senha)
        for idx in range(1, 4):
            global_idx = (professor_index - 1) * 3 + idx
            curso_id = create_course(token, email, global_idx)
            modulo_id = create_module(token, curso_id)
            aula_id = create_lesson(token, modulo_id, email, global_idx)
            create_assessment(token, modulo_id)
            rows.append(
                {
                    "email": email,
                    "senha": senha,
                    "curso_id": curso_id,
                    "modulo_id": modulo_id,
                    "aula_id": aula_id,
                    "prova_modulo_id": modulo_id,
                }
            )
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["email", "senha", "curso_id", "modulo_id", "aula_id", "prova_modulo_id"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Massa Python gerada em {OUT_CSV}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
