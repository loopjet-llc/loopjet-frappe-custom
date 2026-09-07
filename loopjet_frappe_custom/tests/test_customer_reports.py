import json
from pathlib import Path
from types import SimpleNamespace

from loopjet_frappe_custom.customer_reports import (
	CUSTOMER_REPORT_DOCTYPE,
	is_customer_report_pdf,
	make_customer_report_file_private,
)

ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_PATH = (
	ROOT / "loopjet_custom" / "doctype" / "loopjet_customer_report" / "loopjet_customer_report.json"
)


def test_customer_report_doctype_has_the_required_customer_and_pdf_fields() -> None:
	doctype = json.loads(DOCTYPE_PATH.read_text())
	fields = {field["fieldname"]: field for field in doctype["fields"]}

	assert doctype["name"] == CUSTOMER_REPORT_DOCTYPE
	assert fields["customer"]["options"] == "Customer"
	assert fields["report_file"]["fieldtype"] == "Attach"
	assert fields["report_file"]["reqd"] == 1
	assert fields["report_period"]["in_list_view"] == 1
	assert doctype["sort_field"] == "published_on"
	assert doctype["sort_order"] == "DESC"


def test_customer_report_permissions_are_internal_only() -> None:
	doctype = json.loads(DOCTYPE_PATH.read_text())
	roles = {permission["role"] for permission in doctype["permissions"]}

	assert roles == {"System Manager", "Projects Manager"}


def test_customer_report_uploads_are_private_and_pdf_only() -> None:
	assert is_customer_report_pdf("/private/files/report.pdf") is True
	assert is_customer_report_pdf("/private/files/report.PDF?download=1") is True
	assert is_customer_report_pdf("/private/files/report.docx") is False

	report_file = SimpleNamespace(attached_to_doctype=CUSTOMER_REPORT_DOCTYPE, is_private=0)
	unrelated_file = SimpleNamespace(attached_to_doctype="Customer", is_private=0)

	assert make_customer_report_file_private(report_file) is report_file
	assert report_file.is_private == 1
	assert make_customer_report_file_private(unrelated_file) is unrelated_file
	assert unrelated_file.is_private == 0


def test_customer_and_report_forms_expose_upload_list_and_download_actions() -> None:
	customer_js = (ROOT / "public" / "js" / "customer.js").read_text()
	report_js = (
		ROOT
		/ "loopjet_custom"
		/ "doctype"
		/ "loopjet_customer_report"
		/ "loopjet_customer_report.js"
	).read_text()
	hooks = (ROOT / "hooks.py").read_text()

	assert '__("Bericht hochladen")' in customer_js
	assert '__("Kundenberichte öffnen")' in customer_js
	assert "Loopjet Customer Report" in customer_js
	assert '__("PDF herunterladen")' in report_js
	assert "loopjet_frappe_custom.customer_reports.download_customer_report" in report_js
	assert "encodeURIComponent" in report_js
	assert "after_file_upload" in hooks
	assert "make_customer_report_file_private" in hooks


def test_customer_report_download_uses_the_private_file_bytes() -> None:
	source = (ROOT / "customer_reports.py").read_text()

	assert "def download_customer_report" in source
	assert 'report.check_permission("read")' in source
	assert "file_path.read_bytes()" in source
	assert 'frappe.local.response.type = "download"' in source
