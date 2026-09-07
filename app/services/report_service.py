from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape

from app.config import DATA_DIR
from app.database import get_connection
from app.services.investigation_service import build_case_context

REPORTS_DIR = DATA_DIR / "reports"


def create_report(cnpd_id: int, model: str = "manual") -> dict[str, Any]:
    context = build_case_context(cnpd_id)
    case = context["caso"]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pdf_path = REPORTS_DIR / f"caso_{cnpd_id}_{timestamp}.pdf"

    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(escape(f"Relatório do caso CNPD #{cnpd_id}"), styles["Title"]))
    story.append(Spacer(1, .4 * cm))
    story.append(Paragraph(escape(f"Nome: {case['nome']}"), styles["Normal"]))
    story.append(Paragraph(escape(f"Data do desaparecimento: {case['data_desaparecimento'] or '-'}"), styles["Normal"]))
    story.append(Paragraph(escape(f"Local: {case['local_registro'] or '-'}"), styles["Normal"]))
    story.append(Paragraph(escape(f"Sexo: {case['sexo'] or '-'}"), styles["Normal"]))
    story.append(Spacer(1, .3 * cm))
    story.append(Paragraph("Dados e evidências cadastrados", styles["Heading2"]))

    for item in context["evidencias"]:
        text = f"[{item['classificacao']}] {item['tipo']}: {item['valor']}"
        if item["descricao"]:
            text += f" — {item['descricao']}"
        story.append(Paragraph(escape(text), styles["BodyText"]))

    story.append(Paragraph("Pessoas relacionadas", styles["Heading2"]))
    for item in context["pessoas"]:
        story.append(Paragraph(escape(f"{item['nome']} — {item['tipo_relacao'] or '-'}"), styles["BodyText"]))

    story.append(Paragraph("Anotações", styles["Heading2"]))
    for item in context["anotacoes"]:
        story.append(Paragraph(escape(f"[{item['categoria']}] {item['conteudo']}"), styles["BodyText"]))

    story.append(Paragraph("Pontos geográficos", styles["Heading2"]))
    for item in context["pontos"]:
        story.append(Paragraph(escape(f"{item['titulo']} — {item['latitude']}, {item['longitude']} ({item['tipo_local']})"), styles["BodyText"]))

    story.append(Spacer(1, .5 * cm))
    story.append(Paragraph(escape("Este documento é um rascunho operacional e exige revisão humana."), styles["Italic"]))
    SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=1.8 * cm, leftMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm).build(story)

    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO relatorios (cnpd_id, titulo, conteudo, caminho_relativo, sha256, modelo_ia, status, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, 'GERADO', ?)
            """,
            (
                cnpd_id,
                f"Relatório CNPD #{cnpd_id}",
                json.dumps(context, ensure_ascii=False, default=str),
                str(pdf_path.relative_to(Path.cwd())),
                digest,
                model,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        report_id = cursor.lastrowid

    return {"id": report_id, "path": pdf_path, "sha256": digest}
