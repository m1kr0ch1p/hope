"""
Rotas (Routers) para visualização e geração de grafos de conexões.

Este módulo implementa os endpoints para:
- Gerar novo grafo via IA local (Ollama)
- Exibir página interativa do grafo (Cytoscape.js)
- Atualizar status do grafo (confirmado/ignorar)
- Listar nós e arestas em formato JSON para front-end

Uso:
    Incluído em app/main.py via app.include_router(graph.router)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import get_connection
from app.services.graph_service import (
    generate_graph_via_llm,
    get_graph_for_case,
    save_graph_to_db,
    get_grafo_id,
    atualizar_nó,
    atualizar_aresta,
    adicionar_nó,
    adicionar_aresta,
    remover_nó,
    remover_aresta,
)
from app.services.investigation_service import build_case_context

router = APIRouter(
    prefix="/grafos",
    tags=["Grafos de conexões"],
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "app" / "templates"),
)


def _ensure_case(cnpd_id: int) -> None:
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM casos WHERE cnpd_id = ?", (cnpd_id,)
        ).fetchone():
            raise HTTPException(
                status_code=404, detail=f"Caso CNPD {cnpd_id} não encontrado."
            )


def _load_case_extra(cnpd_id: int) -> dict[str, Any]:
    """Carrega os dados básicos do caso para o template."""
    with get_connection() as conn:
        case = conn.execute(
            "SELECT * FROM casos WHERE cnpd_id = ?", (cnpd_id,)
        ).fetchone()
        return dict(case) if case else {}


@router.get("/casos/{cnpd_id}", response_class=HTMLResponse)
def view_graph_page(request: Request, cnpd_id: int):
    """
    Exibe a página interativa do grafo de conexões.

    Carrega o último grafo salvo (ou vazio se não houver)
    e o contexto do caso para renderização.
    """
    _ensure_case(cnpd_id)
    grafo_data = get_graph_for_case(cnpd_id)
    case_data = _load_case_extra(cnpd_id)

    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context={
            "cnpd_id": cnpd_id,
            "case": case_data,
            "grafo": grafo_data,
            "titulo_página": f"Grafo de conexões — CNPD #{cnpd_id}",
        },
    )


@router.post("/casos/{cnpd_id}/gerar", response_class=HTMLResponse)
def generate_graph(request: Request, cnpd_id: int):
    """
    Gera um novo grafo de conexões via Ollama (qwen3.5:latest).

    Requer que o serviço Ollama esteja rodando em
    http://127.0.0.1:11434.

    Após geração, salva no banco e redireciona para a página do grafo.
    """
    _ensure_case(cnpd_id)

    try:
        context = build_case_context(cnpd_id)
        result = generate_graph_via_llm(context)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar grafo: {type(exc).__name__}: {exc}",
        ) from exc

    grafo_id = save_graph_to_db(cnpd_id, result)

    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context={
            "cnpd_id": cnpd_id,
            "case": _load_case_extra(cnpd_id),
            "grafo": get_graph_for_case(cnpd_id),
            "titulo_página": f"Grafo de conexões — CNPD #{cnpd_id}",
            "mensagem_sucesso": True,
        },
    )


@router.get("/casos/{cnpd_id}/api/nós", response_model=list[dict[str, Any]])
def list_nós(cnpd_id: int):
    """
    Retorna a lista de nós do último grafo em formato JSON para front-end.

    Útil para front-end consome diretamente e atualiza o grafo sem recarregar.
    """
    _ensure_case(cnpd_id)
    grafo = get_graph_for_case(cnpd_id)
    if not grafo:
        return []
    return grafo.get("nós", [])


@router.get("/casos/{cnpd_id}/api/arestas", response_model=list[dict[str, Any]])
def list_arestas(cnpd_id: int):
    """
    Retorna a lista de arestas do último grafo em formato JSON para front-end.
    """
    _ensure_case(cnpd_id)
    grafo = get_graph_for_case(cnpd_id)
    if not grafo:
        return []
    return grafo.get("arestas", [])


@router.post("/casos/{cnpd_id}/confirmar")
def confirmar_grafo(request: Request, cnpd_id: int):
    """
    Marca o grafo atual como confirmado pelo investigador.

    Args:
        cnpd_id: ID do caso.

    Returns:
        Redirect para a página do grafo.
    """
    _ensure_case(cnpd_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM grafos_conexoes WHERE cnpd_id = ? ORDER BY id DESC LIMIT 1",
            (cnpd_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE grafos_conexoes SET status = 'CONFIRMADO' WHERE id = ?",
                (row["id"],),
            )
    return HTMLResponse(
        status_code=200,
        content=f"<script>window.location.href='/grafos/casos/{cnpd_id}';</script>",
        media_type="text/html",
    )


@router.post("/casos/{cnpd_id}/regerar")
def regerar_grafo(request: Request, cnpd_id: int):
    """
    Define o status do grafo como RASCUNHO para forçar nova geração.

    Args:
        cnpd_id: ID do caso.

    Returns:
        Redirect para a página do grafo.
    """
    _ensure_case(cnpd_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM grafos_conexoes WHERE cnpd_id = ? ORDER BY id DESC LIMIT 1",
            (cnpd_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE grafos_conexoes SET status = 'RASCUNHO' WHERE id = ?",
                (row["id"],),
            )
    return HTMLResponse(
        status_code=200,
        content=f"<script>window.location.href='/grafos/casos/{cnpd_id}';</script>",
        media_type="text/html",
    )


# ─── API de edição do grafo ────────────────────────────────────────────

@router.get("/casos/{cnpd_id}/api/grafo")
def api_obter_grafo(cnpd_id: int):
    """Retorna o grafo completo (nós + arestas + metadados) em JSON."""
    _ensure_case(cnpd_id)
    return get_graph_for_case(cnpd_id)


@router.post("/casos/{cnpd_id}/api/nós", response_model=dict[str, Any])
def api_adicionar_nó(cnpd_id: int, tipo_nó: str = Form(default="OUTRO"),
                     grupo_nó: str = Form(default="investigador"),
                     rótulo: str = Form(...),
                     subtítulo: str = Form(default=""),
                     valor_principal: str = Form(default=""),
                     nível_confianca: str = Form(default="INVESTIGADOR"),
                     observação: str = Form(default="")):
    """Adiciona um novo nó ao grafo manualmente pelo investigador."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id) or save_graph_to_db(
        cnpd_id,
        {"grafo": {"nós": [], "arestas": []}, "modelo": "manual", "métricas": {}, "prompt_contexto": ""},
    )
    if not gid:
        raise HTTPException(500, "Não foi possível criar o grafo.")
    nó_id = adicionar_nó(gid, tipo_nó=tipo_nó, grupo_nó=grupo_nó,
                          rótulo=rótulo, subtítulo=subtítulo,
                          valor_principal=valor_principal,
                          nível_confianca=nível_confianca)
    if not nó_id:
        raise HTTPException(400, "Rótulo inválido.")
    # Recarrega o grafo para retornar o estado atualizado
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Nó adicionado manualmente."
    return grafo


