"""
Rotas (Routers) para gerenciamento de casos de desaparecidos.

Este módulo implementa os endpoints da API para:
- Listar e buscar casos (com filtros)
- Visualizar detalhes de um caso específico
- Gerenciar evidências, pessoas, redes sociais e localizações
- Upload de imagens
- Download de mídia em formato GeoJSON

Uso:
    Incluído em app/main.py via app.include_router(cases.router)
"""

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
    delete_evidence,
    delete_person,
    delete_social,
    delete_location,
    delete_note,
    delete_media,
)

# Router com tag "Casos" para documentação da API
router = APIRouter(tags=["Casos"])

# Template engine Jinja2 para renderização de HTML
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def load_case_rows(cnpd_id: int) -> dict:
    """
    Carrega todos os dados associados a um caso do CNPD.

    Recupera o caso principal e todos os registros relacionados:
    - Mídias (imagens)
    - Coletas de dados recentes
    - Evidências
    - Pessoas relacionadas
    - Contas sociais
    - Pontos geográficos
    - Anotações

    Args:
        cnpd_id: Identificador único do caso no CNPD.

    Returns:
        dict: Dicionário com todas as informações do caso.

    Raises:
        HTTPException: 404 se o caso não for encontrado.
    """
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
def list_cases(
    request: Request,
    q: str | None = Query(default=None),
    uf: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=10, le=100),
):
    """
    Lista casos de desaparecidos com paginação e filtros.

    Filtros disponíveis:
    - q: Busca por nome, ID ou local do registro
    - uf: Filtra por Unidade Federativa (estado)
    - status: Filtra por status na fonte (ATIVO_NA_FONTE, etc.)

    Args:
        request: Objeto de requisição FastAPI para template.
        q: Termo de busca opcional.
        uf: Filtro por estado (sigla).
        status: Filtro por status.
        page: Número da página (1-indexed).
        per_page: Registros por página (10-100).

    Returns:
        HTMLResponse: Página renderizada com lista de casos.
    """
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
    """
    Exibe detalhes completos de um caso específico.

    Args:
        request: Objeto de requisição FastAPI para template.
        cnpd_id: Identificador do caso.

    Returns:
        HTMLResponse: Página com todos os dados do caso.
    """
    data = load_case_rows(cnpd_id)
    return templates.TemplateResponse(request=request, name="case_detail.html", context=data)


