"""
Rotas (Routers) para geração de relatórios PDF.

Este módulo implementa os endpoints para:
- Gerar relatórios operacionais de casos em PDF
- Download dos arquivos gerados

Uso:
    Incluído em app/main.py via app.include_router(reports.router)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.report_service import create_report

# Router com prefixo "/relatorios"
router = APIRouter(
    prefix="/relatorios",
    tags=["Relatórios"],
)


@router.post("/casos/{cnpd_id}")
def generate_case_report(cnpd_id: int):
    """
    Gera um relatório PDF operacional para um caso específico.

    O relatório inclui:
    - Dados oficiais do CNPD
    - Evidências cadastradas
    - Pessoas e vínculos
    - Redes sociais
    - Pontos geográficos
    - Anotações analíticas
    - Imagens disponíveis

    Args:
        cnpd_id: Identificador único do caso no CNPD.

    Returns:
        FileResponse: Arquivo PDF do relatório.

    Raises:
        HTTPException: 500 em caso de erro na geração do relatório.
    """
    try:
        result = create_report(cnpd_id)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    return FileResponse(
        result["path"],
        media_type="application/pdf",
        filename=result["path"].name,
    )