import io

import pypdfium2 as pdfium

RENDER_SCALE = 2.0  # ~144 DPI — legible for vision OCR without an oversized payload


def render_pdf_page_to_png(content: bytes, page_index: int) -> bytes:
    pdf = pdfium.PdfDocument(content)
    try:
        page = pdf[page_index]
        bitmap = page.render(scale=RENDER_SCALE)
        image = bitmap.to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()
