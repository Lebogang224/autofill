import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytesseract
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pdf_processor import (
    extract_data_from_pdf,
    fill_pdf,
    fill_with_mapping,
    validate_data,
)
import templates_store as ts

if sys.platform == "win32":
    tess = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tess):
        pytesseract.pytesseract.tesseract_cmd = tess

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
WORK_DIR = Path(tempfile.gettempdir()) / "autofill_web"
WORK_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AutoFill")


def _save_upload(upload: UploadFile, suffix: str) -> Path:
    path = WORK_DIR / f"{uuid.uuid4().hex}{suffix}"
    with path.open("wb") as f:
        f.write(upload.file.read())
    return path


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/editor", response_class=HTMLResponse)
def editor():
    return (STATIC_DIR / "editor.html").read_text(encoding="utf-8")


# ---------- legacy extract / fill ----------

@app.post("/api/extract")
async def api_extract(filled_pdf: UploadFile = File(...)):
    src = _save_upload(filled_pdf, ".pdf")
    try:
        data = extract_data_from_pdf(str(src))
        return {"data": data, "errors": validate_data(data)}
    finally:
        src.unlink(missing_ok=True)


@app.post("/api/fill")
async def api_fill(empty_form: UploadFile = File(...), data: str = Form(...)):
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON in 'data'")

    template = _save_upload(empty_form, ".pdf")
    output = WORK_DIR / f"filled_{uuid.uuid4().hex}.pdf"
    try:
        if not fill_pdf(str(template), payload, str(output)):
            raise HTTPException(500, "Failed to fill PDF")
        return {"download_id": output.name}
    finally:
        template.unlink(missing_ok=True)


@app.post("/api/fill-from-json")
async def api_fill_from_json(
    empty_form: UploadFile = File(...),
    json_file: UploadFile = File(...),
):
    try:
        payload = json.loads(json_file.file.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON file")

    template = _save_upload(empty_form, ".pdf")
    output = WORK_DIR / f"filled_{uuid.uuid4().hex}.pdf"
    try:
        if not fill_pdf(str(template), payload, str(output)):
            raise HTTPException(500, "Failed to fill PDF")
        return {"download_id": output.name}
    finally:
        template.unlink(missing_ok=True)


@app.get("/api/download/{download_id}")
def api_download(download_id: str):
    path = WORK_DIR / download_id
    if not path.exists() or ".." in download_id or "/" in download_id:
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="application/pdf", filename="filled_form.pdf")


# ---------- templates ----------

def _public_meta(template_hash: str) -> dict:
    meta = ts.get_meta(template_hash)
    if not meta:
        raise HTTPException(404, "Template not found")
    return {
        "hash": template_hash,
        "name": meta["name"],
        "scale": meta["scale"],
        "pages": meta["pages"],
        "fields": meta.get("fields", []),
    }


@app.get("/api/templates")
def api_list_templates():
    return {"templates": ts.list_templates()}


@app.post("/api/templates")
async def api_create_template(pdf: UploadFile = File(...), name: str = Form(None)):
    src = _save_upload(pdf, ".pdf")
    try:
        h, _ = ts.ingest(src, name=name or pdf.filename)
        return _public_meta(h)
    finally:
        src.unlink(missing_ok=True)


@app.get("/api/templates/{template_hash}")
def api_get_template(template_hash: str):
    return _public_meta(template_hash)


@app.put("/api/templates/{template_hash}/fields")
async def api_save_fields(template_hash: str, payload: dict):
    fields = payload.get("fields")
    if not isinstance(fields, list):
        raise HTTPException(400, "fields must be a list")
    if not ts.save_fields(template_hash, fields):
        raise HTTPException(404, "Template not found")
    return {"ok": True, "field_count": len(fields)}


@app.delete("/api/templates/{template_hash}")
def api_delete_template(template_hash: str):
    if not ts.delete_template(template_hash):
        raise HTTPException(404, "Template not found")
    return {"ok": True}


@app.get("/api/templates/{template_hash}/page/{index}")
def api_template_page(template_hash: str, index: int):
    p = ts.page_image(template_hash, index)
    if not p.exists():
        raise HTTPException(404, "Page not found")
    return FileResponse(p, media_type="image/png")


@app.post("/api/templates/{template_hash}/fill")
async def api_template_fill(template_hash: str, payload: dict):
    meta = ts.get_meta(template_hash)
    if not meta:
        raise HTTPException(404, "Template not found")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise HTTPException(400, "data must be an object")

    template = ts.template_pdf(template_hash)
    output = WORK_DIR / f"filled_{uuid.uuid4().hex}.pdf"
    if not fill_with_mapping(str(template), meta.get("fields", []), data, str(output)):
        raise HTTPException(500, "Failed to fill template")
    return {"download_id": output.name}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
