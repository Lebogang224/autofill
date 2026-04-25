"""Generate two sample PDFs for testing AutoFill.

  filled_sample.pdf  - text PDF containing extractable fields (regex source).
  empty_form.pdf     - blank PDF with AcroForm fields matching the extractor keys.
"""
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.pdfbase.acroform import AcroForm

OUT = Path(__file__).parent
OUT.mkdir(exist_ok=True)

FIELDS = [
    ("full_name", "Full Name", "Jane Q. Doe"),
    ("date_of_birth", "Date of Birth", "1990-04-12"),
    ("ssn", "SSN", "123-45-6789"),
    ("email", "Email", "jane.doe@example.com"),
    ("phone", "Phone", "(555) 123-4567"),
    ("address", "Address", "1428 Elm Street, Springfield, IL 62701"),
]


def make_filled(path: Path):
    c = canvas.Canvas(str(path), pagesize=LETTER)
    w, h = LETTER
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, h - 80, "Patient Intake Form")
    c.setFont("Helvetica", 11)
    c.drawString(72, h - 100, "Submitted 2026-04-25")

    c.setFont("Helvetica", 12)
    y = h - 150
    for _, label, value in FIELDS:
        c.drawString(72, y, f"{label}: {value}")
        y -= 28
    c.showPage()
    c.save()


def make_empty_form(path: Path):
    c = canvas.Canvas(str(path), pagesize=LETTER)
    w, h = LETTER
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, h - 80, "Patient Intake Form")
    c.setFont("Helvetica", 11)
    c.drawString(72, h - 100, "Please complete all fields.")

    form = c.acroForm
    c.setFont("Helvetica", 12)
    y = h - 150
    for key, label, _ in FIELDS:
        c.drawString(72, y, f"{label}:")
        form.textfield(
            name=key,
            tooltip=label,
            x=220, y=y - 4, width=300, height=20,
            borderStyle="underlined",
            borderColor=None,
            fillColor=None,
            forceBorder=True,
        )
        y -= 36
    c.showPage()
    c.save()


if __name__ == "__main__":
    filled = OUT / "filled_sample.pdf"
    empty = OUT / "empty_form.pdf"
    make_filled(filled)
    make_empty_form(empty)
    print(f"Wrote {filled}")
    print(f"Wrote {empty}")
