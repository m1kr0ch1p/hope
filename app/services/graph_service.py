"""
Serviço de geração e gerenciamento de grafos de conexões via IA local (Ollama).

Usa qwen3.5:latest com format='json'. O JSON pode vir no campo 'thinking'
ou 'response' e pode ser truncado — o serviço tenta reconstruir.

Uso:
    from app.services.graph_service import build_graph_via_llm, get_graph_for_case
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import requests

from app.config import (OLLAMA_GENERATE_URL, OLLAMA_MODEL,
                        OLLAMA_NUM_PREDICT, OLLAMA_TIMEOUT_SECONDS,
                        OLLAMA_TEMPERATURE)
from app.database import get_connection
from app.services.investigation_service import build_case_context


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


GRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "nós": {
            "type": "array", "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "tipo": {"type": "string"},
                    "rótulo": {"type": "string"},
                    "subtítulo": {"type": "string"},
                    "valor_principal": {"type": "string"},
                    "grupo": {"type": "string"},
                },
                "required": ["id", "tipo", "rótulo"],
            },
        },
        "arestas": {
            "type": "array", "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "origem": {"type": "string"},
                    "destino": {"type": "string"},
                    "tipo_relação": {"type": "string"},
                    "rótulo": {"type": "string"},
                    "confiança": {"type": "string"},
                    "observação": {"type": "string"},
                },
                "required": ["id", "origem", "destino", "tipo_relação"],
            },
        },
    },
    "required": ["nós", "arestas"],
}


def build_graph_prompt(case_context):
    """Monta o prompt para o Ollama."""
    dados = case_context["caso"]
    evidences = case_context["evidencias"]
    people = case_context["pessoas"]
    socials = case_context["redes_sociais"]
    locations = case_context["pontos"]
    notes = case_context["anotacoes"]
    media = case_context["midias"]

    def chunk(items, fields):
        return [{k: it.get(k) for k in fields if it.get(k)} for it in items]

    # Dados enxutos para caberem no contexto
    prompt_data = {
        "id_caso": dados.get("cnpd_id"),
        "nome": dados.get("nome"),
        "sexo": dados.get("sexo"),
        "idade_desaparecimento": dados.get("idade_desaparecimento"),
        "raca_cor": dados.get("raca_cor"),
        "local": dados.get("local_registro"),
        "uf": dados.get("uf_registro"),
        "data_desaparecimento": dados.get("data_desaparecimento"),
        "localizacao_confirmada": dados.get("localizacao_confirmada"),
        "evidencias": chunk(evidences, ["tipo", "titulo", "valor", "data_evento"]),
        "pessoas": chunk(people, ["nome", "tipo_relacao", "telefone", "email"]),
        "redes_sociais": chunk(socials, ["plataforma", "username", "perfil_url"]),
        "pontos": chunk(locations, ["titulo", "latitude", "longitude", "tipo_local"]),
        "anotacoes": chunk(notes, ["categoria", "conteudo"]),
        "midias": chunk(media, ["nome_original", "descricao"]),
    }

    ctx_json = json.dumps(prompt_data, ensure_ascii=False, indent=2)

    return f"""
Você é um analista OSINT. Recebemos dados de um caso de pessoa desaparecida.
Tarefa: gerar um grafo de nós e arestas representando conexões entre os dados.

REGRAS:
- Nó central SEMPRE: id="central", tipo="PESSOA_DESAPARECIDA", rótulo=nome do desaparecido.
- Novos nós para cada dado distinto detectado.
- Arestas só entre nós declarados; use os "id" dos nós como origem/destino.
- Inclua relação quando houver co-ocorrência (mesmo local, foto, fonte, documento, telefone, email, pessoa).
- confiança: "ALTA" para oficiais; "MÉDIA" para evidências; "IA_SUGERIDO" para inferências.
- RETORNE APENAS O JSON. Sem explicações, sem markdown.

