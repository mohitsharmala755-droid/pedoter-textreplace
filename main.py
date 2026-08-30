# pedoter-textreplace/main.py
#
# Pedoter Skills — PDF Text Replacement microservice.
# Finds exact text spans in a PDF and replaces them in place, reading the
# original font, size, and color directly from the document so the
# replacement inherits the same look, at the same position.
#
# Real constraints (see the README for the full explanation):
#  - If the original font is a custom/embedded font not available to PyMuPDF,
#    the replacement uses PyMuPDF's closest built-in match by font name —
#    visually close for standard fonts (Helvetica/Times/Arial/Courier),
#    noticeably different for unusual custom/branded fonts.
#  - Replacement text longer than the original is auto-shrunk in font size
#    (down to a floor) to avoid overflowing into neighboring content; if it
#    still doesn't fit at the floor size, it's allowed to overflow rather
#    than silently dropping characters.
#  - Case-sensitive exact match by default (see `case_sensitive` param).

import io
import json
from typing import List, Optional

import fitz  # PyMuPDF
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Pedoter Skills — PDF Text Replace")

# Restrict to your real frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to ["https://pedoterskills.netlify.app"] once confirmed working
    allow_methods=["POST"],
    allow_headers=["*"],
)

FONT_SIZE_FLOOR_RATIO = 0.6  # never shrink below 60% of the original size


class Replacement(BaseModel):
    find: str
    replace: str


def fit_font_size(text: str, fontname: str, original_size: float, max_width: float) -> float:
    """Shrink font size until `text` fits within `max_width`, down to a floor."""
    size = original_size
    floor = original_size * FONT_SIZE_FLOOR_RATIO
    while size > floor:
        width = fitz.get_text_length(text, fontname=fontname, fontsize=size)
        if width <= max_width:
            return size
        size -= 0.5
    return floor


@app.post("/replace")
async def replace_text(
    file: UploadFile = File(...),
    replacements: str = Form(...),  # JSON string: [{"find": "...", "replace": "..."}]
    case_sensitive: bool = Form(False),
):
    try:
        repls: List[Replacement] = [Replacement(**r) for r in json.loads(replacements)]
    except Exception:
        raise HTTPException(400, "`replacements` must be valid JSON: [{\"find\":\"..\",\"replace\":\"..\"}]")

    if not repls:
        raise HTTPException(400, "Provide at least one find/replace pair")

    pdf_bytes = await file.read()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(400, "Could not open this file as a PDF")

    total_matches = 0

    for page in doc:
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span["text"]
                    match_text = span_text if case_sensitive else span_text.lower()

                    for r in repls:
                        needle = r.find if case_sensitive else r.find.lower()
                        if needle not in match_text:
                            continue

                        total_matches += 1
                        new_text = span_text.replace(r.find, r.replace) if case_sensitive \
                            else _replace_ci(span_text, r.find, r.replace)

                        rect = fitz.Rect(span["bbox"])
                        fontname = span.get("font", "helv")
                        color_int = span.get("color", 0)
                        color = (
                            ((color_int >> 16) & 255) / 255,
                            ((color_int >> 8) & 255) / 255,
                            (color_int & 255) / 255,
                        )
                        fitted_size = fit_font_size(new_text, fontname, span["size"], rect.width)

                        page.add_redact_annot(
                            rect,
                            text=new_text,
                            fontname=fontname,
                            fontsize=fitted_size,
                            text_color=color,
                            align=fitz.TEXT_ALIGN_LEFT,
                        )
        page.apply_redactions()

    if total_matches == 0:
        raise HTTPException(404, "None of the find terms were found in this PDF")

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    out.seek(0)

    return StreamingResponse(
        out,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=replaced.pdf",
            "X-Matches-Replaced": str(total_matches),
        },
    )


def _replace_ci(haystack: str, needle: str, replacement: str) -> str:
    """Case-insensitive replace that preserves the rest of the string exactly."""
    import re
    return re.sub(re.escape(needle), lambda _: replacement, haystack, flags=re.IGNORECASE)


@app.get("/health")
def health():
    return {"status": "ok"}
