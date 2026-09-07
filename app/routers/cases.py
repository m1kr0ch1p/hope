from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import get_connection
from app.services.investigation_service import (
    build_case_context,
    insert_evidence,
    insert_location,
    insert_note,
    insert_person,
    insert_social,
    save_upload_base64,
)

router = APIRouter(tags=["Casos"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def load_case_rows(cnpd_id: int) -> dict:
    with get_connection() as conn:
        case = conn.execute("SELECT * FROM casos WHERE cnpd_id = ?", (cnpd_id,)).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Caso não encontrado.")
        return {
            "case": case,
            "media": conn.execute("SELECT * FROM midias WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
            "collections": conn.execute(
                """
                SELECT cc.coleta_id, c.iniciada_em, c.status
                FROM casos_coleta cc JOIN coletas c ON c.id = cc.coleta_id
                WHERE cc.cnpd_id = ? ORDER BY cc.coleta_id DESC LIMIT 10
                """,
                (cnpd_id,),
            ).fetchall(),
            "evidences": conn.execute("SELECT * FROM evidencias WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
            "people": conn.execute("SELECT * FROM pessoas_relacionadas WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
            "socials": conn.execute("SELECT * FROM contas_sociais WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
            "locations": conn.execute("SELECT * FROM pontos_geograficos WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
            "notes": conn.execute("SELECT * FROM anotacoes WHERE cnpd_id = ? ORDER BY id DESC", (cnpd_id,)).fetchall(),
        }


@router.get("/", response_class=HTMLResponse)
def list_cases(request: Request, q: str | None = Query(default=None), uf: str | None = Query(default=None), status: str | None = Query(default=None), page: int = Query(default=1, ge=1), per_page: int = Query(default=30, ge=10, le=100)):
    clauses = []
    params: list[object] = []
    if q:
        wildcard = f"%{q.strip()}%"
        clauses.append("(CAST(cnpd_id AS TEXT) LIKE ? OR nome LIKE ? COLLATE NOCASE OR local_registro LIKE ? COLLATE NOCASE)")
        params.extend([wildcard, wildcard, wildcard])
    if uf:
        clauses.append("uf_registro = ?")
        params.append(uf.upper())
    if status:
        clauses.append("status_fonte = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * per_page
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM casos {where}", params).fetchone()[0]
        cases = conn.execute(f"SELECT cnpd_id, nome, sexo, uf_registro, local_registro, data_desaparecimento, status_fonte, prioridade, status_investigacao FROM casos {where} ORDER BY data_desaparecimento DESC, cnpd_id DESC LIMIT ? OFFSET ?", [*params, per_page, offset]).fetchall()
        ufs = conn.execute("SELECT DISTINCT uf_registro FROM casos WHERE uf_registro IS NOT NULL ORDER BY uf_registro").fetchall()
    return templates.TemplateResponse(request=request, name="index.html", context={"cases": cases, "ufs": [row[0] for row in ufs], "q": q or "", "selected_uf": uf or "", "selected_status": status or "", "page": page, "per_page": per_page, "total": total, "total_pages": max(1, (total + per_page - 1) // per_page)})


@router.get("/casos/{cnpd_id}", response_class=HTMLResponse)
def case_detail(request: Request, cnpd_id: int):
    data = load_case_rows(cnpd_id)
    return templates.TemplateResponse(request=request, name="case_detail.html", context=data)


@router.post("/casos/{cnpd_id}/evidencias")
def add_evidence(cnpd_id: int, tipo: str = Form(...), valor: str = Form(...), titulo: str = Form(default=""), descricao: str = Form(default=""), url_fonte: str = Form(default=""), classificacao: str = Form(default="DADO_BRUTO"), nivel_confianca: str = Form(default="NAO_AVALIADO"), status_verificacao: str = Form(default="PENDENTE")):
    insert_evidence(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#evidencias", status_code=303)


@router.post("/casos/{cnpd_id}/pessoas")
def add_person(cnpd_id: int, nome: str = Form(...), tipo_relacao: str = Form(default=""), descricao_relacao: str = Form(default=""), email: str = Form(default=""), telefone: str = Form(default=""), localidade: str = Form(default=""), fonte_url: str = Form(default="")):
    insert_person(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#pessoas", status_code=303)


@router.post("/casos/{cnpd_id}/sociais")
def add_social(cnpd_id: int, plataforma: str = Form(...), username: str = Form(default=""), perfil_url: str = Form(default=""), perfil_id: str = Form(default=""), pessoa_relacionada_id: str = Form(default=""), nome_exibicao: str = Form(default=""), observacao: str = Form(default="")):
    insert_social(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#sociais", status_code=303)


@router.post("/casos/{cnpd_id}/localizacoes")
def add_location(cnpd_id: int, latitude: float = Form(...), longitude: float = Form(...), titulo: str = Form(...), descricao: str = Form(default=""), tipo_local: str = Form(default="OUTRO"), precisao_metros: str = Form(default=""), data_evento: str = Form(default=""), fonte_url: str = Form(default=""), nivel_confianca: str = Form(default="NAO_AVALIADO")):
    insert_location(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#mapa", status_code=303)


@router.post("/casos/{cnpd_id}/anotacoes")
def add_note(cnpd_id: int, conteudo: str = Form(...), categoria: str = Form(default="ANOTACAO"), classificacao: str = Form(default="HIPOTESE"), nivel_confianca: str = Form(default="NAO_AVALIADO")):
    insert_note(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#anotacoes", status_code=303)


@router.post("/casos/{cnpd_id}/upload")
def upload_image(cnpd_id: int, file: UploadFile = File(...), descricao: str = Form(default="")):
    content = file.file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo maior que 10 MB.")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Apenas imagens são permitidas.")
    save_upload_base64(cnpd_id, file.filename or "upload.bin", file.content_type or "", content, descricao)
    return RedirectResponse(f"/casos/{cnpd_id}#midias", status_code=303)


@router.get("/midias/{media_id}")
def serve_media(media_id: int):
    with get_connection() as conn:
        media = conn.execute("SELECT caminho_relativo, mime_type, nome_original FROM midias WHERE id = ?", (media_id,)).fetchone()
    if not media or not media["caminho_relativo"]:
        raise HTTPException(status_code=404, detail="Mídia não encontrada.")
    path = Path(media["caminho_relativo"])
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo indisponível.")
    return FileResponse(path, media_type=media["mime_type"] or "application/octet-stream", filename=media["nome_original"] or path.name)


@router.get("/casos/{cnpd_id}/pontos.geojson")
def points_geojson(cnpd_id: int):
    data = build_case_context(cnpd_id)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
                "properties": {key: value for key, value in row.items() if key not in ("longitude", "latitude")},
            }
            for row in data["pontos"]
        ],
    }
