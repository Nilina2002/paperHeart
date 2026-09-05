"""Smoke tests for core.py PDF operations.

These exercise the real PyMuPDF/Pillow code paths (no mocking) against small
PDFs/images generated on the fly, so a broken dependency or packaging change
is caught before a release is built.
"""

from __future__ import annotations

import os

import pymupdf as fitz
import pytest
from PIL import Image

import core


def make_pdf(path: str, pages: int = 2, text: str = "hello") -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{text} {i + 1}")
    doc.save(path)
    doc.close()


def make_image(path: str, size: tuple[int, int] = (64, 64), color=(255, 0, 0)) -> None:
    Image.new("RGB", size, color).save(path)


def test_merge_pdfs(tmp_path):
    a, b = str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf")
    make_pdf(a, pages=1)
    make_pdf(b, pages=2)
    out = str(tmp_path / "merged.pdf")

    core.merge_pdfs([a, b], out)

    with fitz.open(out) as doc:
        assert doc.page_count == 3


def test_split_pdf_every_n(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=4)
    out_dir = str(tmp_path / "parts")

    outputs = core.split_pdf(src, out_dir, mode="every_n", n=2)

    assert len(outputs) == 2
    for p in outputs:
        with fitz.open(p) as doc:
            assert doc.page_count == 2


def test_rotate_pdf(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=1)
    out = str(tmp_path / "rotated.pdf")

    core.rotate_pdf(src, out, angle=90)

    with fitz.open(out) as doc:
        assert doc[0].rotation == 90


def test_remove_and_extract_pages(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=3)

    removed = str(tmp_path / "removed.pdf")
    core.remove_pages(src, removed, "2")
    with fitz.open(removed) as doc:
        assert doc.page_count == 2

    extracted = str(tmp_path / "extracted.pdf")
    core.extract_pages(src, extracted, "1")
    with fitz.open(extracted) as doc:
        assert doc.page_count == 1


def test_watermark(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=1)
    out = str(tmp_path / "watermarked.pdf")

    core.add_watermark(src, out, "CONFIDENTIAL")

    assert os.path.exists(out)
    with fitz.open(out) as doc:
        assert "CONFIDENTIAL" in doc[0].get_text()


def test_protect_and_unlock(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=1)
    protected = str(tmp_path / "protected.pdf")
    core.protect_pdf(src, protected, user_password="secret123")

    with fitz.open(protected) as doc:
        assert doc.needs_pass

    unlocked = str(tmp_path / "unlocked.pdf")
    core.unlock_pdf(protected, unlocked, "secret123")
    with fitz.open(unlocked) as doc:
        assert not doc.needs_pass


def test_compress_pdf(tmp_path):
    src = str(tmp_path / "src.pdf")
    doc = fitz.open()
    page = doc.new_page()
    img_path = str(tmp_path / "img.png")
    make_image(img_path, size=(800, 800))
    page.insert_image(page.rect, filename=img_path)
    doc.save(src)
    doc.close()

    out = str(tmp_path / "compressed.pdf")
    original_size, new_size = core.compress_pdf(src, out, level="extreme")

    assert os.path.exists(out)
    assert original_size > 0 and new_size > 0


def test_pdf_to_images_and_back(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=1)
    out_dir = str(tmp_path / "images")

    images = core.pdf_to_images(src, out_dir, fmt="png", dpi=72)
    assert len(images) == 1
    assert os.path.exists(images[0])

    out_pdf = str(tmp_path / "roundtrip.pdf")
    core.images_to_pdf(images, out_pdf)
    with fitz.open(out_pdf) as doc:
        assert doc.page_count == 1


def test_pdf_to_text(tmp_path):
    src = str(tmp_path / "src.pdf")
    make_pdf(src, pages=1, text="extract me")
    out_txt = str(tmp_path / "out.txt")

    core.pdf_to_text(src, out_txt)

    with open(out_txt, encoding="utf-8") as f:
        assert "extract me" in f.read()


def test_parse_page_ranges():
    assert core.parse_page_ranges("1-3,5", 10) == [0, 1, 2, 4]
    assert core.parse_page_ranges("", 3) == [0, 1, 2]
    with pytest.raises(ValueError):
        core.parse_page_ranges("abc", 3)
