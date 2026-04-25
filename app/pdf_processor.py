import re
import pytesseract
import pdfplumber
from pdfrw import PdfReader, PdfWriter
from pdfrw.objects import PdfName
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl
from reportlab.pdfgen import canvas
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np

ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY = '/V'

FIELD_PATTERNS = {
    'full_name': r'(?:name|full[_\s]*name)[\s:\-]*(.+)',
    'ssn': r'\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b',
    'email': r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
    'phone': r'(?:phone|tel|telephone)[\s:\-]*([\d\s().-]+)',
    'address': r'(?:address|street)[\s:\-]*(.+)',
    'date_of_birth': r'(?:dob|date\s*of\s*birth)[\s:\-]*([\d/\s-]+)',
}


def extract_data_from_pdf(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    if not full_text.strip():
        images = convert_from_path(pdf_path, dpi=300)
        full_text = ""
        for img in images:
            try:
                gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
                denoised = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
                thresh = cv2.adaptiveThreshold(
                    denoised, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2,
                )
                processed = Image.fromarray(thresh)
                full_text += pytesseract.image_to_string(
                    processed, config=r'--oem 3 --psm 6 -l eng'
                ) + "\n"
            except Exception as e:
                print(f"OCR failed for page: {e}")

    data = {}
    for field, pattern in FIELD_PATTERNS.items():
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            data[field] = m.group(1).strip()
    return data


def is_digital_form(pdf_path: str) -> bool:
    try:
        pdf = PdfReader(pdf_path)
        return any(page.get(ANNOT_KEY) for page in pdf.pages)
    except Exception:
        return False


def fill_digital_pdf(template_path: str, data: dict, output_path: str) -> bool:
    try:
        template = PdfReader(template_path)
        for page in template.pages:
            for annotation in page.get(ANNOT_KEY) or []:
                if annotation.get(ANNOT_FIELD_KEY):
                    field_name = annotation[ANNOT_FIELD_KEY][1:-1]
                    if field_name in data:
                        annotation.update({ANNOT_VAL_KEY: f'({data[field_name]})'})
        PdfWriter().write(output_path, template)
        return True
    except Exception as e:
        print(f"Digital fill failed: {e}")
        return False


def overlay_fill_pdf(template_path: str, data: dict, output_path: str) -> bool:
    try:
        c = canvas.Canvas(output_path)
        template = PdfReader(template_path)
        keys = list(data.keys())
        for page in template.pages:
            mb = page[PdfName.MediaBox]
            w, h = float(mb[2]), float(mb[3])
            c.setPageSize((w, h))
            c.doForm(makerl(c, pagexobj(page)))
            for field, value in data.items():
                y = h - (100 + 20 * keys.index(field))
                c.drawString(100, y, f"{field}: {value}")
            c.showPage()
        c.save()
        return True
    except Exception as e:
        print(f"Overlay fill error: {e}")
        return False


def fill_pdf(template_path: str, data: dict, output_path: str) -> bool:
    if is_digital_form(template_path):
        return fill_digital_pdf(template_path, data, output_path)
    return overlay_fill_pdf(template_path, data, output_path)


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s not in ("", "0", "false", "no", "off", "n")


def fill_with_mapping(template_path: str, fields: list, data: dict, output_path: str) -> bool:
    """Overlay text and checkmarks onto a template using saved field coordinates.

    Each field dict (top-left origin in PDF points):
      { name, type: 'text'|'checkbox', page, x, y, width, height,
        font_size?, align? ('left'|'center'|'right') }
    """
    try:
        template = PdfReader(template_path)
        c = canvas.Canvas(output_path)

        by_page: dict[int, list[dict]] = {}
        for f in fields:
            by_page.setdefault(int(f.get("page", 0)), []).append(f)

        for i, page in enumerate(template.pages):
            mb = page[PdfName.MediaBox]
            page_w = float(mb[2])
            page_h = float(mb[3])
            c.setPageSize((page_w, page_h))
            c.doForm(makerl(c, pagexobj(page)))

            for fld in by_page.get(i, []):
                name = fld.get("name", "")
                value = data.get(name, "")
                ftype = fld.get("type", "text")
                x = float(fld["x"])
                y_top = float(fld["y"])
                w = float(fld.get("width", 100))
                h = float(fld.get("height", 18))
                fs = float(fld.get("font_size") or max(8, min(h - 4, 14)))

                if ftype == "checkbox":
                    if not _truthy(value):
                        continue
                    side = min(w, h) - 2
                    cx = x + (w - side) / 2
                    cy_baseline = page_h - y_top - h + (h - side) / 2 + 1
                    c.setFont("Helvetica-Bold", side)
                    c.drawString(cx, cy_baseline, "X")
                    continue

                text = "" if value is None else str(value)
                if not text:
                    continue
                c.setFont("Helvetica", fs)
                baseline = page_h - y_top - h + (h - fs) / 2 + 1
                align = fld.get("align", "left")
                if align == "center":
                    c.drawCentredString(x + w / 2, baseline, text)
                elif align == "right":
                    c.drawRightString(x + w - 2, baseline, text)
                else:
                    c.drawString(x + 3, baseline, text)

            c.showPage()

        c.save()
        return True
    except Exception as e:
        print(f"Mapping fill failed: {e}")
        return False


def validate_data(data: dict) -> list:
    errors = []
    if not any(f in data and data[f].strip() for f in ('full_name', 'name')):
        errors.append("Full name is required")
    ssn = data.get('ssn', '').strip()
    if ssn and len(re.sub(r'[^\d]', '', ssn)) != 9:
        errors.append("SSN must be 9 digits")
    return errors
