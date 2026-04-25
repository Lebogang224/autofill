"""Generate a more complex multi-page form pair for testing.

  complex_filled.pdf - text PDF with rich extractable content
  complex_empty.pdf  - multi-section AcroForm with text, checkbox, choice fields
"""
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
PAGE_W, PAGE_H = LETTER
M = 54  # margin

ACCENT = HexColor("#1f3a8a")
SUBTLE = HexColor("#e5e7eb")
MUTED = HexColor("#6b7280")

DATA = {
    "applicant": {
        "full_name": "Marcus Aurelius Whitfield",
        "preferred_name": "Marc",
        "date_of_birth": "1987-09-14",
        "ssn": "452-88-3917",
        "drivers_license": "WH-4429871-IL",
        "marital_status": "Married",
        "dependents": "2",
        "citizenship": "US Citizen",
    },
    "contact": {
        "email": "marcus.whitfield@northbrook-consulting.com",
        "phone": "(312) 555-0184",
        "alt_phone": "(312) 555-7720",
        "address": "4821 N. Sheridan Rd, Apt 3B",
        "city": "Chicago",
        "state": "IL",
        "zip": "60640",
        "years_at_address": "6",
    },
    "employment": {
        "employer": "Northbrook Strategic Consulting LLC",
        "job_title": "Senior Engagement Director",
        "employer_address": "200 W. Madison St, Suite 2400, Chicago, IL 60606",
        "supervisor": "Elena Rodriguez-Park",
        "supervisor_phone": "(312) 555-0911",
        "start_date": "2019-03-04",
        "annual_income": "$184,500.00",
        "bonus_income": "$22,400.00",
        "other_income": "$8,200.00",
    },
    "financial": {
        "bank_name": "First Midwest National",
        "account_type": "Checking + Savings",
        "checking_balance": "$14,820.55",
        "savings_balance": "$72,341.18",
        "monthly_rent": "$2,850.00",
        "monthly_debt": "$1,420.00",
        "credit_score": "782",
    },
    "emergency": {
        "ec_name": "Priya Whitfield",
        "ec_relationship": "Spouse",
        "ec_phone": "(312) 555-2210",
        "ec_email": "priya.w@gmail.com",
    },
    "consent": {
        "consent_credit_check": True,
        "consent_background_check": True,
        "consent_marketing": False,
        "preferred_contact": "Email",
    },
    "signature": {
        "signed_by": "Marcus A. Whitfield",
        "signed_date": "2026-04-22",
    },
}


# -------- shared layout helpers --------

def header(c, title, subtitle):
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 80, PAGE_W, 80, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(M, PAGE_H - 48, title)
    c.setFont("Helvetica", 10)
    c.drawString(M, PAGE_H - 66, subtitle)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - M, PAGE_H - 48, "Form NB-2026 / Rev. 4")
    c.drawRightString(PAGE_W - M, PAGE_H - 60, "Confidential")
    c.setFillColor(black)


def section(c, y, title):
    c.setFillColor(SUBTLE)
    c.rect(M, y - 4, PAGE_W - 2 * M, 22, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M + 8, y + 3, title.upper())
    c.setFillColor(black)
    return y - 18


def footer(c, page_num):
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(M, 30, "Northbrook Strategic Consulting LLC  ·  Loan Application Intake")
    c.drawRightString(PAGE_W - M, 30, f"Page {page_num}")
    c.setFillColor(black)


# -------- filled (text) PDF --------

def draw_kv_text(c, y, items, label_w=180):
    c.setFont("Helvetica", 10)
    for label, value in items:
        c.setFillColor(MUTED)
        c.drawString(M + 8, y, f"{label}:")
        c.setFillColor(black)
        c.drawString(M + 8 + label_w, y, str(value))
        y -= 16
    return y - 6