Schema: {json.dumps(GRAPH_SCHEMA, ensure_ascii=False, indent=2)}
Dados: {ctx_json}
""".strip()


def _request(payload):
    r = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Resposta Ollama não é objeto JSON.")
    return data


def _close_json(text):
    """Fecha colchetes/fchaves não fechados."""
    ob = text.count("{") - text.count("}")
    oa = text.count("[") - text.count("]")
    extra = ""
    if oa > 0:
        extra += "]" * oa
    if ob > 0:
        extra += "}" * ob
    return text + extra


def _extract_graph(result):
    """
    Extrai o JSON de grafo. qwen3.5 com format='json' coloca no campo
    'thinking'. Pode vir truncado — tentamos fechar automaticamente.
    """
    raw = result.get("thinking", "") or result.get("response", "")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Ollama sem resposta. done_reason={result.get('done_reason')!r}")

    raw = raw.strip()
    if raw.startswith("Thinking Process:"):
        raw = raw.split("\n\n", 1)[-1] if "\n\n" in raw else raw

    # 1) Parse direto
    if raw.startswith("{"):
        try:
            p = json.loads(raw)
            if isinstance(p, dict) and "nós" in p and "arestas" in p:
                return p
        except json.JSONDecodeError:
            pass

    # 2) Fechar e tentar
    try:
        p = json.loads(_close_json(raw))
        if isinstance(p, dict) and "nós" in p and "arestas" in p:
            return p
    except json.JSONDecodeError:
        pass

    # 3) Regex greedy para achar o maior bloco que começa com { e contém "nós"
    m = re.search(r"\{[\s\S]*\"nós\"[\s\S]*\}", raw)
    if m:
        try:
            p = json.loads(_close_json(m.group()))
            if isinstance(p, dict) and "nós" in p and "arestas" in p:
                return p
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível extrair JSON de grafo. Amostra: {raw[:500]!r}")


def generate_graph_via_llm(case_context):
    """Gera grafo via Ollama (qwen3.5:latest, format=json)."""
    prompt = build_graph_prompt(case_context)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": OLLAMA_TEMPERATURE,
                    "num_predict": max(15000, OLLAMA_NUM_PREDICT),
                    "seed": 42},
        "keep_alive": "10m",
    }
    try:
        result = _request(payload)
        grafo = _extract_graph(result)
        return {
            "grafo": grafo,
            "modelo": result.get("model", OLLAMA_MODEL),
            "métricas": {
                "total_duration": result.get("total_duration"),
                "prompt_eval_count": result.get("prompt_eval_count"),
                "eval_count": result.get("eval_count"),
                "done_reason": result.get("done_reason"),
            },
            "prompt_contexto": prompt,
        }
    except requests.ConnectionError as e:
        raise ConnectionError("Ollama não está acessível em http://127.0.0.1:11434") from e
    except requests.Timeout as e:
        raise TimeoutError("Ollama excedeu o tempo limite de geração.") from e


def save_graph_to_db(cnpd_id, result):
    """Persiste o grafo no banco."""
    nós = result["grafo"].get("nós", [])
    arestas = result["grafo"].get("arestas", [])

    with get_connection() as conn:
        cur = conn.execute(
            "SELECT id FROM grafos_conexoes WHERE cnpd_id=? ORDER BY id DESC LIMIT 1",
            (cnpd_id,))
        row = cur.fetchone()
        if row:
            gid = row["id"]
            conn.execute(
                "UPDATE grafos_conexoes SET status=?,gerado_em=?,modelo_ia=?,resposta_json=?,metros_json=?,prompt_contexto_json=? WHERE id=?",
                ("RASCUNHO", utc_now(), result["modelo"],
                 json.dumps(result["grafo"], ensure_ascii=False, indent=2),
                 json.dumps(result["métricas"], ensure_ascii=False, indent=2),
                 result["prompt_contexto"], gid))
        else:
            cur = conn.execute(
                "INSERT INTO grafos_conexoes (cnpd_id,gerado_em,modelo_ia,resposta_json,metros_json,prompt_contexto_json) VALUES (?,?,?,?,?,?)",
                (cnpd_id, utc_now(), result["modelo"],
                 json.dumps(result["grafo"], ensure_ascii=False, indent=2),
                 json.dumps(result["métricas"], ensure_ascii=False, indent=2),
                 result["prompt_contexto"]))
            gid = cur.lastrowid

        conn.execute("DELETE FROM grafos_arestas WHERE grafo_id=?", (gid,))
        conn.execute("DELETE FROM grafos_nós WHERE grafo_id=?", (gid,))

        # Salva cada nó e guarda o id original do Ollama em dados_extras_json
        for nó in nós:
            id_ollama = nó.get("id", "")
            extras = {
                k: v for k, v in nó.items()
                if k not in ("id", "tipo", "rótulo", "subtítulo", "valor_principal", "grupo")
            }
            if id_ollama and id_ollama not in extras:
                extras["id_ollama"] = id_ollama
            conn.execute(
                "INSERT INTO grafos_nós (grafo_id,origem,tipo_nó,grupo_nó,rótulo,subtítulo,valor_principal,dados_extras_json,nível_confianca) VALUES (?,?,?,?,?,?,?,?,?)",
                (gid, "IA", nó.get("tipo", "OUTRO"), nó.get("grupo", "investigador"),
                 nó.get("rótulo", ""), nó.get("subtítulo", ""),
                 nó.get("valor_principal", ""),
                 json.dumps(extras, ensure_ascii=False) or None,
                 "IA_SUGERIDO"))

        # Indexa por rótulo, valor_principal E id_ollama (para resolver arestas)
        idx = {}
        id_ollama_map = {}
        for n in conn.execute("SELECT id,rótulo,valor_principal,dados_extras_json FROM grafos_nós WHERE grafo_id=?", (gid,)):
            r = n["rótulo"]
            vp = n["valor_principal"] or ""
            idx[r] = n["id"]
            if vp:
                idx[vp] = n["id"]
            extras = n["dados_extras_json"]
            if extras:
                try:
                    d = json.loads(extras)
                    oid = d.get("id_ollama", "")
                    if oid:
                        id_ollama_map[oid] = n["id"]
                except (json.JSONDecodeError, TypeError):
                    pass

        for a in arestas:
            # Tenta resolver origem/destino por id_ollama primeiro, depois por rótulo/valor_principal
            o_oid = a.get("origem", "")
            d_oid = a.get("destino", "")
            oid = id_ollama_map.get(o_oid)
            did = id_ollama_map.get(d_oid)
            if not oid:
                oid = idx.get(o_oid)
            if not did:
                did = idx.get(d_oid)
            if not oid or not did or oid == did:
                print(f"  Aresta ignorada: {a.get('id','?')} o={o_oid!r} d={d_oid!r}")
                continue
            conn.execute(
                "INSERT INTO grafos_arestas (grafo_id,nó_origem,nó_destino,tipo_relação,rótulo_aresta,origem_aresta,nível_confianca,observação) VALUES (?,?,?,?,?,?,?,?)",
                (gid, oid, did, a.get("tipo_relação", "OUTRO"),
                 a.get("rótulo", ""), "IA_SUGERIDO", a.get("confiança", "IA_SUGERIDO"),
                 a.get("observação", "")))

    return gid


def get_graph_for_case(cnpd_id):
    """Recupera o último grafo de um caso."""
    with get_connection() as conn:
        g = conn.execute(
            "SELECT * FROM grafos_conexoes WHERE cnpd_id=? ORDER BY id DESC LIMIT 1",
            (cnpd_id,)).fetchone()
        if not g:
            return {}

        ns = conn.execute("SELECT * FROM grafos_nós WHERE grafo_id=? ORDER BY id", (g["id"],)).fetchall()
        es = conn.execute("""SELECT a.*, o.rótulo AS origem_rótulo, d.rótulo AS destino_rótulo
            FROM grafos_arestas a
            JOIN grafos_nós o ON o.id=a.nó_origem
            JOIN grafos_nós d ON d.id=a.nó_destino
            WHERE a.grafo_id=?
            ORDER BY a.id""", (g["id"],)).fetchall()

        return {
            "grafo_id": g["id"], "status": g["status"],
            "gerado_em": g["gerado_em"], "modelo_ia": g["modelo_ia"],
            "gerado_por": g["gerado_por"],
            "nós": [dict(n) for n in ns],
            "arestas": [dict(e) for e in es],
            "resposta_json": json.loads(g["resposta_json"]) if g["resposta_json"] else None,
        }


def compare_and_merge_graphs(existing, nova_resposta):
    """Compara grafos para revisão."""
    if not existing:
        return {"diferenças": {}, "novo_grafo_id": None}
    ex_ns = {(n["rótulo"], n.get("valor_principal")) for n in existing.get("nós", [])}
    ex_es = {(a["origem_rótulo"], a["destino_rótulo"], a["tipo_relação"]) for a in existing.get("arestas", [])}
    ns = nova_resposta["grafo"].get("nós", [])
    es = nova_resposta["grafo"].get("arestas", [])
    nids = {(n.get("id",""), n.get("rótulo","")) for n in ns}
    return {
        "diferenças": {
            "nós_adicionados": len([n for n in ns if (n.get("id",""), n.get("rótulo","")) not in ex_ns]),
            "nós_removidos": len([n for n in existing["nós"] if (n.get("id",""), n.get("rótulo","")) not in nids]),
            "arestas_entidade": es,
        },
        "nova_resposta": nova_resposta,
    }


def get_grafo_id(cnpd_id: int) -> int | None:
    """Retorna o ID do último grafo de um caso, ou None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM grafos_conexoes WHERE cnpd_id = ? ORDER BY id DESC LIMIT 1",
            (cnpd_id,),
        ).fetchone()
        return row["id"] if row else None


