"""
Core PDF operations for the local iLovePDF-style desktop app.

All functions work fully offline using PyMuPDF (fitz) and Pillow, and mirror
the tool set exposed by the ilovepdf-nodejs client (merge, split, compress,
rotate, watermark, protect/unlock, page extraction, image<->PDF conversion).

Every function raises a plain Exception with a human-readable message on
failure so the UI layer can show it to the user as-is.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass

import pymupdf as fitz  # PyMuPDF
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_page_ranges(spec: str, max_pages: int) -> list[int]:
    """Parse a page spec like '1-3,5,8-10' into a sorted list of 0-based
    page indexes, clamped to [0, max_pages-1]. Empty spec -> all pages."""
    spec = (spec or "").strip()
    if not spec:
        return list(range(max_pages))

    pages: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start_s, end_s = start_s.strip(), end_s.strip()
            try:
                start = int(start_s) if start_s else 1
                end = int(end_s) if end_s else max_pages
            except ValueError:
                raise ValueError(f"Invalid page range: '{chunk}'")
            if start > end:
                start, end = end, start
            for p in range(start, end + 1):
                if 1 <= p <= max_pages:
                    pages.add(p - 1)
        else:
            try:
                p = int(chunk)
            except ValueError:
                raise ValueError(f"Invalid page number: '{chunk}'")
            if 1 <= p <= max_pages:
                pages.add(p - 1)

    if not pages:
        raise ValueError("No valid pages found in the given range.")
    return sorted(pages)


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@dataclass
class PdfInfo:
    page_count: int
    is_encrypted: bool
    title: str


def get_pdf_info(path: str, password: str | None = None) -> PdfInfo:
    doc = fitz.open(path)
    try:
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                raise ValueError("This PDF is password protected. Provide the correct password.")
        return PdfInfo(
            page_count=doc.page_count,
            is_encrypted=doc.is_encrypted,
            title=(doc.metadata or {}).get("title") or os.path.basename(path),
        )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_pdfs(input_paths: list[str], output_path: str) -> None:
    if len(input_paths) < 2:
        raise ValueError("Select at least two PDF files to merge.")
    ensure_parent_dir(output_path)

    merged = fitz.open()
    try:
        for path in input_paths:
            with fitz.open(path) as src:
                if src.needs_pass:
                    raise ValueError(f"'{os.path.basename(path)}' is password protected. Unlock it first.")
                merged.insert_pdf(src)
        merged.save(output_path)
    finally:
        merged.close()


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_pdf(
    input_path: str,
    output_dir: str,
    mode: str = "every_n",
    n: int = 1,
    ranges_spec: str = "",
) -> list[str]:
    """Split a PDF.

    mode='every_n': emit one file every `n` pages.
    mode='ranges': emit one file per comma-separated range in ranges_spec
                   (each range/number becomes its own output file).
    Returns the list of output file paths created.
    """
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(input_path))[0]
    outputs: list[str] = []

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        total = doc.page_count

        if mode == "every_n":
            if n < 1:
                raise ValueError("Pages per file must be at least 1.")
            chunk_index = 1
            for start in range(0, total, n):
                end = min(start + n, total)
                out_path = os.path.join(output_dir, f"{base}_part{chunk_index}.pdf")
                part = fitz.open()
                part.insert_pdf(doc, from_page=start, to_page=end - 1)
                part.save(out_path)
                part.close()
                outputs.append(out_path)
                chunk_index += 1
        elif mode == "ranges":
            groups = [g.strip() for g in ranges_spec.split(",") if g.strip()]
            if not groups:
                raise ValueError("Enter at least one page range, e.g. 1-3,4-6")
            for idx, group in enumerate(groups, start=1):
                pages = parse_page_ranges(group, total)
                out_path = os.path.join(output_dir, f"{base}_part{idx}.pdf")
                part = fitz.open()
                for p in pages:
                    part.insert_pdf(doc, from_page=p, to_page=p)
                part.save(out_path)
                part.close()
                outputs.append(out_path)
        else:
            raise ValueError(f"Unknown split mode: {mode}")

    return outputs


def zip_files(file_paths: list[str], zip_path: str) -> None:
    ensure_parent_dir(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in file_paths:
            zf.write(f, arcname=os.path.basename(f))


# ---------------------------------------------------------------------------
# Rotate / remove / extract pages
# ---------------------------------------------------------------------------

def rotate_pdf(input_path: str, output_path: str, angle: int, pages_spec: str = "") -> None:
    if angle % 90 != 0:
        raise ValueError("Rotation angle must be a multiple of 90.")
    ensure_parent_dir(output_path)
    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        target_pages = parse_page_ranges(pages_spec, doc.page_count)
        for p in target_pages:
            page = doc[p]
            page.set_rotation((page.rotation + angle) % 360)
        doc.save(output_path)


def remove_pages(input_path: str, output_path: str, pages_spec: str) -> None:
    ensure_parent_dir(output_path)
    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        to_remove = set(parse_page_ranges(pages_spec, doc.page_count))
        if not to_remove:
            raise ValueError("Select at least one page to remove.")
        if len(to_remove) >= doc.page_count:
            raise ValueError("Cannot remove every page from the document.")
        doc.delete_pages(sorted(to_remove))
        doc.save(output_path)


def extract_pages(input_path: str, output_path: str, pages_spec: str) -> None:
    ensure_parent_dir(output_path)
    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        keep = parse_page_ranges(pages_spec, doc.page_count)
        out = fitz.open()
        for p in keep:
            out.insert_pdf(doc, from_page=p, to_page=p)
        out.save(output_path)
        out.close()


# ---------------------------------------------------------------------------
# Compress
# ---------------------------------------------------------------------------

# quality presets: (jpeg_quality, max_dimension_px)
COMPRESSION_PRESETS = {
    "low": (85, 2000),      # light compression, high quality
    "recommended": (60, 1600),
    "extreme": (35, 1200),
}


def compress_pdf(input_path: str, output_path: str, level: str = "recommended") -> tuple[int, int]:
    """Recompress embedded images and re-save the PDF.
    Returns (original_size_bytes, new_size_bytes)."""
    if level not in COMPRESSION_PRESETS:
        raise ValueError(f"Unknown compression level: {level}")
    quality, max_dim = COMPRESSION_PRESETS[level]
    ensure_parent_dir(output_path)

    original_size = os.path.getsize(input_path)

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")

        seen_xrefs: set[int] = set()
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image["image"]
                    from io import BytesIO

                    pil_img = Image.open(BytesIO(img_bytes))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")

                    w, h = pil_img.size
                    scale = min(1.0, max_dim / max(w, h)) if max(w, h) > max_dim else 1.0
                    if scale < 1.0:
                        pil_img = pil_img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

                    buf = BytesIO()
                    pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                    doc.update_stream(xref, buf.getvalue())
                except Exception:
                    # Skip images that can't be re-encoded (e.g. CMYK/mask images)
                    continue

        doc.save(output_path, garbage=4, deflate=True, clean=True)

    new_size = os.path.getsize(output_path)
    return original_size, new_size


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------

def add_watermark(
    input_path: str,
    output_path: str,
    text: str,
    opacity: float = 0.3,
    rotation: int = 45,
    font_size: int = 40,
    color: tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> None:
    if not text.strip():
        raise ValueError("Enter watermark text.")
    ensure_parent_dir(output_path)

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        for page in doc:
            rect = page.rect
            center = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
            text_width = fitz.get_text_length(text, fontname="helv", fontsize=font_size)
            start = fitz.Point(center.x - text_width / 2, center.y)
            matrix = fitz.Matrix(rotation)
            page.insert_text(
                start,
                text,
                fontsize=font_size,
                color=color,
                fontname="helv",
                render_mode=0,
                overlay=True,
                fill_opacity=opacity,
                morph=(center, matrix),
            )
        doc.save(output_path)


# ---------------------------------------------------------------------------
# PDF <-> Images
# ---------------------------------------------------------------------------

def pdf_to_images(input_path: str, output_dir: str, fmt: str = "png", dpi: int = 150) -> list[str]:
    fmt = fmt.lower()
    if fmt not in ("png", "jpg", "jpeg"):
        raise ValueError("Format must be png or jpg.")
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(input_path))[0]
    outputs: list[str] = []

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Unlock it first.")
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix)
            ext = "jpg" if fmt in ("jpg", "jpeg") else "png"
            out_path = os.path.join(output_dir, f"{base}_page{i}.{ext}")
            if ext == "jpg":
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                img.save(out_path, format="JPEG", quality=90)
            else:
                pix.save(out_path)
            outputs.append(out_path)

    return outputs


def images_to_pdf(image_paths: list[str], output_path: str) -> None:
    if not image_paths:
        raise ValueError("Select at least one image.")
    ensure_parent_dir(output_path)

    doc = fitz.open()
    try:
        for img_path in image_paths:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            from io import BytesIO

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=92)
            img_bytes = buf.getvalue()

            width_pt, height_pt = img.width * 72.0 / 96.0, img.height * 72.0 / 96.0
            page = doc.new_page(width=width_pt, height=height_pt)
            page.insert_image(page.rect, stream=img_bytes)
        doc.save(output_path)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Protect / Unlock
# ---------------------------------------------------------------------------

def protect_pdf(input_path: str, output_path: str, user_password: str, owner_password: str | None = None) -> None:
    if not user_password:
        raise ValueError("Enter a password to protect the PDF with.")
    ensure_parent_dir(output_path)

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("This PDF is already password protected. Unlock it first.")
        perm = int(
            fitz.PDF_PERM_PRINT
            | fitz.PDF_PERM_COPY
            | fitz.PDF_PERM_ANNOTATE
            | fitz.PDF_PERM_ACCESSIBILITY
        )
        doc.save(
            output_path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw=owner_password or user_password,
            user_pw=user_password,
            permissions=perm,
        )


def unlock_pdf(input_path: str, output_path: str, password: str) -> None:
    ensure_parent_dir(output_path)
    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                raise ValueError("Incorrect password.")
        doc.save(output_path, encryption=fitz.PDF_ENCRYPT_NONE)


# ---------------------------------------------------------------------------
# PDF -> Text
# ---------------------------------------------------------------------------

def pdf_to_text(input_path: str, output_path: str, password: str | None = None) -> None:
    ensure_parent_dir(output_path)
    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                raise ValueError("This PDF is password protected. Provide the correct password.")
        text_parts = [page.get_text() for page in doc]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\f\n".join(text_parts))


def format_bytes(n: int) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if n < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= step
    return f"{n:.1f} TB"
