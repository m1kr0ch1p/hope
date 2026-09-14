"""
Serviço de geração de relatórios em PDF.

Este módulo fornece funções para:
- Construção de relatórios operacionais em PDF
- Inclusão de imagens e mapas
- Formatação estilizada com ReportLab

Uso:
    from app.services.report_service import create_report
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.config import BASE_DIR, REPORTS_DIR
from app.database import get_connection
from app.services.investigation_service import build_case_context

# Constantes de formatação
MAX_REPORT_IMAGES = 6
REPORT_IMAGE_MAX_WIDTH = 15.5 * cm
REPORT_IMAGE_MAX_HEIGHT = 11.0 * cm
MAP_WIDTH = 15.5 * cm
MAP_HEIGHT = 9.0 * cm


def utc_now() -> str:
    """
    Retorna timestamp UTC atual em formato ISO 8601.

    Returns:
        str: Timestamp ISO formatado.
    """
    return datetime.now(timezone.utc).isoformat()


def safe_text(value: Any) -> str:
    """
    Converte valores em texto seguro para ReportLab/Paragraph.

    Escapa caracteres XML/HTML e converte quebras de linha para <br/>.

    Args:
        value: Valor a ser convertido.

    Returns:
        str: Texto seguro para renderização.
    """
    if value is None:
        return "-"

    return escape(str(value)).replace("\n", "<br/>")


def resolve_media_path(relative_or_absolute_path: str | None) -> Path | None:
    """
    Resolve um caminho de mídia persistido no banco.

    Os caminhos podem ser relativos à raiz do projeto ou absolutos,
    dependendo da versão que inseriu o registro.

    Args:
        relative_or_absolute_path: Caminho armazenado no banco.

    Returns:
        Path | None: Caminho resolvido ou None se não existir.
    """
    if not relative_or_absolute_path:
        return None

    path = Path(relative_or_absolute_path)

    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists() or not path.is_file():
        return None

    return path


def fit_image(
    image_path: Path,
    max_width: float,
    max_height: float,
) -> Image:
    """
    Carrega uma imagem para Platypus preservando a proporção.

    Redimensiona a imagem para caber dentro das dimensões máximas
    sem estourar as proporções originais.

    Args:
        image_path: Caminho para o arquivo de imagem.
        max_width: Largura máxima em pontos.
        max_height: Altura máxima em pontos.

    Returns:
        Image: Objeto Image do ReportLab configurado.
    """
    image = Image(str(image_path))

    original_width = float(image.imageWidth)
    original_height = float(image.imageHeight)

    if original_width <= 0 or original_height <= 0:
        image.drawWidth = max_width
        image.drawHeight = max_height
        return image

    scale = min(
        max_width / original_width,
        max_height / original_height,
        1.0,
    )

    image.drawWidth = original_width * scale
    image.drawHeight = original_height * scale

    return image


def visible_media(context: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Seleciona mídias de imagem que ainda existem no disco.

    Prioriza a imagem principal CNPD e depois imagens adicionadas pelo
    investigador. Evita incluir arquivos corrompidos, ausentes ou não-imagem.

    Args:
        context: Contexto completo do caso.

    Returns:
        list: Lista de mídias com caminho resolvido (_resolved_path).
    """
    media = context.get("midias", [])

    def priority(item: dict[str, Any]) -> tuple[int, int]:
        """Prioriza imagem principal CNPD."""
        is_official = (
            item.get("tipo") == "IMAGEM_PRINCIPAL"
            and item.get("origem") == "CNPD"
        )

        return (0 if is_official else 1, int(item.get("id", 0)))

    selected: list[dict[str, Any]] = []

    for item in sorted(media, key=priority):
        mime_type = (item.get("mime_type") or "").lower()

        if not mime_type.startswith("image/"):
            continue

        path = resolve_media_path(item.get("caminho_relativo"))

        if path is None:
            continue

        selected.append({
            **item,
            "_resolved_path": path,
        })

        if len(selected) >= MAX_REPORT_IMAGES:
            break

    return selected


