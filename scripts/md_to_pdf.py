"""Render docs/walkthrough.md to docs/walkthrough.pdf. Plain document styling.

    python scripts/md_to_pdf.py docs/walkthrough.md docs/walkthrough.pdf
"""
import re
import sys
from pathlib import Path

from PIL import Image as PI
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
base = src.parent
INK = colors.HexColor("#222222"); GREY = colors.HexColor("#666666"); CODE_BG = colors.HexColor("#f4f4f4")

TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=INK, spaceAfter=10)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=16, spaceAfter=5, keepWithNext=True)
BODY = ParagraphStyle("b", fontName="Times-Roman", fontSize=10.5, leading=14.5, textColor=INK, spaceAfter=7)
BUL = ParagraphStyle("bl", parent=BODY, leftIndent=16, bulletIndent=5, spaceAfter=3)
CAP = ParagraphStyle("c", parent=BODY, fontName="Times-Italic", fontSize=9, leading=12, textColor=GREY, spaceBefore=2, spaceAfter=10)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=7.8, leading=9.8, textColor=INK, backColor=CODE_BG, borderPadding=(5, 6, 5, 6), leftIndent=3, rightIndent=3, spaceBefore=3, spaceAfter=9)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=11.5, spaceAfter=0)


def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r"<font face='Courier' size='9'>\1</font>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", t)
    return t


story, lines, i = [], src.read_text().splitlines(), 0
para = []


def flush():
    global para
    if para:
        story.append(Paragraph(inline(" ".join(para)), BODY)); para = []


while i < len(lines):
    l = lines[i]
    if l.startswith("```"):
        flush(); j = i + 1; buf = []
        while j < len(lines) and not lines[j].startswith("```"): buf.append(lines[j]); j += 1
        story.append(Preformatted("\n".join(buf), CODE)); i = j + 1; continue
    if l.startswith("# "):
        flush(); story.append(Paragraph(inline(l[2:]), TITLE)); i += 1; continue
    if l.startswith("## "):
        flush(); story.append(Paragraph(inline(l[3:]), H2)); i += 1; continue
    m = re.match(r"!\[.*?\]\((.+?)\)", l)
    if m:
        flush(); p = base / m.group(1); w, h = PI.open(p).size
        width = 6.2 * inch if h / w < 0.5 else 4.4 * inch
        story.append(Image(str(p), width=width, height=width * h / w)); i += 1
        # italic caption line directly after, if present
        while i < len(lines) and not lines[i].strip(): i += 1
        if i < len(lines) and lines[i].startswith("*") and lines[i].endswith("*"):
            story.append(Paragraph(inline(lines[i][1:-1]), CAP)); i += 1
        continue
    if l.startswith("|"):
        flush(); rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|[-| ]+\|$", lines[i]):
                rows.append([Paragraph(inline(c.strip()), CELL) for c in lines[i].strip("|").split("|")])
            i += 1
        ncol = len(rows[0]); widths = [1.3 * inch] + [(6.7 * inch - 1.3 * inch) / (ncol - 1)] * (ncol - 1)
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.append(t); story.append(Spacer(1, 8)); continue
    if l.startswith("- "):
        flush(); story.append(Paragraph(inline(l[2:]), BUL, bulletText="•")); i += 1; continue
    if not l.strip():
        flush(); i += 1; continue
    para.append(l.strip()); i += 1
flush()


def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(GREY)
    canvas.drawRightString(letter[0] - inch, 0.6 * inch, str(doc.page)); canvas.restoreState()


SimpleDocTemplate(str(dst), pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                  title="Operator Layer: notes on how I built it", author="Mohamed Harhash").build(story, onFirstPage=footer, onLaterPages=footer)
print(dst)
