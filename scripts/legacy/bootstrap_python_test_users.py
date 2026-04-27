#!/usr/bin/env python3
"""Provisiona professores ativos para a suíte de paridade."""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = os.getenv("BOOTSTRAP_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@teste.com")
ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "Senha@123")
ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "professores_login.csv"


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


def login_admin() -> str:
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/api/v1/auth/login",
        {"email_ou_usuario": ADMIN_EMAIL, "senha": ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"Falha no login do admin ({status}): {payload}")
    token = ((payload.get("data") or {}).get("access_token") or "").strip()
    if not token:
        raise RuntimeError(f"Login admin sem token: {payload}")
    return token


def list_users(token: str) -> dict[str, dict]:
    users: dict[str, dict] = {}
    status, payload = request_json(
        "GET",
        f"{BASE_URL}/api/v1/admin/usuarios?skip=0&limit=100",
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"Falha ao listar usuarios ({status}): {payload}")
    for user in (payload.get("data") or {}).get("usuarios", []):
        email = (user.get("email") or "").strip().lower()
        if email:
            users[email] = user
    return users


def ensure_user(token: str, existing: dict[str, dict], email: str, senha: str, index: int) -> None:
    email_key = email.lower()
    user = existing.get(email_key)
    if user is None:
        cadastro = {
            "nome": f"Professor Benchmark {index}",
            "cpf": f"900000000{index:02d}"[-11:],
            "email": email,
            "senha": senha,
            "perfil": "PROFESSOR",
        }
        status, payload = request_json("POST", f"{BASE_URL}/api/v1/auth/cadastro", cadastro)
        if status != 201:
            raise RuntimeError(f"Falha ao cadastrar {email} ({status}): {payload}")
        user = payload.get("data") or {}
        existing[email_key] = user
        print(f"[criado] {email}")
    else:
        print(f"[existe ] {email}")
    if (user.get("status") or "").upper() != "ATIVO":
        status, payload = request_json(
            "PATCH",
            f"{BASE_URL}/api/v1/admin/usuarios/{user['id']}/ativar",
            token=token,
        )
        if status != 200:
            raise RuntimeError(f"Falha ao ativar {email} ({status}): {payload}")
        print(f"[ativo  ] {email}")
    else:
        print(f"[ok     ] {email}")


def main() -> int:
    if not CSV_PATH.exists():
        raise RuntimeError(f"CSV nao encontrado: {CSV_PATH}")
    token = login_admin()
    users = list_users(token)
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            ensure_user(token, users, row["email"].strip(), row["senha"].strip(), index)
    print("Bootstrap de professores concluido.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