@router.post("/casos/{cnpd_id}/api/arestas", response_model=dict[str, Any])
def api_adicionar_aresta(cnpd_id: int, origem_id: int = Form(...),
                         destino_id: int = Form(...),
                         tipo_relação: str = Form(default="OUTRO"),
                         rótulo_aresta: str = Form(default=""),
                         nível_confianca: str = Form(default="INVESTIGADOR"),
                         observação: str = Form(default="")):
    """Adiciona uma nova aresta manualmente."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado para este caso.")
    aresta_id = adicionar_aresta(gid, origem_id, destino_id,
                                  tipo_relação=tipo_relação,
                                  rótulo_aresta=rótulo_aresta,
                                  nível_confianca=nível_confianca,
                                  observação=observação)
    if not aresta_id:
        raise HTTPException(400, "Não foi possível criar a aresta (origem/destino inválidos ou iguais).")
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Aresta adicionada manualmente."
    return grafo


@router.post("/casos/{cnpd_id}/api/nós/{no_id}/atualizar", response_model=dict[str, Any])
def api_atualizar_nó(cnpd_id: int, no_id: int,
                     tipo_nó: str | None = Form(default=None),
                     grupo_nó: str | None = Form(default=None),
                     rótulo: str | None = Form(default=None),
                     subtítulo: str | None = Form(default=None),
                     valor_principal: str | None = Form(default=None),
                     nível_confianca: str | None = Form(default=None)):
    """Atualiza um nó existente."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado.")
    ok = atualizar_nó(gid, no_id, tipo_nó=tipo_nó, grupo_nó=grupo_nó,
                       rótulo=rótulo, subtítulo=subtítulo,
                       valor_principal=valor_principal,
                       nível_confianca=nível_confianca)
    if not ok:
        raise HTTPException(404, "Nó não encontrado ou não pertence a este grafo.")
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Nó atualizado."
    return grafo


