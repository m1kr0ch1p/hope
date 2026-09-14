"""
Serviços de investigação e gerenciamento de dados de casos.

Este módulo fornece funções para:
- Operações CRUD em evidências, pessoas, redes sociais, localizações e anotações
- Gerenciamento de upload de imagens
- Construção de contexto completo de caso para IA

Uso:
    from app.services.investigation_service import (
        build_case_context,
        insert_evidence,
        insert_person,
        ...
    )
"""

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

# Diretórios definidos aqui para uso local
UPLOADS_DIR = DATA_DIR / "images" / "uploads"
REPORTS_DIR = DATA_DIR / "reports"


def now() -> str:
    """
    Retorna timestamp UTC atual em formato ISO 8601.

    Returns:
        str: Timestamp ISO formatado.
    """
    return datetime.now(timezone.utc).isoformat()


def get_case(cnpd_id: int):
    """
    Recupera um caso pelo seu identificador CNPD.

    Args:
        cnpd_id: Identificador único do caso no CNPD.

    Returns:
        sqlite3.Row | None: Registro do caso ou None se não encontrado.
    """
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM casos WHERE cnpd_id = ?",
            (cnpd_id,),
        ).fetchone()


def ensure_case(cnpd_id: int) -> None:
    """
    Verifica se um caso existe, levantando erro se não encontrado.

    Args:
        cnpd_id: Identificador do caso.

    Raises:
        ValueError: Se o caso não for encontrado.
    """
    if not get_case(cnpd_id):
        raise ValueError(f"Caso CNPD {cnpd_id} não encontrado.")


def insert_evidence(cnpd_id: int, data: dict[str, Any]) -> None:
    """
    Insere uma nova evidência no banco de dados.

    Args:
        cnpd_id: Identificador do caso.
        data: Dicionário com os campos da evidência (tipo, valor, titulo, etc.).

    Raises:
        ValueError: Se o caso não existir.
    """
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
    """
    Insere uma pessoa relacionada ao caso.

    Args:
        cnpd_id: Identificador do caso.
        data: Dicionário com os campos da pessoa (nome, tipo_relacao, email, etc.).

    Raises:
        ValueError: Se o caso não existir.
    """
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
    """
    Insere uma conta de rede social associada ao caso.

    Args:
        cnpd_id: Identificador do caso.
        data: Dicionário com os campos da conta (plataforma, username, etc.).

    Raises:
        ValueError: Se o caso não existir.
    """
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
    """
    Insere um ponto geográfico no caso.

    Args:
        cnpd_id: Identificador do caso.
        data: Dicionário com latitude, longitude e outros campos.

    Raises:
        ValueError: Se latitude/longitude estiverem fora dos limites.
    """
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
    """
    Insere uma anotação analítica no caso.

    Args:
        cnpd_id: Identificador do caso.
        data: Dicionário com categoria, conteudo, classificacao, etc.

    Raises:
        ValueError: Se o caso não existir.
    """
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
    """
    Sanitiza um nome de arquivo, removendo caracteres perigosos.

    Args:
        value: Nome original do arquivo.

    Returns:
        str: Nome de arquivo seguro.
    """
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
    """
    Salva uma imagem enviada pelo investigador no caso.

    O conteúdo é salvo em disco e a referência é armazenada no banco
    com o conteúdo em base64.

    Args:
        cnpd_id: Identificador do caso.
        filename: Nome original do arquivo.
        content_type: Tipo MIME do arquivo.
        content: Bytes do arquivo.
        description: Descrição opcional da imagem.

    Raises:
        ValueError: Se o caso não existir.
    """
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
    """
    Constrói o contexto completo de um caso para processamento.

    Recupera todas as informações associadas ao caso, incluindo:
    - Dados oficiais do caso
    - Evidências
    - Pessoas relacionadas
    - Redes sociais
    - Pontos geográficos
    - Anotações
    - Mídias

    Args:
        cnpd_id: Identificador do caso.

    Returns:
        dict: Dicionário com todas as informações estruturadas.

    Raises:
        ValueError: Se o caso não existir.
    """
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


def delete_evidence(cnpd_id: int, evidencia_id: int) -> bool:
    """Remove uma evidência específica."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM evidencias WHERE id = ? AND cnpd_id = ?", (evidencia_id, cnpd_id))
        return cur.rowcount > 0


def delete_person(cnpd_id: int, pessoa_id: int) -> bool:
    """Remove uma pessoa relacionada e suas contas sociais."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        conn.execute("UPDATE contas_sociais SET pessoa_relacionada_id = NULL WHERE pessoa_relacionada_id = ?", (pessoa_id,))
        cur = conn.execute("DELETE FROM pessoas_relacionadas WHERE id = ? AND cnpd_id = ?", (pessoa_id, cnpd_id))
        return cur.rowcount > 0


def delete_social(cnpd_id: int, social_id: int) -> bool:
    """Remove uma conta social."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM contas_sociais WHERE id = ? AND cnpd_id = ?", (social_id, cnpd_id))
        return cur.rowcount > 0


def delete_location(cnpd_id: int, location_id: int) -> bool:
    """Remove um ponto geográfico."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM pontos_geograficos WHERE id = ? AND cnpd_id = ?", (location_id, cnpd_id))
        return cur.rowcount > 0


def delete_note(cnpd_id: int, note_id: int) -> bool:
    """Remove uma anotação."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM anotacoes WHERE id = ? AND cnpd_id = ?", (note_id, cnpd_id))
        return cur.rowcount > 0


def delete_media(cnpd_id: int, media_id: int) -> bool:
    """Remove uma mídia (remove o arquivo do disco também)."""
    ensure_case(cnpd_id)
    with get_connection() as conn:
        media = conn.execute("SELECT caminho_relativo, conteudo_base64 FROM midias WHERE id = ? AND cnpd_id = ?", (media_id, cnpd_id)).fetchone()
        if not media:
            return False
        if media["caminho_relativo"]:
            path = BASE_DIR / media["caminho_relativo"]
            if path.exists():
                path.unlink()
        cur = conn.execute("DELETE FROM midias WHERE id = ? AND cnpd_id = ?", (media_id, cnpd_id))
        return cur.rowcount > 0