def atualizar_nó(grafo_id: int, nó_id: int, **updates) -> bool:
    """Atualiza propriedades de um nó existente.

    Campos permitidos: tipo_nó, grupo_nó, rótulo, subtítulo,
    valor_principal, nível_confianca, dados_extras_json.
    """
    permitidos = {
        "tipo_nó", "grupo_nó", "rótulo", "subtítulo",
        "valor_principal", "nível_confianca", "dados_extras_json",
    }
    campos = {k: v for k, v in updates.items() if k in permitidos and v is not None}
    if not campos:
        return False
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [nó_id, grafo_id]
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE grafos_nós SET {sets} WHERE id = ? AND grafo_id = ?",
            valores,
        )
        return cur.rowcount > 0


def atualizar_aresta(grafo_id: int, aresta_id: int, **updates) -> bool:
    """Atualiza propriedades de uma aresta existente.

    Campos permitidos: tipo_relação, rótulo_aresta, nível_confianca, observação.
    """
    permitidos = {"tipo_relação", "rótulo_aresta", "nível_confianca", "observação"}
    campos = {k: v for k, v in updates.items() if k in permitidos and v is not None}
    if not campos:
        return False
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [aresta_id, grafo_id]
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE grafos_arestas SET {sets} WHERE id = ? AND grafo_id = ?",
            valores,
        )
        return cur.rowcount > 0


