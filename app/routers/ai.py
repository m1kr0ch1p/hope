from __future__ import annotations

import json
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import get_connection
from app.services.investigation_service import build_case_context
from app.services.ollama_service import generate_report_draft


router = APIRouter(
    prefix="/ia",
    tags=["IA local"],
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "app" / "templates")
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post(
    "/casos/{cnpd_id}/rascunho",
    response_class=HTMLResponse,
)
def create_draft(
    request: Request,
    cnpd_id: int,
):
    try:
        context = build_case_context(cnpd_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    try:
        result = generate_report_draft(context)

    except requests.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível acessar o Ollama local. "
                "Confirme se o serviço está em execução em "
                "http://127.0.0.1:11434."
            ),
        ) from exc

    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                "O Ollama excedeu o tempo limite de geração."
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    created_at = utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rascunhos_ia (
                cnpd_id,
                modelo,
                prompt_contexto_json,
                resposta_json,
                metricas_json,
                status,
                criado_em,
                atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, 'RASCUNHO', ?, ?)
            """,
            (
                cnpd_id,
                result["model"],
                json.dumps(
                    result["input_context"],
                    ensure_ascii=False,
                    indent=2,
                ),
                json.dumps(
                    result["draft"],
                    ensure_ascii=False,
                    indent=2,
                ),
                json.dumps(
                    result["metrics"],
                    ensure_ascii=False,
                    indent=2,
                ),
                created_at,
                created_at,
            ),
        )

        draft_id = cursor.lastrowid

    return templates.TemplateResponse(
        request=request,
        name="ai_draft.html",
        context={
            "cnpd_id": cnpd_id,
            "draft_id": draft_id,
            "draft": result["draft"],
            "model": result["model"],
            "metrics": result["metrics"],
        },
    )


@router.get(
    "/casos/{cnpd_id}/rascunhos/{draft_id}",
    response_class=HTMLResponse,
)
def view_draft(
    request: Request,
    cnpd_id: int,
    draft_id: int,
):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM rascunhos_ia
            WHERE id = ? AND cnpd_id = ?
            """,
            (draft_id, cnpd_id),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Rascunho não encontrado.",
        )

    return templates.TemplateResponse(
        request=request,
        name="ai_draft.html",
        context={
            "cnpd_id": cnpd_id,
            "draft_id": draft_id,
            "draft": json.loads(row["resposta_json"]),
            "model": row["modelo"],
            "metrics": json.loads(
                row["metricas_json"] or "{}"
            ),
        },
    )