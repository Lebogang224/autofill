# AutoFill

A local web app that fills out PDF forms for you — including scanned and "flat" PDFs that don't have any fillable fields built in.

Originally a PyQt5 desktop tool; rebuilt as a FastAPI + modern web UI that runs entirely on your own machine. No files leave your computer.

## What it can do

Three ways to fill a form:

### 1. Templates — works on *any* PDF
The headline feature. Works on flat scans, photos of paper forms, anything.

1. Upload a blank PDF once.
2. The editor renders each page; draw rectangles where each field should go and name them (`full_name`, `email`, `signed_date`, …).
3. Save. The mapping is fingerprinted to the file's hash, so re-uploading the same blank form auto-loads its layout.
4. From then on: pick the template → fill in values → download a stamped PDF.

Supports text fields (with font size + alignment) and checkboxes. Multi-page PDFs supported.

### 2. Extract & Fill
Hand it a *filled* PDF and a *blank* one. It pulls fields out of the filled document (regex over text; OCR fallback for scans) and pours them into AcroForm fields on the blank.

Best for fillable PDFs that already have form widgets.

### 3. Fill from JSON
Hand it a JSON file of `{ field_name: value }` plus a blank fillable PDF. Done.

## Run it

Requires Python 3.11+ and (optional, for OCR) Tesseract installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app\server.py
```

Open http://127.0.0.1:8000.

## Sample forms

`samples/` contains generators for two test PDFs each:

```bash
.venv\Scripts\python samples\generate_samples.py    # simple intake form
.venv\Scripts\python samples\generate_complex.py    # multi-page application
```

Each script writes a *filled* version (text PDF you can extract from) and an *empty* version (AcroForm PDF you can fill).

## Project layout

```
app/
  server.py            FastAPI app, all HTTP endpoints
  pdf_processor.py     PDF read / extract / fill core
  templates_store.py   Persistent template + field-mapping store
  static/
    index.html         Main UI (Templates · Extract · JSON tabs)
    editor.html        Coordinate-mapping editor
  data/templates/      Saved templates (gitignored)
samples/               Test-PDF generators
autofill_desktop.py    Original PyQt5 desktop app (still runs)
```

## Notes

- Templates are stored at `app/data/templates/<hash>/`. Delete the folder to forget a template.
- The PyQt5 desktop app (`app/autofill_desktop.py`) is preserved for reference but the web UI supersedes it.
- Filled PDFs land in your OS temp dir and are served once — they're not retained long-term.
