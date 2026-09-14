"""
Rotas (Routers) para sincronização de dados do CNPD.

Este módulo implementa os endpoints para:
- Iniciar coletas de dados do Portal Público do CNPD
- Visualizar histórico de coletas
- Gerenciar processos de sincronização em background

Uso:
    Incluído em app/main.py via app.include_router(sync.router)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import get_connection, initialize_database
from app.services.sync_service import synchronize_cnpd

logger = logging.getLogger(__name__)

# Router com prefixo "/sincronizar" para todos os endpoints
router = APIRouter(
    prefix="/sincronizar",
    tags=["Sincronização"],
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "app" / "templates")
)


def load_collections():
    """
    Carrega o histórico das últimas 30 coletas do banco.

    Returns:
        list: Lista de objetos Row com informações de coleta.
    """
    initialize_database()

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                id,
                iniciada_em,
                finalizada_em,
                status,
                pagina_inicial,
                paginas_lidas,
                registros_lidos,
                erro
            FROM coletas
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()


@router.get("", response_class=HTMLResponse)
def sync_page(
    request: Request,
    ok: int | None = None,
):
    """
    Exibe a página de sincronização com histórico de coletas.

    Args:
        request: Objeto de requisição FastAPI para template.
        ok: Parâmetro opcional que indica sucesso da última operação.

    Returns:
        HTMLResponse: Página com lista de coletas e status.
    """
    try:
        collections = load_collections()
        sync_error = None

    except Exception as exc:
        logger.exception(
            "Falha ao carregar histórico."
        )
        collections = []
        sync_error = f"{type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        request=request,
        name="sync.html",
        context={
            "collections": collections,
            "sync_ok": bool(ok),
            "sync_error": sync_error,
        },
    )


@router.post(
    "/cnpd",
    response_class=HTMLResponse,
)
def start_sync(
    request: Request,
    max_pages: int = Form(default=10000),
    start_page: int = Form(default=0),
    order: str = Form(default="MAIS_RECENTE"),
    download_images: bool = Form(default=False),
):
    """
    Inicia uma nova sincronização do CNPD.

    Este endpoint dispara uma coleta em background do portal público
    do CNPD, buscando novos casos de desaparecidos.

    Args:
        request: Objeto de requisição FastAPI.
        max_pages: Máximo de páginas a serem lidas (padrão: 10000).
        start_page: Página inicial para começar (padrão: 0).
        order: Ordem de classificação - "MAIS_RECENTE" ou "MAIS_ANTIGO" (padrão: MAIS_RECENTE).
        download_images: Se True, baixa imagens dos casos (padrão: False).

    Returns:
        RedirectResponse: Redireciona para a página de sincronização com ID da coleta.

    Raises:
        HTTPException: 500 em caso de erro, com detalhes na página.
    """
    max_pages = max(1, min(max_pages, 10000))
    start_page = max(0, start_page)

    try:
        result = synchronize_cnpd(
            max_pages=max_pages,
            start_page=start_page,
            order=order,
            download_images=download_images,
        )

    except Exception as exc:
        logger.exception(
            "Falha durante a sincronização."
        )

        try:
            collections = load_collections()
        except Exception:
            collections = []

        return templates.TemplateResponse(
            request=request,
            name="sync.html",
            context={
                "collections": collections,
                "sync_ok": False,
                "sync_error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            },
            status_code=500,
        )

    return RedirectResponse(
        url=(
            "/sincronizar"
            f"?ok=1&coleta_id={result['collection_id']}"
        ),
        status_code=303,
    )