from __future__ import annotations

import json
from typing import Any

import requests

from app.config import (
    OLLAMA_GENERATE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT_SECONDS,
)


REPORT_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "resumo_executivo": {"type": "string"},
        "dados_oficiais": {
            "type": "array",
            "items": {"type": "string"},
        },
        "evidencias_relevantes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "classificacao": {
                        "type": "string",
                        "enum": [
                            "DADO_BRUTO",
                            "FATO_CONFIRMADO",
                            "HIPOTESE",
                            "PENDENCIA",
                        ],
                    },
                    "fonte": {"type": "string"},
                    "observacao": {"type": "string"},
                },
                "required": ["descricao", "classificacao"],
            },
        },
        "pessoas_e_vinculos": {
            "type": "array",
            "items": {"type": "string"},
        },
        "cronologia": {
            "type": "array",
            "items": {"type": "string"},
        },
        "hipoteses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "base_disponivel": {"type": "string"},
                    "limitacao": {"type": "string"},
                },
                "required": [
                    "descricao",
                    "base_disponivel",
                    "limitacao",
                ],
            },
        },
        "pendencias": {
            "type": "array",
            "items": {"type": "string"},
        },
        "proximos_passos": {
            "type": "array",
            "items": {"type": "string"},
        },
        "alertas_eticos": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "titulo",
        "resumo_executivo",
        "dados_oficiais",
        "evidencias_relevantes",
        "pessoas_e_vinculos",
        "cronologia",
        "hipoteses",
        "pendencias",
        "proximos_passos",
        "alertas_eticos",
    ],
}


