from io import BytesIO
import json
import tempfile
import re
import html

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ======================================================
# FONT
# ======================================================

try:
    pdfmetrics.registerFont(
        TTFont(
            "DejaVuSans",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
    )
    FONT_NAME = "DejaVuSans"
except Exception:
    FONT_NAME = "Helvetica"


# ======================================================
# STYLES
# ======================================================

styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "Title",
    parent=styles["Title"],
    fontName=FONT_NAME,
    fontSize=20,
    leading=24,
)

ROLE_STYLE = ParagraphStyle(
    "Role",
    parent=styles["BodyText"],
    fontName=FONT_NAME,
    fontSize=9,
    textColor=colors.HexColor("#666666"),
)

BODY_STYLE = ParagraphStyle(
    "Body",
    parent=styles["BodyText"],
    fontName=FONT_NAME,
    fontSize=10,
    leading=16,
)

CODE_STYLE = ParagraphStyle(
    "Code",
    parent=BODY_STYLE,
    fontName="Courier",
    backColor=colors.HexColor("#F4F4F4"),
)


# ======================================================
# CLEAN CONTENT
# ======================================================

def clean_content(content):

    if not content:
        return ""

    content = str(content)

    content = html.escape(content)

    content = re.sub(
        r'\*\*(.*?)\*\*',
        r'<b>\1</b>',
        content,
        flags=re.DOTALL
    )

    content = re.sub(
        r'\*(.*?)\*',
        r'<i>\1</i>',
        content,
        flags=re.DOTALL
    )

    content = content.replace("\n", "<br/>")

    return content


# ======================================================
# CHAT BUBBLE
# ======================================================

def create_chat_bubble(role, content):

    role = role.lower()

    if role == "user":
        bg = colors.HexColor("#DCF8C6")
    else:
        bg = colors.HexColor("#F7F7F8")

    paragraph = Paragraph(
        clean_content(content),
        BODY_STYLE
    )

    bubble = Table(
        [[paragraph]],
        colWidths=[470]
    )

    bubble.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),

            ("BOX",
             (0, 0),
             (-1, -1),
             0.7,
             colors.HexColor("#CCCCCC")),

            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),

            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )

    return bubble


# ======================================================
# HEADER
# ======================================================

def draw_page(canvas, doc):

    canvas.saveState()

    canvas.setFont(FONT_NAME, 9)

    canvas.setFillColor(colors.grey)

    canvas.drawString(
        40,
        20,
        f"Page {canvas.getPageNumber()}"
    )

    canvas.restoreState()


# ======================================================
# BUILD CHAT
# ======================================================

def build_elements(messages, title=None):

    elements = []

    if title:

        elements.append(
            Paragraph(title, TITLE_STYLE)
        )

        elements.append(
            Spacer(1, 20)
        )

    for msg in messages:

        role = msg.get(
            "role",
            "assistant"
        )

        content = msg.get(
            "content",
            ""
        )

        if not isinstance(content, str):

            try:
                content = json.dumps(
                    content,
                    ensure_ascii=False,
                    indent=2
                )

            except Exception:
                content = str(content)

        elements.append(
            Paragraph(
                role.capitalize(),
                ROLE_STYLE
            )
        )

        elements.append(
            Spacer(1, 4)
        )

        elements.append(
            create_chat_bubble(
                role,
                content
            )
        )

        elements.append(
            Spacer(1, 12)
        )

    return elements


# ======================================================
# PDF BYTES
# ======================================================

def messages_to_pdf_bytes(
    messages,
    title="ChatGPT Conversation"
):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=35
    )

    elements = build_elements(
        messages,
        title
    )

    doc.build(
        elements,
        onFirstPage=draw_page,
        onLaterPages=draw_page
    )

    pdf = buffer.getvalue()

    buffer.close()

    return pdf


# ======================================================
# PDF FILE
# ======================================================

def messages_to_pdf_file(
    messages,
    title="ChatGPT Conversation"
):

    temp = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    )

    temp.close()

    doc = SimpleDocTemplate(
        temp.name,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=35
    )

    elements = build_elements(
        messages,
        title
    )

    doc.build(
        elements,
        onFirstPage=draw_page,
        onLaterPages=draw_page
    )

    return temp.name


# ======================================================
# EXAMPLE
# ======================================================

if __name__ == "__main__":

    messages = [
        {
            "role": "user",
            "content": "Give latest top 2 news of India."
        },
        {
            "role": "assistant",
            "content": """
**Top News**

1. Market rises sharply.

2. New infrastructure projects announced.

*More details available.*
"""
        }
    ]

    file_path = messages_to_pdf_file(
        messages,
        "Chat Export"
    )

    print(file_path)