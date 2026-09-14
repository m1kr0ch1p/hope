"""
Cliente API para comunicação com o Portal Público do CNPD.

Este módulo fornece a classe CNPDClient para:
- Buscar casos de desaparecidos via API REST
- Download de imagens oficiais dos casos
- Tratamento de erros, retries e cache de sessão

Uso:
    from app.services.cnpd_client import CNPDClient
    
    client = CNPDClient()
    for page, payload in client.iter_pages():
        # Processar casos
        ...
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    """
    Retorna timestamp UTC atual em formato ISO 8601.

    Returns:
        str: Timestamp ISO formatado.
    """
    return datetime.now(timezone.utc).isoformat()


def parse_date_br(value: Any) -> str | None:
    """
    Converte data no formato brasileiro (DD/MM/AAAA) para ISO (AAAA-MM-DD).

    Args:
        value: Valor da data (string ou outro tipo).

    Returns:
        str | None: Data no formato ISO ou None se inválida/vazia.
    """
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return str(value)
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return value


def source_hash(record: dict[str, Any]) -> str:
    """
    Gera hash SHA-256 canônico de um registro para detecção de mudanças.

    O hash é calculado sobre a representação JSON normalizada (chaves ordenadas,
    sem espaços extras) do registro, permitindo comparar se um caso foi
    atualizado na fonte.

    Args:
        record: Dicionário com os dados do registro.

    Returns:
        str: Hash SHA-256 hexadecimal.
    """
    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Normaliza um registro bruto da API CNPD para o formato interno.

    Converte campos da API (camelCase) para o padrão interno (snake_case)
    e gera campos derivados como hash da fonte e URL de imagem.

    Args:
        record: Registro bruto da API CNPD.

    Returns:
        dict: Registro normalizado no formato interno.

    Raises:
        ValueError: Se o registro não tiver campo 'id'.
    """
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
    """
    Constrói a URL para obter metadatos de imagem de um caso.

    Args:
        cnpd_id: Identificador do caso no CNPD.

    Returns:
        str: URL da API de metadados de imagem.
    """
    return CNPD_IMAGE_METADATA_URL_TEMPLATE.format(desaparecimento_id=cnpd_id)


