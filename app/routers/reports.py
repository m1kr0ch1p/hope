from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.database import get_connection
from app.services.report_service import create_report

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.post("/casos/{cnpd_id}")
def generate_case_report(cnpd_id: int):
    try:
        result = create_report(cnpd_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        result["path"],
        media_type="application/pdf",
        filename=result["path"].name,
    )
