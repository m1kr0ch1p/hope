from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import (
    CNPD_BASE_URL,
    CNPD_FILTER_URL,
    CNPD_IMAGE_METADATA_URL_TEMPLATE,
    CNPD_PAINEL_URL,
    DEFAULT_PAGE_DELAY_SECONDS,
    DEFAULT_REQUEST_TIMEOUT,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_date_br(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return str(value)
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return value


def source_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    cnpd_id = record.get("id")
    if cnpd_id is None:
        raise ValueError("Registro CNPD sem campo id.")
    cnpd_id = int(cnpd_id)
    return {
        "cnpd_id": cnpd_id,
        "nome": record.get("nome") or "NOME_NAO_INFORMADO",
        "idade_atual": record.get("idadeAtual"),
        "idade_desaparecimento": record.get("idadeDesaparecimento"),
        "sexo": record.get("sexo"),
        "raca_cor": record.get("racaCor"),
        "local_registro": record.get("localRegistro"),
        "uf_registro": record.get("ufRegistro"),
        "data_desaparecimento": parse_date_br(record.get("dataDesaparecimento")),
        "data_registro_desaparecimento": parse_date_br(record.get("dataRegistroDesaparecimento")),
        "localizacao_confirmada": record.get("flLocalizacaoConfirmada"),
        "imagem_metadata_url": image_metadata_url(cnpd_id),
        "dados_fonte_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        "hash_fonte": source_hash(record),
    }


def image_metadata_url(cnpd_id: int | str) -> str:
    return CNPD_IMAGE_METADATA_URL_TEMPLATE.format(desaparecimento_id=cnpd_id)


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": CNPD_BASE_URL,
        "Referer": CNPD_PAINEL_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    return session


class CNPDClient:
    def __init__(
        self,
        *,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        page_delay: float = DEFAULT_PAGE_DELAY_SECONDS,
    ) -> None:
        self.timeout = timeout
        self.page_delay = page_delay
        self.session = create_session()

    def fetch_page(
        self,
        page: int,
        *,
        order: str = "MAIS_RECENTE",
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.session.post(
            CNPD_FILTER_URL,
            params={"ordenacao": order, "pagina": page},
            json=filters if filters is not None else {},
            timeout=self.timeout,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise ValueError(f"Listagem CNPD não retornou JSON: {content_type!r}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("A raiz da resposta CNPD não é um objeto JSON.")
        records = payload.get("desaparecidos")
        if not isinstance(records, list):
            raise ValueError(
                "Campo desaparecidos ausente ou inválido. "
                f"Chaves: {list(payload.keys())}"
            )
        return payload

    def iter_pages(
        self,
        *,
        start_page: int = 0,
        max_pages: int = 3,
        order: str = "MAIS_RECENTE",
    ) -> Iterator[tuple[int, dict[str, Any]]]:
        for page in range(start_page, start_page + max_pages):
            payload = self.fetch_page(page, order=order)
            yield page, payload
            if not payload["desaparecidos"]:
                break
            time.sleep(self.page_delay)

    def fetch_main_image_metadata(self, cnpd_id: int) -> dict[str, Any] | None:
        response = self.session.get(
            image_metadata_url(cnpd_id),
            headers={"Accept": "application/json, text/plain, */*"},
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Metadados de imagem em formato inválido.")
        return payload

    @staticmethod
    def _safe_filename(value: str, fallback: str) -> str:
        name = Path(value).name
        name = re.sub(r"[^A-Za-z0-9À-ÿ._ -]", "_", name).strip(" .")
        return name or fallback

    @staticmethod
    def _extension_from_magic(content: bytes) -> str | None:
        if content.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return ".webp"
        return None

    def download_main_image(self, cnpd_id: int, base_directory: Path) -> dict[str, Any] | None:
        metadata = self.fetch_main_image_metadata(cnpd_id)
        if metadata is None:
            return None
        arquivo = metadata.get("arquivoCnpd")
        if not isinstance(arquivo, dict):
            raise ValueError("arquivoCnpd ausente nos metadados de imagem.")
        dto = arquivo.get("arquivoDTO")
        if not isinstance(dto, dict):
            raise ValueError("arquivoDTO ausente nos metadados de imagem.")
        encoded = dto.get("conteudo")
        if not isinstance(encoded, str) or not encoded.strip():
            raise ValueError("Conteúdo Base64 de imagem ausente.")
        encoded = re.sub(r"\s+", "", encoded.split(",", 1)[-1])
        try:
            content = base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ValueError("Conteúdo Base64 de imagem inválido.") from exc
        extension = self._extension_from_magic(content)
        if extension is None:
            raise ValueError("Formato de imagem não reconhecido.")
        original_name = dto.get("nome") or arquivo.get("nome") or f"main_{cnpd_id}{extension}"
        filename = self._safe_filename(str(original_name), f"main_{cnpd_id}{extension}")
        if Path(filename).suffix.lower() != extension:
            filename = f"{Path(filename).stem}{extension}"
        output_dir = base_directory / str(cnpd_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / filename
        output_file.write_bytes(content)
        declared_size = dto.get("tamanho") if dto.get("tamanho") is not None else arquivo.get("tamanho")
        return {
            "cnpd_id": cnpd_id,
            "metadata_id": metadata.get("id"),
            "arquivo_cnpd_id": arquivo.get("id"),
            "nome_original": str(original_name),
            "caminho_relativo": str(output_file),
            "mime_type": f"image/{'jpeg' if extension == '.jpg' else extension.lstrip('.')}",
            "tamanho_bytes": len(content),
            "tamanho_declarado": declared_size,
            "url_origem": image_metadata_url(cnpd_id),
            "sha256": hashlib.sha256(content).hexdigest(),
            "arquivo_path_fonte": arquivo.get("path"),
            "coletado_em": utc_now(),
        }
