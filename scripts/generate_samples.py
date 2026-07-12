"""Renders synthetic placeholder letters into samples/ for early pipeline
development, before real (redacted) letter photos are available. All NRIC
numbers, names, and amounts below are fake."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

LETTERS = {
    "cpf_statement": """CENTRAL PROVIDENT FUND BOARD
CPF Contribution Statement

Dear Member,

NRIC: S1234567A (placeholder)
This statement confirms your CPF contributions for
the period Jan 2026 - Jun 2026.

Total contributions received: $9,240.00
Your CPF balances as at 30 Jun 2026:
  Ordinary Account: $54,120.33
  Special Account: $21,880.10
  MediSave Account: $18,502.44

No action is required. This statement is for your
records only.

CPF Board""",
    "iras_notice": """INLAND REVENUE AUTHORITY OF SINGAPORE
Notice of Assessment - Year of Assessment 2026

Dear Taxpayer,

Tax Reference: S1234567A (placeholder)

Your income tax for YA2026 has been assessed:
  Chargeable Income: $52,000
  Tax Payable: $1,180.00

Payment is due by 31 Aug 2026. You may pay via
GIRO, PayNow, or AXS. Late payment incurs a 5%
penalty.

IRAS""",
    "town_council_notice": """ANG MOK KIO TOWN COUNCIL
Conservancy & Service Charges - Reminder Notice

Dear Resident,

Block 123 Ang Mo Kio Ave 4, #05-678

Your conservancy charges for Jul 2026 amounting to
$89.50 remain unpaid. Please settle this amount by
25 Jul 2026 to avoid a late payment surcharge.

Payment can be made via AXS, SAM, or GIRO.

Ang Mo Kio Town Council""",
    "polyclinic_bill": """NATIONAL HEALTHCARE GROUP POLYCLINICS
Outpatient Bill

Dear Patient,

Visit date: 3 Jul 2026
Consultation & Medication: $42.00
Subsidy applied: -$25.00
Amount payable: $17.00

Please settle payment within 30 days at any
polyclinic counter or via the HealthHub app.

NHG Polyclinics""",
    "scam_letter": """URGENT NOTICE - IMMEDIATE ACTION REQUIRED

Dear Valued Customer,

Our records show you have an outstanding
government fine of $3,500 that must be paid TODAY
to avoid arrest and legal action. Failure to
respond within 2 hours will result in a warrant
being issued.

To settle this matter immediately, transfer the
amount to PayNow number 8123 4567 and reply with
your full NRIC number and bank account details for
verification.

This is your FINAL warning.

Enforcement Division""",
}

BLURRED_FROM = "town_council_notice"


def render_letter(text: str, path: Path) -> None:
    canvas = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=20)
    draw.multiline_text((40, 40), text, fill="black", font=font, spacing=10)
    canvas.save(path, "JPEG")


def render_blurred_variant(source_text: str, path: Path) -> None:
    canvas = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=20)
    draw.multiline_text((40, 40), source_text, fill="black", font=font, spacing=10)
    canvas = canvas.rotate(6, expand=True, fillcolor="white")
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=3))
    canvas.save(path, "JPEG")


def main() -> None:
    SAMPLES_DIR.mkdir(exist_ok=True)
    for name, text in LETTERS.items():
        render_letter(text, SAMPLES_DIR / f"{name}.jpg")
    render_blurred_variant(LETTERS[BLURRED_FROM], SAMPLES_DIR / "bad_quality_photo.jpg")
    print(f"Generated {len(LETTERS) + 1} sample letters in {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
