from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, DATA_DIR
from app.database import get_connection


UPLOADS_DIR = DATA_DIR / "images" / "uploads"
REPORTS_DIR = DATA_DIR / "reports"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_case(cnpd_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM casos WHERE cnpd_id = ?",
            (cnpd_id,),
        ).fetchone()


def ensure_case(cnpd_id: int) -> None:
    if not get_case(cnpd_id):
        raise ValueError(f"Caso CNPD {cnpd_id} não encontrado.")


def insert_evidence(cnpd_id: int, data: dict[str, Any]) -> None:
    ensure_case(cnpd_id)
    timestamp = now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO evidencias (
                cnpd_id, tipo, titulo, valor, descricao, url_fonte,
                data_evento, classificacao, nivel_confianca,
                status_verificacao, criado_por, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                data["tipo"],
                data.get("titulo"),
                data["valor"],
                data.get("descricao"),
                data.get("url_fonte"),
                data.get("data_evento"),
                data.get("classificacao", "DADO_BRUTO"),
                data.get("nivel_confianca", "NAO_AVALIADO"),
                data.get("status_verificacao", "PENDENTE"),
                data.get("criado_por"),
                timestamp,
                timestamp,
            ),
        )


def insert_person(cnpd_id: int, data: dict[str, Any]) -> None:
    ensure_case(cnpd_id)
    timestamp = now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pessoas_relacionadas (
                cnpd_id, nome, tipo_relacao, descricao_relacao, email,
                telefone, localidade, fonte_url, nivel_confianca,
                status_verificacao, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                data["nome"],
                data.get("tipo_relacao"),
                data.get("descricao_relacao"),
                data.get("email"),
                data.get("telefone"),
                data.get("localidade"),
                data.get("fonte_url"),
                data.get("nivel_confianca", "NAO_AVALIADO"),
                data.get("status_verificacao", "PENDENTE"),
                timestamp,
                timestamp,
            ),
        )


def insert_social(cnpd_id: int, data: dict[str, Any]) -> None:
    ensure_case(cnpd_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO contas_sociais (
                cnpd_id, pessoa_relacionada_id, plataforma, username,
                perfil_url, perfil_id, nome_exibicao, observacao,
                fonte_url, nivel_confianca, status_verificacao, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                data.get("pessoa_relacionada_id") or None,
                data["plataforma"],
                data.get("username"),
                data.get("perfil_url"),
                data.get("perfil_id"),
                data.get("nome_exibicao"),
                data.get("observacao"),
                data.get("fonte_url"),
                data.get("nivel_confianca", "NAO_AVALIADO"),
                data.get("status_verificacao", "PENDENTE"),
                now(),
            ),
        )


def insert_location(cnpd_id: int, data: dict[str, Any]) -> None:
    ensure_case(cnpd_id)
    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude deve estar entre -180 e 180.")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pontos_geograficos (
                cnpd_id, latitude, longitude, titulo, descricao, tipo_local,
                precisao_metros, data_evento, fonte_url, nivel_confianca,
                status_verificacao, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                latitude,
                longitude,
                data["titulo"],
                data.get("descricao"),
                data.get("tipo_local", "OUTRO"),
                data.get("precisao_metros") or None,
                data.get("data_evento") or None,
                data.get("fonte_url"),
                data.get("nivel_confianca", "NAO_AVALIADO"),
                data.get("status_verificacao", "PENDENTE"),
                now(),
            ),
        )


def insert_note(cnpd_id: int, data: dict[str, Any]) -> None:
    ensure_case(cnpd_id)
    timestamp = now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO anotacoes (
                cnpd_id, categoria, conteudo, classificacao,
                nivel_confianca, criado_por, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                data.get("categoria", "ANOTACAO"),
                data["conteudo"],
                data.get("classificacao", "HIPOTESE"),
                data.get("nivel_confianca", "NAO_AVALIADO"),
                data.get("criado_por"),
                timestamp,
                timestamp,
            ),
        )


def sanitize_filename(value: str) -> str:
    name = Path(value).name
    name = re.sub(r"[^A-Za-z0-9À-ÿ._ -]", "_", name).strip(" .")
    return name or "upload.bin"


def save_upload_base64(
    cnpd_id: int,
    filename: str,
    content_type: str,
    content: bytes,
    description: str | None = None,
) -> None:
    ensure_case(cnpd_id)
    safe_name = sanitize_filename(filename)
    digest = hashlib.sha256(content).hexdigest()
    encoded = base64.b64encode(content).decode("ascii")

    destination_dir = UPLOADS_DIR / str(cnpd_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{digest[:16]}_{safe_name}"
    destination.write_bytes(content)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO midias (
                cnpd_id, tipo, origem, nome_original, caminho_relativo,
                mime_type, tamanho_bytes, sha256, descricao, conteudo_base64,
                criado_em
            ) VALUES (?, 'IMAGEM_INVESTIGADOR', 'INVESTIGADOR', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cnpd_id,
                safe_name,
                str(destination.relative_to(BASE_DIR)),
                content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
                len(content),
                digest,
                description,
                encoded,
                now(),
            ),
        )


def build_case_context(cnpd_id: int) -> dict[str, Any]:
    ensure_case(cnpd_id)
    with get_connection() as conn:
        case = conn.execute("SELECT * FROM casos WHERE cnpd_id = ?", (cnpd_id,)).fetchone()
        result: dict[str, Any] = {"caso": dict(case)}
        for table, key in (
            ("evidencias", "evidencias"),
            ("pessoas_relacionadas", "pessoas"),
            ("contas_sociais", "redes_sociais"),
            ("pontos_geograficos", "pontos"),
            ("anotacoes", "anotacoes"),
            ("midias", "midias"),
        ):
            result[key] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall()]
        return result