def make_filled(path: Path):
    c = canvas.Canvas(str(path), pagesize=LETTER)

    # ----- Page 1: Personal + Contact -----
    header(c, "Loan Application — Intake Packet", "Submitted 2026-04-22 09:14 CT")
    y = PAGE_H - 110

    y = section(c, y, "Applicant Information")
    a = DATA["applicant"]
    y = draw_kv_text(c, y - 4, [
        ("Full Name", a["full_name"]),
        ("Preferred Name", a["preferred_name"]),
        ("Date of Birth", a["date_of_birth"]),
        ("SSN", a["ssn"]),
        ("Driver's License", a["drivers_license"]),
        ("Marital Status", a["marital_status"]),
        ("Dependents", a["dependents"]),
        ("Citizenship", a["citizenship"]),
    ])

    y = section(c, y, "Contact Information")
    co = DATA["contact"]
    y = draw_kv_text(c, y - 4, [
        ("Email", co["email"]),
        ("Phone", co["phone"]),
        ("Alternate Phone", co["alt_phone"]),
        ("Address", co["address"]),
        ("City / State / ZIP", f"{co['city']}, {co['state']} {co['zip']}"),
        ("Years at Address", co["years_at_address"]),
    ])

    y = section(c, y, "Employment")
    e = DATA["employment"]
    y = draw_kv_text(c, y - 4, [
        ("Employer", e["employer"]),
        ("Job Title", e["job_title"]),
        ("Employer Address", e["employer_address"]),
        ("Supervisor", e["supervisor"]),
        ("Supervisor Phone", e["supervisor_phone"]),
        ("Start Date", e["start_date"]),
        ("Annual Income", e["annual_income"]),
        ("Bonus Income", e["bonus_income"]),
        ("Other Income", e["other_income"]),
    ])

    footer(c, 1)
    c.showPage()

    # ----- Page 2: Financial + Emergency + Consent -----
    header(c, "Loan Application — Continued", "Section B")
    y = PAGE_H - 110

    y = section(c, y, "Financial Snapshot")
    f = DATA["financial"]
    y = draw_kv_text(c, y - 4, [
        ("Bank Name", f["bank_name"]),
        ("Account Type", f["account_type"]),
        ("Checking Balance", f["checking_balance"]),
        ("Savings Balance", f["savings_balance"]),
        ("Monthly Rent", f["monthly_rent"]),
        ("Monthly Debt Payments", f["monthly_debt"]),
        ("Credit Score (self-reported)", f["credit_score"]),
    ])

    y = section(c, y, "Emergency Contact")
    em = DATA["emergency"]
    y = draw_kv_text(c, y - 4, [
        ("Name", em["ec_name"]),
        ("Relationship", em["ec_relationship"]),
        ("Phone", em["ec_phone"]),
        ("Email", em["ec_email"]),
    ])

    y = section(c, y, "Consent & Preferences")
    cs = DATA["consent"]
    yes = lambda b: "[X] Yes" if b else "[ ] No"
    y = draw_kv_text(c, y - 4, [
        ("Authorize credit check", yes(cs["consent_credit_check"])),
        ("Authorize background check", yes(cs["consent_background_check"])),
        ("Opt-in to marketing emails", yes(cs["consent_marketing"])),
        ("Preferred contact method", cs["preferred_contact"]),
    ])

    y = section(c, y, "Signature")
    s = DATA["signature"]
    c.setFont("Helvetica-Oblique", 14)
    c.drawString(M + 8, y - 24, s["signed_by"])
    c.setStrokeColor(MUTED)
    c.line(M + 8, y - 28, M + 320, y - 28)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawString(M + 8, y - 40, f"Signed electronically on {s['signed_date']}")
    c.setFillColor(black)

    footer(c, 2)
    c.save()


# -------- empty AcroForm PDF --------

