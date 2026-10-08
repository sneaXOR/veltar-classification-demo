from __future__ import annotations

from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "backend" / "tests" / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def write_pdf(name: str, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "\n".join(lines), fontsize=11)
    doc.save(FIXTURE_DIR / name)


def render_first_page(pdf_name: str, image_name: str) -> None:
    doc = fitz.open(FIXTURE_DIR / pdf_name)
    page = doc[0]
    page.get_pixmap(matrix=fitz.Matrix(2, 2)).save(FIXTURE_DIR / image_name)


def main() -> None:
    write_pdf(
        "spec_inertial.pdf",
        [
            "INS-7200 inertial navigation specification",
            "CEP rate: 0.5 nm/hr",
            "Operational temperature and qualification thresholds included",
        ],
    )
    write_pdf(
        "non_technical_invoice.pdf",
        [
            "Invoice 2026-001",
            "Commercial shipment documentation",
            "Billing address and payment details only",
        ],
    )
    render_first_page("spec_inertial.pdf", "spec_inertial_page1.png")
    (FIXTURE_DIR / "sample_email.eml").write_text(
        "Subject: Drawing release\n\nPlease find attached the latest engine drawing package.",
        encoding="utf-8",
    )
    print(f"Demo corpus written to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