def create_session() -> requests.Session:
    """
    Cria e configura uma sessão HTTP com retry automático.

    Configura:
    - Retries automáticos para erros 429, 502, 503, 504
    - Backoff exponencial (1.5x) entre tentativas
    - Headers de identificação como navegador real

    Returns:
        requests.Session: Sessão HTTP configurada.
    """
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
    """
    Cliente para comunicação com a API REST do Portal Público do CNPD.

    Fornece métodos para:
    - Iteração paginada sobre casos
    - Download de imagens oficiais
    - Busca de metadatos de mídia

    Attributes:
        timeout: Timeout padrão para requisições (segundos).
        page_delay: Delay entre requisições de página (segundos).
        session: Sessão HTTP configurada.
    """

    def __init__(
        self,
        *,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        page_delay: float = DEFAULT_PAGE_DELAY_SECONDS,
    ) -> None:
        """
        Inicializa o cliente CNPD.

        Args:
            timeout: Timeout para requisições HTTP.
            page_delay: Delay entre requisições para evitar rate limiting.
        """
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
        """
        Busca uma página específica de casos do CNPD.

        Args:
            page: Número da página (0-indexed).
            order: Ordem de classificação.
            filters: Filtros adicionais (opcional).

        Returns:
            dict: Payload da resposta contendo 'desaparecidos', 'totalPaginas', etc.

        Raises:
            ValueError: Se a resposta não for JSON ou não tiver lista de casos.
        """
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
        max_pages: int = 10000,
        order: str = "MAIS_RECENTE",
    ) -> Any:
        """
        Iterador gerador sobre páginas de casos do CNPD.

        Para cada página retorna uma tupla (numero_da_pagina, payload).
        A iteração para quando:
        - totalPaginas é alcançado
        - Uma página está vazia
        - IDs já vistos são repetidos (detecção de Loops)

        Args:
            start_page: Página inicial para começar.
            max_pages: Limite máximo de pages (proteção contra loops).
            order: Ordem de classificação.

        Yields:
            tuple[int, dict]: (número da página, payload JSON)

        Raises:
            ValueError: Se a resposta não contiver lista válida de casos.
        """
        """Itera as páginas reais retornadas pela API pública do CNPD.

        A resposta atual do endpoint contém os campos ``desaparecidos``,
        ``totalRegistros``, ``totalPaginas``, ``paginaAtual`` e
        ``tamanhoPagina``. A coleta para ao alcançar ``totalPaginas`` ou uma
        página vazia; ``max_pages`` continua sendo apenas um limite de proteção.
        """
        page = max(0, int(start_page))
        limit = max(1, int(max_pages))
        seen_pages: set[tuple[str, ...]] = set()

        for _ in range(limit):
            payload = self.fetch_page(page, order=order)
            records = payload.get("desaparecidos", [])

            if not isinstance(records, list):
                raise ValueError(
                    "Resposta CNPD sem lista válida de desaparecidos."
                )
            if not records:
                break

            ids = tuple(
                str(item.get("id") or item.get("cnpdId") or item.get("cnpd_id"))
                for item in records
                if isinstance(item, dict)
            )
            if ids and ids in seen_pages:
                break
            if ids:
                seen_pages.add(ids)

            yield page, payload

            total_pages = payload.get("totalPaginas")
            current_page = payload.get("paginaAtual", page)
            try:
                if int(current_page) + 1 >= int(total_pages):
                    break
            except (TypeError, ValueError):
                pass

            page_size = payload.get("tamanhoPagina")
            try:
                if page_size is not None and len(records) < int(page_size):
                    break
            except (TypeError, ValueError):
                pass

            page += 1

    def fetch_main_image_metadata(self, cnpd_id: int) -> dict[str, Any] | None:
        """
        Busca os metadados da imagem principal de um caso.

        Args:
            cnpd_id: Identificador do caso.

        Returns:
            dict | None: Metadados da imagem ou None se não encontrada (404).

        Raises:
            ValueError: Se os metadados estiverem em formato inválido.
        """
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
        """
        Sanitiza um nome de arquivo, removendo caracteres perigosos.

        Args:
            value: Nome original do arquivo.
            fallback: Nome alternativo se o resultado estiver vazio.

        Returns:
            str: Nome de arquivo seguro para o sistema de arquivos.
        """
        name = Path(value).name
        name = re.sub(r"[^A-Za-z0-9À-ÿ._ -]", "_", name).strip(" .")
        return name or fallback

    @staticmethod
    def _extension_from_magic(content: bytes) -> str | None:
        """
        Detecta a extensão de imagem pelo cabeçalho (magic bytes).

        Args:
            content: Bytes do arquivo.

        Returns:
            str | None: Extensão (.jpg, .png, .gif, .webp) ou None.
        """
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
        """
        Baixa e salva a imagem principal oficial de um caso CNPD.

        Args:
            cnpd_id: Identificador do caso.
            base_directory: Diretório base para salvar a imagem.

        Returns:
            dict | None: Metadados da imagem salva ou None se não encontrada.

        Raises:
            ValueError: Se o formato da imagem ou metadados for inválido.
        """
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

    def find_existing_main_image(
        self,
        cnpd_id: int,
        output_root: Path,
    ) -> dict[str, Any] | None:
        """
        Busca uma imagem principal já salva em disco, se existir.

        Útil para evitar re-download de imagens já coletadas.

        Args:
            cnpd_id: Identificador do caso.
            output_root: Diretório raiz de imagens.

        Returns:
            dict | None: Metadados da imagem encontrada ou None.
        """
        """Retorna imagem oficial já salva em disco, se existir."""
        case_dir = output_root / str(cnpd_id)

        if not case_dir.exists():
            return None

        candidates = [
            path
            for path in case_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".webp",
            }
        ]

        if not candidates:
            return None

        path = sorted(
            candidates,
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[0]

        content = path.read_bytes()
        extension = path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(extension, "application/octet-stream")

        return {
            "cnpd_id": cnpd_id,
            "nome_original": path.name,
            "caminho_relativo": str(path),
            "mime_type": mime_type,
            "tamanho_bytes": len(content),
            "url_origem": image_metadata_url(cnpd_id),
            "sha256": hashlib.sha256(content).hexdigest(),
            "arquivo_cnpd_id": None,
            "arquivo_path_fonte": None,
            "coletado_em": utc_now(),
        }