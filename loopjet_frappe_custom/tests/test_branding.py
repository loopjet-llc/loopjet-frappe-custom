from pathlib import Path


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