def generate_static_map(
    points: list[dict[str, Any]],
    output_path: Path,
) -> Path | None:
    """
    Gera PNG estático baseado em OpenStreetMap a partir dos pontos do caso.

    A imagem recebe atribuição visível ao OpenStreetMap, necessária em
    documentos que incluem mapa estático derivado de dados/tiles OSM.

    Args:
        points: Lista de pontos geográficos com latitude/longitude.
        output_path: Caminho para salvar o PNG gerado.

    Returns:
        Path | None: Caminho do arquivo gerado ou None se falhar.
    """
    if not points:
        return None

    try:
        from staticmap import CircleMarker, StaticMap
        from PIL import Image as PILImage
        from PIL import ImageDraw, ImageFont
    except ImportError:
        return None

    valid_points: list[dict[str, Any]] = []

    for point in points:
        try:
            lat = float(point["latitude"])
            lon = float(point["longitude"])
        except (KeyError, TypeError, ValueError):
            continue

        valid_points.append({
            **point,
            "_lat": lat,
            "_lon": lon,
        })

    if not valid_points:
        return None

    static_map = StaticMap(
        1200,
        700,
        url_template=(
            "https://tile.openstreetmap.org/"
            "{z}/{x}/{y}.png"
        ),
    )

    # Cores por tipo de local
    colors_by_type = {
        "ULTIMO_LOCAL_CONHECIDO": "#2d8cff",
        "LOCAL_DESAPARECIMENTO": "#f44336",
        "AVISTAMENTO": "#ffca28",
        "RESIDENCIA": "#66bb6a",
        "OUTRO": "#ab47bc",
    }

    for point in valid_points:
        marker_color = colors_by_type.get(
            point.get("tipo_local"),
            "#ab47bc",
        )

        static_map.add_marker(
            CircleMarker(
                (point["_lon"], point["_lat"]),
                marker_color,
                14,
            )
        )

    image = static_map.render()

    if image.mode != "RGB":
        image = image.convert("RGB")

    # Adiciona barra rodapé com atribuição OSM
    canvas = PILImage.new(
        "RGB",
        (image.width, image.height + 46),
        "white",
    )

    canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    attribution = (
        "Mapa: \u00a9 OpenStreetMap contributors "
        "-- https://www.openstreetmap.org/copyright"
    )

    try:
        font = ImageFont.truetype(
            "arial.ttf",
            18,
        )
    except OSError:
        font = ImageFont.load_default()

    draw.text(
        (14, image.height + 14),
        attribution,
        fill="#202020",
        font=font,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    canvas.save(output_path, format="PNG")

    return output_path


def build_media_section(
    story: list[Any],
    context: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    """
    Inclui imagens locais no PDF, quando disponíveis.

    Adiciona imagens até o limite MAX_REPORT_IMAGES, com legendas
    contendo nome, origem e hash SHA-256.

    Args:
        story: Lista para adicionar elementos ao relatório.
        context: Contexto do caso com mídias.
        styles: Dicionário de estilos ReportLab.
    """
    media_items = visible_media(context)

    if not media_items:
        story.append(
            Paragraph(
                "Nenhuma imagem local disponível para inclusão.",
                styles["SmallMuted"],
            )
        )
        return

    for index, media in enumerate(media_items, start=1):
        image_path = media["_resolved_path"]

        try:
            image = fit_image(
                image_path,
                REPORT_IMAGE_MAX_WIDTH,
                REPORT_IMAGE_MAX_HEIGHT,
            )
        except Exception:
            story.append(
                Paragraph(
                    (
                        "Não foi possível renderizar a imagem: "
                        f"{safe_text(media.get('nome_original'))}"
                    ),
                    styles["SmallMuted"],
                )
            )
            continue

        caption = (
            f"<b>Imagem {index}</b> — "
            f"{safe_text(media.get('nome_original'))}<br/>"
            f"Origem: {safe_text(media.get('origem'))}<br/>"
            f"SHA-256: {safe_text(media.get('sha256'))}"
        )

        if media.get("descricao"):
            caption += (
                "<br/>Descrição: "
                f"{safe_text(media.get('descricao'))}"
            )

        story.append(
            KeepTogether([
                image,
                Spacer(1, 0.15 * cm),
                Paragraph(caption, styles["SmallMuted"]),
                Spacer(1, 0.55 * cm),
            ])
        )


def build_map_section(
    story: list[Any],
    context: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    map_path: Path,
) -> None:
    """
    Gera e adiciona um mapa estático ao PDF.

    Se o mapa não puder ser gerado, lista os pontos em texto.

    Args:
        story: Lista para adicionar elementos ao relatório.
        context: Contexto do caso com pontos geográficos.
        styles: Dicionário de estilos ReportLab.
        map_path: Caminho para salvar o mapa gerado.
    """
    points = context.get("pontos", [])

    if not points:
        story.append(
            Paragraph(
                "Nenhum ponto geográfico registrado.",
                styles["SmallMuted"],
            )
        )
        return

    generated_map = generate_static_map(points, map_path)

    if generated_map is None:
        story.append(
            Paragraph(
                (
                    "O mapa estático não foi gerado. "
                    "Instale Pillow e staticmap para habilitar este recurso."
                ),
                styles["SmallMuted"],
            )
        )

        for point in points:
            story.append(
                Paragraph(
                    (
                        f"{safe_text(point.get('titulo'))}: "
                        f"{safe_text(point.get('latitude'))}, "
                        f"{safe_text(point.get('longitude'))} "
                        f"({safe_text(point.get('tipo_local'))})"
                    ),
                    styles["BodyText"],
                )
            )

        return

    image = fit_image(
        generated_map,
        MAP_WIDTH,
        MAP_HEIGHT,
    )

    story.append(image)
    story.append(Spacer(1, 0.2 * cm))

    story.append(
        Paragraph(
            (
                "Mapa estático com os pontos geográficos cadastrados. "
                "Mapa: \u00a9 OpenStreetMap contributors."
            ),
            styles["SmallMuted"],
        )
    )

    story.append(Spacer(1, 0.45 * cm))

    for point in points:
        point_text = (
            f"<b>{safe_text(point.get('titulo'))}</b> — "
            f"{safe_text(point.get('latitude'))}, "
            f"{safe_text(point.get('longitude'))}; "
            f"tipo: {safe_text(point.get('tipo_local'))}"
        )

        if point.get("descricao"):
            point_text += (
                "<br/>"
                f"{safe_text(point.get('descricao'))}"
            )

        story.append(
            Paragraph(
                point_text,
                styles["BodyText"],
            )
        )


def create_report(cnpd_id: int) -> dict[str, Any]:
    """
    Cria um relatório operacional PDF para um caso.

    O relatório inclui todos os dados estruturados do caso, imagens
    disponíveis e um mapa com os pontos geográficos.

    Args:
        cnpd_id: Identificador único do caso.

    Returns:
        dict: Informações sobre o relatório gerado:
            - id: ID no banco
            - path: Caminho do arquivo PDF
            - map_path: Caminho do mapa (ou None)
            - sha256: Hash do arquivo PDF
    """
    context = build_case_context(cnpd_id)
    case = context["caso"]

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc,
    ).strftime("%Y%m%d_%H%M%S")

    pdf_path = REPORTS_DIR / (
        f"caso_{cnpd_id}_{timestamp}.pdf"
    )

    map_path = REPORTS_DIR / (
        f"caso_{cnpd_id}_{timestamp}_mapa.png"
    )

    styles = getSampleStyleSheet()

    # Estilo para texto em tamanho pequeno e cor cinza
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#535c68"),
        )
    )

    # Estilo para texto de caso
    styles.add(
        ParagraphStyle(
            name="CaseText",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14,
            spaceAfter=4,
        )
    )

    story: list[Any] = []

    # Cabeçalho do relatório
    story.append(
        Paragraph(
            safe_text(
                f"Relatório operacional — Caso CNPD #{cnpd_id}"
            ),
            styles["Title"],
        )
    )

    story.append(
        Spacer(1, 0.25 * cm)
    )

    story.append(
        Paragraph(
            safe_text(
                f"Nome: {case.get('nome')}"
            ),
            styles["CaseText"],
        )
    )

    story.append(
        Paragraph(
            safe_text(
                "Data do desaparecimento: "
                f"{case.get('data_desaparecimento') or '-'}"
            ),
            styles["CaseText"],
        )
    )

    story.append(
        Paragraph(
            safe_text(
                "Local de registro: "
                f"{case.get('local_registro') or '-'}"
            ),
            styles["CaseText"],
        )
    )

    story.append(
        Paragraph(
            safe_text(
                f"UF: {case.get('uf_registro') or '-'}"
            ),
            styles["CaseText"],
        )
    )

    story.append(
        Paragraph(
            safe_text(
                f"Status na fonte: {case.get('status_fonte')}"
            ),
            styles["CaseText"],
        )
    )

    story.append(
        Spacer(1, 0.3 * cm)
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=0.6,
            color=colors.HexColor("#8792a2"),
        )
    )

    story.append(
        Spacer(1, 0.35 * cm)
    )

    # Seção de Imagens
    story.append(
        Paragraph(
            "Imagens associadas ao caso",
            styles["Heading2"],
        )
    )

    build_media_section(
        story,
        context,
        styles,
    )

    # Seção de Evidências
    story.append(
        Paragraph(
            "Evidências e pesquisas abertas",
            styles["Heading2"],
        )
    )

    evidence_items = context.get("evidencias", [])

    if evidence_items:
        for item in evidence_items:
            text = (
                f"[{safe_text(item.get('classificacao'))}] "
                f"{safe_text(item.get('tipo'))}: "
                f"{safe_text(item.get('valor'))}"
            )

            if item.get("descricao"):
                text += (
                    "<br/>"
                    f"{safe_text(item.get('descricao'))}"
                )

            if item.get("url_fonte"):
                text += (
                    "<br/>Fonte: "
                    f"{safe_text(item.get('url_fonte'))}"
                )

            story.append(
                Paragraph(
                    text,
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Nenhuma evidência cadastrada.",
                styles["SmallMuted"],
            )
        )

    story.append(
        Spacer(1, 0.25 * cm)
    )

    # Seção de Pessoas
    story.append(
        Paragraph(
            "Pessoas relacionadas",
            styles["Heading2"],
        )
    )

    people_items = context.get("pessoas", [])

    if people_items:
        for item in people_items:
            text = (
                f"<b>{safe_text(item.get('nome'))}</b> — "
                f"{safe_text(item.get('tipo_relacao'))}"
            )

            if item.get("telefone"):
                text += (
                    "<br/>Telefone: "
                    f"{safe_text(item.get('telefone'))}"
                )

            if item.get("email"):
                text += (
                    "<br/>E-mail: "
                    f"{safe_text(item.get('email'))}"
                )

            story.append(
                Paragraph(
                    text,
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Nenhuma pessoa relacionada cadastrada.",
                styles["SmallMuted"],
            )
        )

    story.append(
        Spacer(1, 0.25 * cm)
    )

    # Seção de Redes Sociais
    story.append(
        Paragraph(
            "Contas e perfis sociais",
            styles["Heading2"],
        )
    )

    social_items = context.get("redes_sociais", [])

    if social_items:
        for item in social_items:
            text = (
                f"<b>{safe_text(item.get('plataforma'))}</b>: "
                f"{safe_text(item.get('username') or item.get('perfil_url'))}"
            )

            if item.get("perfil_id"):
                text += (
                    "<br/>ID: "
                    f"{safe_text(item.get('perfil_id'))}"
                )

            if item.get("observacao"):
                text += (
                    "<br/>"
                    f"{safe_text(item.get('observacao'))}"
                )

            story.append(
                Paragraph(
                    text,
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Nenhuma conta social cadastrada.",
                styles["SmallMuted"],
            )
        )

    story.append(
        Spacer(1, 0.25 * cm)
    )

    # Seção de Mapa
    story.append(
        Paragraph(
            "Mapa e pontos geográficos",
            styles["Heading2"],
        )
    )

    build_map_section(
        story,
        context,
        styles,
        map_path,
    )

    # Seção de Anotações
    story.append(
        Paragraph(
            "Anotações analíticas",
            styles["Heading2"],
        )
    )

    note_items = context.get("anotacoes", [])

    if note_items:
        for item in note_items:
            text = (
                f"[{safe_text(item.get('categoria'))}] "
                f"{safe_text(item.get('conteudo'))}"
            )

            story.append(
                Paragraph(
                    text,
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Nenhuma anotação cadastrada.",
                styles["SmallMuted"],
            )
        )

    story.append(
        Spacer(1, 0.55 * cm)
    )

    # Rodapé com aviso ético
    story.append(
        Paragraph(
            (
                "Este documento é um relatório operacional. "
                "Dados brutos, fatos confirmados, hipóteses e pendências "
                "devem ser revisados por pessoa autorizada antes de "
                "qualquer uso ou compartilhamento."
            ),
            styles["SmallMuted"],
        )
    )

    # Gera o PDF
    SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title=f"Relatório CNPD #{cnpd_id}",
        author="HOPE — CNPD-OSINT",
    ).build(story)

    # Calcula hash e salva registro no banco
    pdf_hash = hashlib.sha256(
        pdf_path.read_bytes()
    ).hexdigest()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO relatorios (
                cnpd_id, titulo, conteudo, caminho_relativo, sha256, modelo_ia, status, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, 'GERADO', ?)
            """,
            (
                cnpd_id,
                f"Relatório CNPD #{cnpd_id}",
                json.dumps(
                    context,
                    ensure_ascii=False,
                    default=str,
                ),
                str(pdf_path.relative_to(BASE_DIR)),
                pdf_hash,
                "SEM_IA",
                utc_now(),
            ),
        )

        report_id = cursor.lastrowid

    return {
        "id": report_id,
        "path": pdf_path,
        "map_path": map_path if map_path.exists() else None,
        "sha256": pdf_hash,
    }