def make_empty(path: Path):
    c = canvas.Canvas(str(path), pagesize=LETTER)
    form = c.acroForm

    def text_field(name, x, y, w=240, h=18, multiline=False):
        form.textfield(
            name=name, tooltip=name,
            x=x, y=y - 4, width=w, height=h,
            borderStyle="underlined", forceBorder=True,
            fieldFlags="multiline" if multiline else "",
        )

    def checkbox(name, x, y):
        form.checkbox(
            name=name, tooltip=name,
            x=x, y=y - 2, size=12,
            buttonStyle="check", borderStyle="solid",
            forceBorder=True,
        )

    def choice(name, options, x, y, w=160, h=18):
        form.choice(
            name=name, tooltip=name, value=options[0],
            options=options, x=x, y=y - 4,
            width=w, height=h, forceBorder=True,
        )

    def labeled_text(label, key, x, y, w=240, multiline=False):
        c.setFont("Helvetica", 9)
        c.setFillColor(MUTED)
        c.drawString(x, y + 14, label)
        c.setFillColor(black)
        text_field(key, x, y, w=w, multiline=multiline)

    # ----- Page 1 -----
    header(c, "Loan Application — Intake Packet", "Please complete all sections.")
    y = PAGE_H - 110

    y = section(c, y, "Applicant Information")
    y -= 6
    labeled_text("Full Name", "full_name", M + 8, y - 18, w=300)
    labeled_text("Preferred Name", "preferred_name", M + 320, y - 18, w=180)
    y -= 50
    labeled_text("Date of Birth (YYYY-MM-DD)", "date_of_birth", M + 8, y - 18, w=140)
    labeled_text("SSN", "ssn", M + 160, y - 18, w=140)
    labeled_text("Driver's License", "drivers_license", M + 312, y - 18, w=180)
    y -= 50
    c.setFont("Helvetica", 9); c.setFillColor(MUTED)
    c.drawString(M + 8, y, "Marital Status")
    c.setFillColor(black)
    choice("marital_status", ["Single", "Married", "Divorced", "Widowed"], M + 8, y - 16, w=140)
    labeled_text("Dependents", "dependents", M + 160, y - 16, w=80)
    c.setFont("Helvetica", 9); c.setFillColor(MUTED)
    c.drawString(M + 252, y, "Citizenship")
    c.setFillColor(black)
    choice("citizenship", ["US Citizen", "Permanent Resident", "Visa Holder", "Other"],
           M + 252, y - 16, w=180)
    y -= 60

    y = section(c, y, "Contact Information")
    y -= 6
    labeled_text("Email", "email", M + 8, y - 18, w=300)
    labeled_text("Phone", "phone", M + 320, y - 18, w=180)
    y -= 50
    labeled_text("Alternate Phone", "alt_phone", M + 8, y - 18, w=180)
    labeled_text("Years at Current Address", "years_at_address", M + 200, y - 18, w=80)
    y -= 50
    labeled_text("Street Address", "address", M + 8, y - 18, w=480)
    y -= 50
    labeled_text("City", "city", M + 8, y - 18, w=200)
    labeled_text("State", "state", M + 220, y - 18, w=60)
    labeled_text("ZIP", "zip", M + 290, y - 18, w=100)
    y -= 60

    y = section(c, y, "Employment")
    y -= 6
    labeled_text("Employer", "employer", M + 8, y - 18, w=300)
    labeled_text("Job Title", "job_title", M + 320, y - 18, w=180)
    y -= 50
    labeled_text("Employer Address", "employer_address", M + 8, y - 18, w=480)
    y -= 50
    labeled_text("Supervisor", "supervisor", M + 8, y - 18, w=200)
    labeled_text("Supervisor Phone", "supervisor_phone", M + 220, y - 18, w=160)
    labeled_text("Start Date", "start_date", M + 392, y - 18, w=100)
    y -= 50
    labeled_text("Annual Income", "annual_income", M + 8, y - 18, w=140)
    labeled_text("Bonus Income", "bonus_income", M + 160, y - 18, w=140)
    labeled_text("Other Income", "other_income", M + 312, y - 18, w=140)

    footer(c, 1)
    c.showPage()

    # ----- Page 2 -----
    header(c, "Loan Application — Continued", "Section B")
    y = PAGE_H - 110

    y = section(c, y, "Financial Snapshot")
    y -= 6
    labeled_text("Bank Name", "bank_name", M + 8, y - 18, w=240)
    c.setFont("Helvetica", 9); c.setFillColor(MUTED)
    c.drawString(M + 260, y - 4, "Account Type")
    c.setFillColor(black)
    choice("account_type", ["Checking", "Savings", "Checking + Savings", "Money Market"],
           M + 260, y - 22, w=200)
    y -= 50
    labeled_text("Checking Balance", "checking_balance", M + 8, y - 18, w=140)
    labeled_text("Savings Balance", "savings_balance", M + 160, y - 18, w=140)
    labeled_text("Credit Score", "credit_score", M + 312, y - 18, w=80)
    y -= 50
    labeled_text("Monthly Rent", "monthly_rent", M + 8, y - 18, w=140)
    labeled_text("Monthly Debt Payments", "monthly_debt", M + 160, y - 18, w=180)
    y -= 60

    y = section(c, y, "Emergency Contact")
    y -= 6
    labeled_text("Name", "ec_name", M + 8, y - 18, w=240)
    labeled_text("Relationship", "ec_relationship", M + 260, y - 18, w=200)
    y -= 50
    labeled_text("Phone", "ec_phone", M + 8, y - 18, w=180)
    labeled_text("Email", "ec_email", M + 200, y - 18, w=280)
    y -= 60

    y = section(c, y, "Consent & Preferences")
    y -= 8
    items = [
        ("consent_credit_check", "I authorize a credit check"),
        ("consent_background_check", "I authorize a background check"),
        ("consent_marketing", "Send me marketing communications"),
    ]
    for key, label in items:
        checkbox(key, M + 8, y - 4)
        c.setFont("Helvetica", 10)
        c.drawString(M + 28, y - 2, label)
        y -= 22
    y -= 4
    c.setFont("Helvetica", 9); c.setFillColor(MUTED)
    c.drawString(M + 8, y, "Preferred contact method")
    c.setFillColor(black)
    choice("preferred_contact", ["Email", "Phone", "SMS", "Postal Mail"],
           M + 8, y - 18, w=180)
    y -= 60

    y = section(c, y, "Signature")
    y -= 6
    labeled_text("Signed by (full legal name)", "signed_by", M + 8, y - 18, w=300)
    labeled_text("Date", "signed_date", M + 320, y - 18, w=140)

    footer(c, 2)
    c.save()


if __name__ == "__main__":
    filled = OUT / "complex_filled.pdf"
    empty = OUT / "complex_empty.pdf"
    make_filled(filled)
    make_empty(empty)
    print(f"Wrote {filled}")
    print(f"Wrote {empty}")
