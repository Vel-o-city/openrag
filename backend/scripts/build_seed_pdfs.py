"""Renders scripts/seed_documents/sources/*.md into committed PDFs.

Run only when the seed text changes:
    uv run --with reportlab python scripts/build_seed_pdfs.py

reportlab is deliberately not a project dependency — the generated PDFs are
committed, so seeding a fresh environment needs no rendering toolchain. The
markdown handled here is only what the seed sources actually use: '#' headings,
'**bold**' lines, tables, and paragraphs.
"""

import re
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

SEED_DIR = Path(__file__).parent / "seed_documents"
SOURCE_DIR = SEED_DIR / "sources"

_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=17, leading=21, spaceAfter=10
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12.5, leading=16, spaceBefore=12, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10.5,
            leading=15.5,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
    }


def _to_flowables(markdown: str, styles: dict[str, ParagraphStyle]) -> list:
    flowables: list = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            text = _INLINE_BOLD.sub(r"<b>\1</b>", " ".join(paragraph))
            flowables.append(Paragraph(text, styles["body"]))
            paragraph.clear()

    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
        elif stripped.startswith("## "):
            flush()
            flowables.append(Paragraph(stripped[3:], styles["h2"]))
        elif stripped.startswith("# "):
            flush()
            flowables.append(Paragraph(stripped[2:], styles["h1"]))
        else:
            paragraph.append(stripped)

    flush()
    return flowables


def build(source: Path) -> Path:
    styles = _styles()
    target = SEED_DIR / f"{source.stem}.pdf"

    SimpleDocTemplate(
        str(target),
        pagesize=A4,
        title=source.stem,
        author="OpenRAG seed data (fictional)",
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    ).build([Spacer(1, 2 * mm), *_to_flowables(source.read_text(), styles)])

    return target


def main() -> None:
    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        raise SystemExit(f"No seed sources found in {SOURCE_DIR}")

    for source in sources:
        target = build(source)
        print(f"{source.name} -> {target.name} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
