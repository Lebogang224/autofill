"""Persistent storage for PDF templates and their field mappings.

Each template is keyed by a SHA-256 prefix of the blank PDF, so re-uploading
the same blank form automatically picks up the saved field map.

Layout:
  data/templates/<hash>/
    template.pdf          original blank PDF
    meta.json             { name, scale, pages: [...], fields: [...] }
    pages/<i>.png         pre-rendered page image at RENDER_DPI
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium

DATA_DIR = Path(__file__).parent / "data" / "templates"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RENDER_DPI = 144  # 2x of 72


def hash_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def template_dir(template_hash: str) -> Path:
    return DATA_DIR / template_hash


def template_pdf(template_hash: str) -> Path:
    return template_dir(template_hash) / "template.pdf"


def page_image(template_hash: str, index: int) -> Path:
    return template_dir(template_hash) / "pages" / f"{index}.png"


def _render_pages(pdf_path: Path, pages_dir: Path) -> tuple[list[dict], float]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    scale = RENDER_DPI / 72
    pages = []
    for i, page in enumerate(doc):
        w_pt, h_pt = page.get_size()
        img = page.render(scale=scale).to_pil()
        img.save(pages_dir / f"{i}.png")
        pages.append({
            "index": i,
            "width_pt": float(w_pt),
            "height_pt": float(h_pt),
            "image_w": img.width,
            "image_h": img.height,
        })
    return pages, scale


def ingest(pdf_path: str | Path, name: Optional[str] = None) -> tuple[str, dict]:
    """Copy the PDF into the template store and pre-render pages.

    Returns (hash, meta). Idempotent — re-ingesting the same file is a no-op.
    """
    src = Path(pdf_path)
    h = hash_file(src)
    d = template_dir(h)
    d.mkdir(parents=True, exist_ok=True)

    dest = template_pdf(h)
    if not dest.exists():
        shutil.copy(src, dest)

    meta_path = d / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if name and meta.get("name") != name:
            meta["name"] = name
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return h, meta

    pages, scale = _render_pages(dest, d / "pages")
    meta = {
        "name": name or src.name,
        "scale": scale,
        "pages": pages,
        "fields": [],
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return h, meta


def get_meta(template_hash: str) -> Optional[dict]:
    p = template_dir(template_hash) / "meta.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_fields(template_hash: str, fields: list[dict]) -> bool:
    meta = get_meta(template_hash)
    if not meta:
        return False
    meta["fields"] = fields
    (template_dir(template_hash) / "meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return True


def list_templates() -> list[dict]:
    out = []
    if not DATA_DIR.exists():
        return out
    for d in sorted(DATA_DIR.iterdir()):
        if not d.is_dir():
            continue
        mp = d / "meta.json"
        if not mp.exists():
            continue
        meta = json.loads(mp.read_text(encoding="utf-8"))
        out.append({
            "hash": d.name,
            "name": meta.get("name", d.name),
            "page_count": len(meta.get("pages", [])),
            "field_count": len(meta.get("fields", [])),
        })
    return out


def delete_template(template_hash: str) -> bool:
    d = template_dir(template_hash)
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True