@router.post("/casos/{cnpd_id}/evidencias")
def add_evidence(cnpd_id: int, tipo: str = Form(...), valor: str = Form(...), titulo: str = Form(default=""), descricao: str = Form(default=""), url_fonte: str = Form(default=""), classificacao: str = Form(default="DADO_BRUTO"), nivel_confianca: str = Form(default="NAO_AVALIADO"), status_verificacao: str = Form(default="PENDENTE")):
    """
    Adiciona uma nova evidência a um caso.

    Args:
        cnpd_id: Identificador do caso.
        tipo: Tipo da evidência (ex: LOCALIZACAO, CONTATO).
        valor: Valor da evidência (texto ou URL).
        titulo: Título/descrição curta.
        descricao: Descrição detalhada.
        url_fonte: URL da fonte da evidência.
        classificacao: DADO_BRUTO, FATO_CONFIRMADO, HIPOTESE, PENDENCIA.
        nivel_confianca: NAO_AVALIADO, BAIXO, MEDIO, ALTO.
        status_verificacao: PENDENTE, CONFIRMADO, REJEITADO.

    Returns:
        RedirectResponse: Redireciona para a seção de evidências do caso.
    """
    insert_evidence(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#evidencias", status_code=303)


@router.post("/casos/{cnpd_id}/pessoas")
def add_person(cnpd_id: int, nome: str = Form(...), tipo_relacao: str = Form(default=""), descricao_relacao: str = Form(default=""), email: str = Form(default=""), telefone: str = Form(default=""), localidade: str = Form(default=""), fonte_url: str = Form(default="")):
    """
    Adiciona uma pessoa relacionada a um caso.

    Args:
        cnpd_id: Identificador do caso.
        nome: Nome da pessoa.
        tipo_relacao: Parente, amigo, autoridade, etc.
        descricao_relacao: Descrição da relação.
        email: Contato por e-mail.
        telefone: Contato por telefone.
        localidade: Cidade/estado da pessoa.
        fonte_url: URL da fonte da informação.

    Returns:
        RedirectResponse: Redireciona para a seção de pessoas do caso.
    """
    insert_person(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#pessoas", status_code=303)


@router.post("/casos/{cnpd_id}/sociais")
def add_social(cnpd_id: int, plataforma: str = Form(...), username: str = Form(default=""), perfil_url: str = Form(default=""), perfil_id: str = Form(default=""), pessoa_relacionada_id: str = Form(default=""), nome_exibicao: str = Form(default=""), observacao: str = Form(default="")):
    """
    Adiciona uma conta de rede social associada ao caso.

    Args:
        cnpd_id: Identificador do caso.
        plataforma: Nome da plataforma (Facebook, Instagram, WhatsApp, etc.).
        username: Nome de usuário.
        perfil_url: URL do perfil.
        perfil_id: ID numérico do perfil.
        pessoa_relacionada_id: ID da pessoa relacionada (opcional).
        nome_exibicao: Nome exibido na plataforma.
        observacao: Observações sobre a conta.

    Returns:
        RedirectResponse: Redireciona para a seção de redes sociais do caso.
    """
    insert_social(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#sociais", status_code=303)


@router.post("/casos/{cnpd_id}/localizacoes")
def add_location(cnpd_id: int, latitude: float = Form(...), longitude: float = Form(...), titulo: str = Form(...), descricao: str = Form(default=""), tipo_local: str = Form(default="OUTRO"), precisao_metros: str = Form(default=""), data_evento: str = Form(default=""), fonte_url: str = Form(default=""), nivel_confianca: str = Form(default="NAO_AVALIADO")):
    """
    Adiciona um ponto geográfico ao caso.

    Args:
        cnpd_id: Identificador do caso.
        latitude: Latitude (deve estar entre -90 e 90).
        longitude: Longitude (deve estar entre -180 e 180).
        titulo: Título do local.
        descricao: Descrição detalhada.
        tipo_local: ULTIMO_LOCAL_CONHECIDO, LOCAL_DESAPARECIMENTO, AVISTAMENTO, RESIDENCIA, OUTRO.
        precisao_metros: Precisão estimada em metros.
        data_evento: Data do evento (formato YYYY-MM-DD).
        fonte_url: Fonte da informação geográfica.
        nivel_confianca: NAO_AVALIADO, BAIXO, MEDIO, ALTO.

    Returns:
        RedirectResponse: Redireciona para a seção de mapa do caso.

    Raises:
        HTTPException: Se latitude/longitude estiverem fora dos limites válidos.
    """
    insert_location(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#mapa", status_code=303)


@router.post("/casos/{cnpd_id}/anotacoes")
def add_note(cnpd_id: int, conteudo: str = Form(...), categoria: str = Form(default="ANOTACAO"), classificacao: str = Form(default="HIPOTESE"), nivel_confianca: str = Form(default="NAO_AVALIADO")):
    """
    Adiciona uma anotação analítica ao caso.

    Args:
        cnpd_id: Identificador do caso.
        conteudo: Texto da anotação.
        categoria: Categoria (ANOTACAO, HIPOTETE, etc.).
        classificacao: HIPOTESE, FATO, CONCLUSAO.
        nivel_confianca: NAO_AVALIADO, BAIXO, MEDIO, ALTO.

    Returns:
        RedirectResponse: Redireciona para a seção de anotações do caso.
    """
    insert_note(cnpd_id, locals())
    return RedirectResponse(f"/casos/{cnpd_id}#anotacoes", status_code=303)


@router.post("/casos/{cnpd_id}/upload")
def upload_image(cnpd_id: int, file: UploadFile = File(...), descricao: str = Form(default="")):
    """
    Realiza upload de uma imagem para um caso.

    O arquivo é salvo em base64 no banco e em disco localmente.
    Limite de tamanho: 10 MB.
    Formatos aceitos: qualquer tipo de imagem (verificado pelo content-type).

    Args:
        cnpd_id: Identificador do caso.
        file: Arquivo de imagem a ser carregado.
        descricao: Descrição opcional da imagem.

    Returns:
        RedirectResponse: Redireciona para a seção de mídias do caso.

    Raises:
        HTTPException: 413 se arquivo > 10MB, 415 se não for imagem.
    """
    content = file.file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo maior que 10 MB.")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Apenas imagens são permitidas.")
    save_upload_base64(cnpd_id, file.filename or "upload.bin", file.content_type or "", content, descricao)
    return RedirectResponse(f"/casos/{cnpd_id}#midias", status_code=303)


@router.get("/midias/{media_id}")
def serve_media(media_id: int):
    """
    Servir uma mídia (arquivo) pelo ID.

    Args:
        media_id: ID da mídia no banco.

    Returns:
        FileResponse: Arquivo solicitado com tipo MIME correto.

    Raises:
        HTTPException: 404 se mídia não for encontrada ou arquivo ausente.
    """
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
    """
    Retorna pontos geográficos do caso em formato GeoJSON.

    Útil para visualização em mapas(interativos.

    Args:
        cnpd_id: Identificador do caso.

    Returns:
        dict: GeoJSON FeatureCollection com pontos do caso.
    """
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


@router.get(
    "/guia-procedimentos",
    response_class=HTMLResponse,
)
def procedures_guide():
    """
    Entrega o guia educacional local e autocontido.

    O guia fornece instruções detalhadas para procedimentos OSINT
    aplicáveis a investigações de pessoas desaparecidas.

    Returns:
        FileResponse: Arquivo HTML do guia de procedimentos.

    Raises:
        HTTPException: 404 se o guia não for encontrado.
    """
    guide_path = (
        BASE_DIR
        / "app"
        / "static"
        / "guia_procedimentos_osint_frontend.html"
    )

    if not guide_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Guia não encontrado no caminho esperado: "
                f"{guide_path}"
            ),
        )

    return FileResponse(
        path=str(guide_path),
        media_type="text/html; charset=utf-8",
        filename="guia_procedimentos_osint_frontend.html",
    )


# ─── Endpoints de exclusão de dados do caso ─────────────────────────────

@router.post("/casos/{cnpd_id}/evidencias/{evidencia_id}/remover")
def remove_evidence(cnpd_id: int, evidencia_id: int):
    """Remove uma evidência do caso."""
    if not delete_evidence(cnpd_id, evidencia_id):
        raise HTTPException(404, "Evidência não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#evidencias", status_code=303)


@router.post("/casos/{cnpd_id}/pessoas/{pessoa_id}/remover")
def remove_person(cnpd_id: int, pessoa_id: int):
    """Remove uma pessoa relacionada do caso."""
    if not delete_person(cnpd_id, pessoa_id):
        raise HTTPException(404, "Pessoa não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#pessoas", status_code=303)


@router.post("/casos/{cnpd_id}/sociais/{social_id}/remover")
def remove_social(cnpd_id: int, social_id: int):
    """Remove uma conta social do caso."""
    if not delete_social(cnpd_id, social_id):
        raise HTTPException(404, "Conta social não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#sociais", status_code=303)


@router.post("/casos/{cnpd_id}/localizacoes/{location_id}/remover")
def remove_location(cnpd_id: int, location_id: int):
    """Remove um ponto geográfico do caso."""
    if not delete_location(cnpd_id, location_id):
        raise HTTPException(404, "Localização não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#mapa", status_code=303)


@router.post("/casos/{cnpd_id}/anotacoes/{note_id}/remover")
def remove_note(cnpd_id: int, note_id: int):
    """Remove uma anotação do caso."""
    if not delete_note(cnpd_id, note_id):
        raise HTTPException(404, "Anotação não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#anotacoes", status_code=303)


@router.post("/casos/{cnpd_id}/midias/{media_id}/remover")
def remove_media(cnpd_id: int, media_id: int):
    """Remove uma mídia do caso (arquivo também é deletado)."""
    if not delete_media(cnpd_id, media_id):
        raise HTTPException(404, "Mídia não encontrada.")
    return RedirectResponse(f"/casos/{cnpd_id}#midias", status_code=303)