def adicionar_nó(grafo_id: int, **dados) -> int | None:
    """Adiciona um novo nó ao grafo. Retorna o ID do nó criado, ou None em erro."""
    permitidos = {
        "tipo_nó", "grupo_nó", "rótulo", "subtítulo",
        "valor_principal", "nível_confianca", "dados_extras_json",
    }
    campos = {k: v for k, v in dados.items() if k in permitidos}
    rótulo = campos.pop("rótulo", "").strip()
    if not rótulo:
        return None
    extras = {
        k: v for k, v in campos.items()
        if k not in ("tipo_nó", "grupo_nó", "subtítulo", "valor_principal", "nível_confianca")
    }
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO grafos_nós
               (grafo_id, origem, tipo_nó, grupo_nó, rótulo, subtítulo,
                valor_principal, dados_extras_json, nível_confianca)
               VALUES (?, 'INVESTIGADOR', ?, ?, ?, ?, ?, ?, ?)""",
            (
                grafo_id,
                campos.get("tipo_nó", "OUTRO"),
                campos.get("grupo_nó", "investigador"),
                rótulo,
                campos.get("subtítulo", ""),
                campos.get("valor_principal", ""),
                json.dumps(extras, ensure_ascii=False) or None,
                campos.get("nível_confianca", "INVESTIGADOR"),
            ),
        )
        return cur.lastrowid


def adicionar_aresta(grafo_id: int, origem_id: int, destino_id: int, **dados) -> int | None:
    """Adiciona uma nova aresta. Retorna o ID da aresta criada, ou None em erro."""
    if origem_id == destino_id:
        return None
    permitidos = {"tipo_relação", "rótulo_aresta", "nível_confianca", "observação"}
    campos = {k: v for k, v in dados.items() if k in permitidos}
    with get_connection() as conn:
        o = conn.execute(
            "SELECT 1 FROM grafos_nós WHERE id = ? AND grafo_id = ?",
            (origem_id, grafo_id),
        ).fetchone()
        d = conn.execute(
            "SELECT 1 FROM grafos_nós WHERE id = ? AND grafo_id = ?",
            (destino_id, grafo_id),
        ).fetchone()
        if not o or not d:
            return None
        cur = conn.execute(
            """INSERT INTO grafos_arestas
               (grafo_id, nó_origem, nó_destino, tipo_relação,
                rótulo_aresta, origem_aresta, nível_confianca, observação)
               VALUES (?, ?, ?, ?, ?, 'INVESTIGADOR', ?, ?)""",
            (
                grafo_id,
                origem_id,
                destino_id,
                campos.get("tipo_relação", "OUTRO"),
                campos.get("rótulo_aresta", ""),
                campos.get("nível_confianca", "INVESTIGADOR"),
                campos.get("observação", ""),
            ),
        )
        return cur.lastrowid


def remover_nó(grafo_id: int, nó_id: int) -> bool:
    """Remove um nó e todas as arestas conectadas a ele."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM grafos_nós WHERE id = ? AND grafo_id = ?",
            (nó_id, grafo_id),
        )
        if cur.rowcount > 0:
            conn.execute(
                "DELETE FROM grafos_arestas WHERE nó_origem = ? OR nó_destino = ?",
                (nó_id, nó_id),
            )
            return True
        return False


def remover_aresta(grafo_id: int, aresta_id: int) -> bool:
    """Remove uma aresta específica."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM grafos_arestas WHERE id = ? AND grafo_id = ?",
            (aresta_id, grafo_id),
        )
        return cur.rowcount > 0
