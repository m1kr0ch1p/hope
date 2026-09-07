from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import IMAGE_SOURCE_DIR, RAW_DIR
from app.database import get_connection
from app.services.cnpd_client import CNPDClient, normalize_record

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_raw_page(coleta_id: int, page: int, payload: dict[str, Any]) -> Path:
    destination_dir = RAW_DIR / f"coleta_{coleta_id}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"pagina_{page:05d}.json"
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def create_collection(conn: sqlite3.Connection, order: str, start_page: int) -> int:
    cursor = conn.execute(
        """
        INSERT INTO coletas (iniciada_em, status, ordenacao, pagina_inicial)
        VALUES (?, 'INICIADA', ?, ?)
        """,
        (utc_now(), order, start_page),
    )
    return int(cursor.lastrowid)


def finalize_collection(
    conn: sqlite3.Connection,
    collection_id: int,
    *,
    status: str,
    pages_read: int,
    records_read: int,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE coletas
        SET finalizada_em = ?, status = ?, paginas_lidas = ?,
            registros_lidos = ?, erro = ?
        WHERE id = ?
        """,
        (utc_now(), status, pages_read, records_read, error, collection_id),
    )


def upsert_case(conn: sqlite3.Connection, case: dict[str, Any]) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO casos (
            cnpd_id, nome, idade_atual, idade_desaparecimento, sexo,
            raca_cor, local_registro, uf_registro, data_desaparecimento,
            data_registro_desaparecimento, localizacao_confirmada,
            imagem_metadata_url, dados_fonte_json, hash_fonte,
            primeira_coleta_em, ultima_coleta_em, status_fonte,
            ausencias_consecutivas
        ) VALUES (
            :cnpd_id, :nome, :idade_atual, :idade_desaparecimento, :sexo,
            :raca_cor, :local_registro, :uf_registro, :data_desaparecimento,
            :data_registro_desaparecimento, :localizacao_confirmada,
            :imagem_metadata_url, :dados_fonte_json, :hash_fonte,
            :primeira_coleta_em, :ultima_coleta_em, 'ATIVO_NA_FONTE', 0
        )
        ON CONFLICT(cnpd_id) DO UPDATE SET
            nome = excluded.nome,
            idade_atual = excluded.idade_atual,
            idade_desaparecimento = excluded.idade_desaparecimento,
            sexo = excluded.sexo,
            raca_cor = excluded.raca_cor,
            local_registro = excluded.local_registro,
            uf_registro = excluded.uf_registro,
            data_desaparecimento = excluded.data_desaparecimento,
            data_registro_desaparecimento = excluded.data_registro_desaparecimento,
            localizacao_confirmada = excluded.localizacao_confirmada,
            imagem_metadata_url = excluded.imagem_metadata_url,
            dados_fonte_json = excluded.dados_fonte_json,
            hash_fonte = excluded.hash_fonte,
            ultima_coleta_em = excluded.ultima_coleta_em,
            status_fonte = 'ATIVO_NA_FONTE',
            ausencias_consecutivas = 0
        """,
        {
            **case,
            "primeira_coleta_em": now,
            "ultima_coleta_em": now,
        },
    )


def mark_case_seen(conn: sqlite3.Connection, collection_id: int, cnpd_id: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO casos_coleta (coleta_id, cnpd_id, encontrado)
        VALUES (?, ?, 1)
        """,
        (collection_id, cnpd_id),
    )


def store_source_image(conn: sqlite3.Connection, image: dict[str, Any]) -> None:
    image_path = Path(image["caminho_relativo"])
    try:
        relative_path = image_path.relative_to(Path.cwd())
    except ValueError:
        relative_path = image_path

    conn.execute(
        """
        INSERT OR IGNORE INTO midias (
            cnpd_id, tipo, origem, nome_original, caminho_relativo,
            mime_type, tamanho_bytes, url_origem, sha256, descricao, criado_em
        ) VALUES (?, 'IMAGEM_PRINCIPAL', 'CNPD', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            image["cnpd_id"],
            image["nome_original"],
            str(relative_path),
            image["mime_type"],
            image["tamanho_bytes"],
            image["url_origem"],
            image["sha256"],
            f"arquivoCnpd.id={image.get('arquivo_cnpd_id')}; path={image.get('arquivo_path_fonte')}",
            image["coletado_em"],
        ),
    )


def synchronize_cnpd(
    *,
    max_pages: int = 1,
    start_page: int = 0,
    order: str = "MAIS_RECENTE",
    page_delay: float = 1.0,
    download_images: bool = False,
    image_delay: float = 0.5,
) -> dict[str, Any]:
    if max_pages < 1:
        raise ValueError("max_pages deve ser maior que zero.")

    client = CNPDClient(page_delay=page_delay)
    pages_read = 0
    records_read = 0
    images_downloaded = 0
    image_errors = 0

    with get_connection() as conn:
        collection_id = create_collection(conn, order, start_page)

    logger.info(
        "Coleta %s iniciada: start_page=%s max_pages=%s imagens=%s",
        collection_id,
        start_page,
        max_pages,
        download_images,
    )

    try:
        for page, payload in client.iter_pages(
            start_page=start_page,
            max_pages=max_pages,
            order=order,
        ):
            records = payload.get("desaparecidos", [])
            if not isinstance(records, list):
                raise ValueError("Resposta CNPD sem lista válida de desaparecidos.")

            with get_connection() as conn:
                save_raw_page(collection_id, page, payload)
                pages_read += 1

                for raw in records:
                    if not isinstance(raw, dict):
                        continue

                    case = normalize_record(raw)
                    upsert_case(conn, case)
                    mark_case_seen(conn, collection_id, case["cnpd_id"])
                    records_read += 1

                    if download_images:
                        try:
                            image = client.download_main_image(
                                case["cnpd_id"],
                                IMAGE_SOURCE_DIR,
                            )
                            if image:
                                store_source_image(conn, image)
                                images_downloaded += 1
                            if image_delay > 0:
                                time.sleep(image_delay)
                        except Exception as image_exc:
                            image_errors += 1
                            logger.warning(
                                "Imagem não obtida para CNPD %s: %s",
                                case["cnpd_id"],
                                image_exc,
                            )

            logger.info(
                "Coleta %s: página %s processada; %s registros.",
                collection_id,
                page,
                len(records),
            )

        with get_connection() as conn:
            finalize_collection(
                conn,
                collection_id,
                status="COMPLETA",
                pages_read=pages_read,
                records_read=records_read,
            )

        logger.info(
            "Coleta %s concluída: páginas=%s registros=%s.",
            collection_id,
            pages_read,
            records_read,
        )

        return {
            "collection_id": collection_id,
            "status": "COMPLETA",
            "pages_read": pages_read,
            "records_read": records_read,
            "images_downloaded": images_downloaded,
            "image_errors": image_errors,
        }

    except Exception as exc:
        logger.exception("Coleta %s falhou.", collection_id)
        with get_connection() as conn:
            finalize_collection(
                conn,
                collection_id,
                status="FALHOU",
                pages_read=pages_read,
                records_read=records_read,
                error=f"{type(exc).__name__}: {exc}",
            )
        raise