def compact_context(context: dict[str, Any]) -> dict[str, Any]:
    """Remove JSON bruto, Base64 e metadados não necessários ao rascunho."""
    case = context.get("caso", {})

    official = {
        "cnpd_id": case.get("cnpd_id"),
        "nome": case.get("nome"),
        "idade_atual": case.get("idade_atual"),
        "idade_desaparecimento": case.get(
            "idade_desaparecimento"
        ),
        "sexo": case.get("sexo"),
        "raca_cor": case.get("raca_cor"),
        "local_registro": case.get("local_registro"),
        "uf_registro": case.get("uf_registro"),
        "data_desaparecimento": case.get(
            "data_desaparecimento"
        ),
        "data_registro_desaparecimento": case.get(
            "data_registro_desaparecimento"
        ),
        "localizacao_confirmada": case.get(
            "localizacao_confirmada"
        ),
        "status_fonte": case.get("status_fonte"),
    }

    evidences = [
        {
            "tipo": item.get("tipo"),
            "titulo": item.get("titulo"),
            "valor": item.get("valor"),
            "descricao": item.get("descricao"),
            "url_fonte": item.get("url_fonte"),
            "data_evento": item.get("data_evento"),
            "classificacao": item.get("classificacao"),
            "nivel_confianca": item.get("nivel_confianca"),
            "status_verificacao": item.get(
                "status_verificacao"
            ),
        }
        for item in context.get("evidencias", [])
    ]

    people = [
        {
            "nome": item.get("nome"),
            "tipo_relacao": item.get("tipo_relacao"),
            "descricao_relacao": item.get(
                "descricao_relacao"
            ),
            "localidade": item.get("localidade"),
            "nivel_confianca": item.get("nivel_confianca"),
            "status_verificacao": item.get(
                "status_verificacao"
            ),
        }
        for item in context.get("pessoas", [])
    ]

    socials = [
        {
            "plataforma": item.get("plataforma"),
            "username": item.get("username"),
            "perfil_id": item.get("perfil_id"),
            "perfil_url": item.get("perfil_url"),
            "nome_exibicao": item.get("nome_exibicao"),
            "observacao": item.get("observacao"),
            "nivel_confianca": item.get("nivel_confianca"),
            "status_verificacao": item.get(
                "status_verificacao"
            ),
        }
        for item in context.get("redes_sociais", [])
    ]

    locations = [
        {
            "titulo": item.get("titulo"),
            "tipo_local": item.get("tipo_local"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "data_evento": item.get("data_evento"),
            "descricao": item.get("descricao"),
            "nivel_confianca": item.get("nivel_confianca"),
            "status_verificacao": item.get(
                "status_verificacao"
            ),
        }
        for item in context.get("pontos", [])
    ]

    notes = [
        {
            "categoria": item.get("categoria"),
            "classificacao": item.get("classificacao"),
            "conteudo": item.get("conteudo"),
            "nivel_confianca": item.get("nivel_confianca"),
        }
        for item in context.get("anotacoes", [])
    ]

    media = [
        {
            "tipo": item.get("tipo"),
            "origem": item.get("origem"),
            "nome_original": item.get("nome_original"),
            "descricao": item.get("descricao"),
        }
        for item in context.get("midias", [])
    ]

    return {
        "dados_oficiais_cnpd": official,
        "evidencias": evidences,
        "pessoas_relacionadas": people,
        "redes_sociais": socials,
        "pontos_geograficos": locations,
        "anotacoes": notes,
        "midias_disponiveis": media,
    }


def build_prompt(compact_data: dict[str, Any]) -> str:
    """
    Prompt curto e explícito. A resposta deve ir para o canal final,
    não para o canal de raciocínio interno do modelo.
    """
    schema_text = json.dumps(
        REPORT_DRAFT_SCHEMA,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    context_text = json.dumps(
        compact_data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"""
Gere o rascunho de relatório abaixo usando exclusivamente os dados fornecidos.

REGRAS:
- Não invente nomes, datas, locais, vínculos, eventos, fontes ou conclusões.
- DADO_BRUTO não é FATO_CONFIRMADO.
- Se não houver informação suficiente, registre pendência ou use lista vazia.
- Hipóteses devem ser explicitamente rotuladas e incluir limitações.
- Não afirme localização, óbito, crime ou vínculo sem confirmação explícita.
- Não escreva raciocínio, explicação, Markdown, texto antes ou depois do JSON.
- RESPONDA IMEDIATAMENTE COM O OBJETO JSON FINAL.
- Não use canal de pensamento; coloque o JSON na resposta final.

JSON Schema obrigatório:
{schema_text}

Dados do caso:
{context_text}
""".strip()


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        OLLAMA_GENERATE_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError(
            "Resposta do Ollama não é um objeto JSON."
        )

    return data


def _extract_json(result: dict[str, Any]) -> dict[str, Any]:
    raw_response = result.get("response")

    if not isinstance(raw_response, str) or not raw_response.strip():
        done_reason = result.get("done_reason")
        thinking = result.get("thinking")

        message = (
            "O Ollama não retornou resposta final utilizável. "
            f"done_reason={done_reason!r}. "
            f"thinking_presente={bool(thinking)}. "
            "O modelo pode ter consumido o limite de tokens no raciocínio interno."
        )

        raise ValueError(message)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Ollama retornou texto final que não é JSON válido. "
            f"Amostra: {raw_response[:800]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "O JSON retornado não é um objeto."
        )

    return parsed


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_duration": result.get("total_duration"),
        "load_duration": result.get("load_duration"),
        "prompt_eval_count": result.get("prompt_eval_count"),
        "eval_count": result.get("eval_count"),
        "done_reason": result.get("done_reason"),
    }


def generate_report_draft(
    context: dict[str, Any],
) -> dict[str, Any]:
    """
    Gera rascunho com duas tentativas:

    1. JSON Schema e orçamento maior de tokens;
    2. JSON mode simples como fallback.

    qwen3.5 pode gastar tokens no campo `thinking`. Por isso o primeiro
    orçamento precisa ser suficientemente maior que o tamanho do rascunho.
    """
    compact_data = compact_context(context)
    prompt = build_prompt(compact_data)

    base_payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
    
        # Desativa o canal interno de raciocínio para evitar que
        # qwen3.5 consuma num_predict inteiro em thinking.
        "think": False,
    
        "options": {
            "temperature": 0.1,
            "num_predict": max(3000, OLLAMA_NUM_PREDICT),
            "seed": 42,
        },
    }

    attempts = [
        (
            "json_mode",
            {
                **base_payload,
                "format": "json",
            },
        ),
        (
            "json_schema_fallback",
            {
                **base_payload,
                "format": REPORT_DRAFT_SCHEMA,
                "options": {
                    "temperature": 0.1,
                    "num_predict": max(
                        6000,
                        OLLAMA_NUM_PREDICT,
                    ),
                    "seed": 42,
                },
            },
        ),
    ]

    failures: list[str] = []

    for mode, payload in attempts:
        try:
            result = _request(payload)
            draft = _extract_json(result)

            return {
                "draft": draft,
                "model": result.get("model", OLLAMA_MODEL),
                "generation_mode": mode,
                "metrics": _metrics(result),
                "input_context": compact_data,
            }
        except Exception as exc:
            failures.append(
                f"{mode}: {type(exc).__name__}: {exc}"
            )

    raise ValueError(
        "Falha ao gerar rascunho no Ollama. "
        + " | ".join(failures)
    )
