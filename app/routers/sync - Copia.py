from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import get_connection, initialize_database
from app.services.sync_service import synchronize_cnpd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sincronizar", tags=["Sincronização"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def load_collections():
    initialize_database()
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, iniciada_em, finalizada_em, status, ordenacao,
                   pagina_inicial, paginas_lidas, registros_lidos, erro
            FROM coletas
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()


@router.get("", response_class=HTMLResponse)
def sync_page(request: Request, ok: int | None = None):
    try:
        collections = load_collections()
        sync_error = None
    except Exception as exc:
        logger.exception("Erro ao abrir página de sincronização.")
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


@router.post("/cnpd", response_class=HTMLResponse)
def start_sync(
    request: Request,
    max_pages: int = Form(default=1),
    start_page: int = Form(default=0),
    order: str = Form(default="MAIS_RECENTE"),
    download_images: bool = Form(default=False),
):
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
        logger.exception("Falha na sincronização CNPD.")
        return templates.TemplateResponse(
            request=request,
            name="sync.html",
            context={
                "collections": load_collections(),
                "sync_ok": False,
                "sync_error": f"{type(exc).__name__}: {exc}",
            },
            status_code=500,
        )

    return RedirectResponse(
        url=f"/sincronizar?ok=1&coleta_id={result['collection_id']}",
        status_code=303,
    )
