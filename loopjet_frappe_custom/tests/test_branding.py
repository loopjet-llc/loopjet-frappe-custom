from pathlib import Path

from loopjet_frappe_custom.invoice_print import INVOICE_CSS, INVOICE_HTML


def test_invoice_template_uses_the_default_company_bank_account() -> None:
	branding_source = Path(__file__).resolve().parents[1].joinpath("branding.py").read_text()

	assert 'doc.html = INVOICE_HTML if doctype == "Sales Invoice" else PRINT_HTML' in branding_source
	assert '"is_company_account": 1, "is_default": 1, "disabled": 0' in INVOICE_HTML
	assert '{% if not is_offer and bank_iban %}' in INVOICE_HTML
	assert "{{ bank_iban }}" in INVOICE_HTML
	assert "{{ bank_bic }}" in INVOICE_HTML
	assert "lj-payment" in INVOICE_CSS


def test_invoice_template_omits_visual_pills_and_in_words_box() -> None:
	branding_source = Path(__file__).resolve().parents[1].joinpath("branding.py").read_text()

	assert "lj-status" not in branding_source
	assert "lj-eyebrow" not in branding_source
	assert "doc.in_words" not in branding_source
	assert "In words" not in branding_source
	assert "In Worten" not in branding_source


def test_invoice_template_does_not_force_a4_height() -> None:
	branding_source = Path(__file__).resolve().parents[1].joinpath("branding.py").read_text()

	assert "min-height: 270mm" not in branding_source


def test_invoice_template_renders_service_period_only_when_present() -> None:
	branding_source = Path(__file__).resolve().parents[1].joinpath("branding.py").read_text()

	assert "Leistungszeitraum" in branding_source
	assert "service_period_value" in branding_source
	assert "{% if service_period_value %}" in branding_source
	assert '"reqd": 0' in branding_source
	assert '"reqd": 1' not in branding_source