@router.post("/casos/{cnpd_id}/api/arestas/{a_id}/atualizar", response_model=dict[str, Any])
def api_atualizar_aresta(cnpd_id: int, a_id: int,
                         tipo_relação: str | None = Form(default=None),
                         rótulo_aresta: str | None = Form(default=None),
                         nível_confianca: str | None = Form(default=None),
                         observação: str | None = Form(default=None)):
    """Atualiza uma aresta existente."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado.")
    ok = atualizar_aresta(gid, a_id, tipo_relação=tipo_relação,
                          rótulo_aresta=rótulo_aresta,
                          nível_confianca=nível_confianca,
                          observação=observação)
    if not ok:
        raise HTTPException(404, "Aresta não encontrada.")
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Aresta atualizada."
    return grafo


@router.post("/casos/{cnpd_id}/api/nós/{no_id}/remover", response_model=dict[str, Any])
def api_remover_nó(cnpd_id: int, no_id: int):
    """Remove um nó e todas as arestas conectadas a ele."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado.")
    if not remover_nó(gid, no_id):
        raise HTTPException(404, "Nó não encontrado.")
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Nó removido."
    return grafo


@router.post("/casos/{cnpd_id}/api/arestas/{a_id}/remover", response_model=dict[str, Any])
def api_remover_aresta(cnpd_id: int, a_id: int):
    """Remove uma aresta específica."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado.")
    if not remover_aresta(gid, a_id):
        raise HTTPException(404, "Aresta não encontrada.")
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = "Aresta removida."
    return grafo


@router.post("/casos/{cnpd_id}/api/grafo/sincronizar")
def api_sincronizar_grafo(cnpd_id: int):
    """Recalcula as arestas baseadas nos nós atuais (linkagem automática)."""
    _ensure_case(cnpd_id)
    gid = get_grafo_id(cnpd_id)
    if not gid:
        raise HTTPException(404, "Grafo não encontrado.")
    with get_connection() as conn:
        # Remove todas as arestas atuais
        conn.execute("DELETE FROM grafos_arestas WHERE grafo_id = ?", (gid,))
        # Reconstrói: conecta nós que compartilham valor_principal similar ou mesmo grupo
        nós = conn.execute(
            "SELECT id, rótulo, valor_principal, tipo_nó, grupo_nó FROM grafos_nós WHERE grafo_id = ? ORDER BY id",
            (gid,),
        ).fetchall()
        created = 0
        for i in range(len(nós)):
            for j in range(i + 1, len(nós)):
                a = nós[i]
                b = nós[j]
                # Pula se um dos dois for o nó central
                if a["grupo_nó"] == "central" and b["grupo_nó"] == "central":
                    continue
                # Tenta conectar se houver correspondência de valor ou relação temática
                vp_a = (a["valor_principal"] or "").strip().lower()
                vp_b = (b["valor_principal"] or "").strip().lower()
                rot_a = (a["rótulo"] or "").strip().lower()
                rot_b = (b["rótulo"] or "").strip().lower()
                tipo_a = (a["tipo_nó"] or "").strip()
                tipo_b = (b["tipo_nó"] or "").strip()
                should_link = False
                motivo = ""
                if vp_a and vp_a == vp_b and a["id"] != b["id"]:
                    should_link = True
                    motivo = "mesmo valor"
                elif rot_a and rot_a == rot_b and a["id"] != b["id"] and tipo_a != tipo_b:
                    should_link = True
                    motivo = "mesmo rótulo, tipo diferente"
                elif tipo_a in ("LOCAL", "ENDEREÇO", "LOCAL_GEOGRÁFICO") and tipo_b == "PESSOA_RELACIONADA":
                    should_link = True
                    motivo = "pessoa em local"
                elif tipo_b in ("LOCAL", "ENDEREÇO", "LOCAL_GEOGRÁFICO") and tipo_a == "PESSOA_RELACIONADA":
                    should_link = True
                    motivo = "pessoa em local"
                if should_link:
                    obs = f"{motivo} ({motivo})"
                    conn.execute(
                        """INSERT INTO grafos_arestas
                           (grafo_id, nó_origem, nó_destino, tipo_relação,
                            rótulo_aresta, origem_aresta, nível_confianca, observação)
                           VALUES (?, ?, ?, 'RELACIONADO', ?, 'SINTETICO', 'MÉDIA', ?)""",
                        (gid, a["id"], b["id"], motivo, obs),
                    )
                    created += 1
    grafo = get_graph_for_case(cnpd_id)
    grafo["mensagem"] = f"{created} arestas reconstruídas automaticamente."
    return grafo
