import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopjet_frappe_custom import activity_reports
from loopjet_frappe_custom.activity_report_print import ACTIVITY_REPORT_CSS, ACTIVITY_REPORT_HTML

ROOT = Path(__file__).resolve().parents[1]


def test_report_schema_is_independent_and_can_link_one_invoice() -> None:
	report = json.loads(
		(ROOT / "loopjet_custom/doctype/loopjet_activity_report/loopjet_activity_report.json").read_text()
	)
	entry = json.loads(
		(ROOT / "loopjet_custom/doctype/loopjet_activity_entry/loopjet_activity_entry.json").read_text()
	)
	fields = {field["fieldname"]: field for field in report["fields"]}
	entry_fields = {field["fieldname"]: field for field in entry["fields"]}
	assert fields["customer"]["options"] == "Customer"
	assert fields["sales_invoice"]["options"] == "Sales Invoice"
	assert not fields["sales_invoice"].get("reqd")
	assert fields["activities"]["options"] == "Loopjet Activity Entry"
	assert report["is_submittable"] == 1
	assert entry["istable"] == 1
	assert all(entry_fields[name]["reqd"] == 1 for name in ("service_date", "activity_title", "hours"))
	assert {permission["role"] for permission in report["permissions"]} == {
		"System Manager",
		"Accounts Manager",
		"Accounts User",
		"Projects Manager",
	}


def test_activity_rows_enforce_dates_positive_hours_and_period() -> None:
	rows = [
		SimpleNamespace(service_date="2026-11-13", activity_title="Besprechung", hours=1),
		SimpleNamespace(service_date="2026-11-16", activity_title="Architektur", hours=1),
		SimpleNamespace(service_date="2026-11-18", activity_title="Entwicklung", hours=6),
	]
	assert activity_reports.validate_activity_entries(rows, "2026-11-01", "2026-11-30") == 8
	assert activity_reports.validate_activity_entries([], "2026-11-01", "2026-11-30") == 0
	with pytest.raises(ValueError, match="nach dem Beginn"):
		activity_reports.validate_activity_entries(rows, "2026-11-30", "2026-11-01")
	with pytest.raises(ValueError, match="nach dem Berichtszeitraum"):
		activity_reports.validate_activity_entries(rows, "2026-11-01", "2026-11-17")
	rows[2].hours = -1
	with pytest.raises(ValueError, match="positive Stundenzahl"):
		activity_reports.validate_activity_entries(rows, "2026-11-01", "2026-11-30")


def test_invoice_defaults_copy_context_without_inventing_work(monkeypatch) -> None:
	monkeypatch.setattr(activity_reports, "_today", lambda: "2026-11-19")
	invoice = SimpleNamespace(
		name="ACC-SINV-2026-00015",
		customer="thinking services ag",
		company="Loopjet LLC",
		service_period_start="2026-11-01",
		service_period_end="2026-11-30",
		posting_date="2026-11-30",
		loopjet_document_language="Deutsch",
		address_display="Kanalweg 16a<br>9462 Montlingen<br>Schweiz",
	)
	defaults = activity_reports.report_defaults_from_invoice(invoice)
	assert defaults["sales_invoice"] == invoice.name
	assert defaults["customer"] == invoice.customer
	assert defaults["period_start"] == "2026-11-01"
	assert defaults["customer_address"] == "Kanalweg 16a\n9462 Montlingen\nSchweiz"
	assert defaults["report_date"] == "2026-11-19"
	assert "activities" not in defaults


def test_invoice_action_creates_one_report_and_reuses_it(monkeypatch) -> None:
	read_checks = []
	created = []
	invoice = SimpleNamespace(
		name="ACC-SINV-2026-00015",
		customer="thinking services ag",
		company="Loopjet LLC",
		service_period_start="2026-11-01",
		service_period_end="2026-11-30",
		posting_date="2026-11-30",
		loopjet_document_language="Deutsch",
		address_display="Kanalweg 16a",
		docstatus=0,
		check_permission=lambda permission: read_checks.append(permission),
	)
	report = SimpleNamespace(
		name="LAR-2026-00001",
		insert=lambda: created.append(True),
		check_permission=lambda permission: read_checks.append(permission),
	)
	existing = {"name": None}
	defaults = []

	def get_doc(*args):
		if args == ("Sales Invoice", invoice.name):
			return invoice
		if len(args) == 1 and isinstance(args[0], dict):
			defaults.append(args[0])
			return report
		return report

	frappe_stub = SimpleNamespace(
		get_doc=get_doc,
		db=SimpleNamespace(get_value=lambda *args: existing["name"]),
	)
	monkeypatch.setattr(activity_reports, "_frappe", frappe_stub)
	assert activity_reports.get_or_create_for_invoice(invoice.name) == {"name": report.name, "created": True}
	assert created == [True]
	assert defaults[0]["sales_invoice"] == invoice.name
	existing["name"] = report.name
	assert activity_reports.get_or_create_for_invoice(invoice.name) == {"name": report.name, "created": False}
	assert created == [True]
	assert read_checks == ["read", "read", "read"]


def test_print_format_is_time_only_and_cannot_show_payment_details() -> None:
	assert "@page { size: A4" in ACTIVITY_REPORT_CSS
	assert "{{ row.activity_title | e }}" in ACTIVITY_REPORT_HTML
	assert "{{ row.details | e }}" in ACTIVITY_REPORT_HTML
	assert '{{ row.get_formatted("hours", doc) }}' in ACTIVITY_REPORT_HTML
	assert "doc.sales_invoice" in ACTIVITY_REPORT_HTML
	assert not any(
		word in ACTIVITY_REPORT_HTML.lower()
		for word in ("iban", "swift", "bank_", "payment", "rate", "amount")
	)
