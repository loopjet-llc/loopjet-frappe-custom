"""Structured, independently printable activity reports for consulting work."""

from __future__ import annotations

import html
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

try:
	import frappe as _frappe
	from frappe.utils import today as _today
except ModuleNotFoundError:  # Pure helpers remain testable without a Bench installation.
	_frappe = None

	def _today() -> str:
		return date.today().isoformat()


ACTIVITY_REPORT_DOCTYPE = "Loopjet Activity Report"


def _whitelist(function):
	if _frappe is None:
		return function
	return _frappe.whitelist()(function)


def address_display_to_text(value: str | None) -> str:
	"""Turn ERPNext's address HTML into editable plain text for the report."""
	if not value:
		return ""
	text = re.sub(r"(?i)<br\s*/?>|</(?:p|div)>", "\n", value)
	text = re.sub(r"<[^>]+>", "", text)
	return "\n".join(line.strip() for line in html.unescape(text).splitlines() if line.strip())


def calculate_total_hours(rows: list[Any]) -> float:
	"""Sum positive hour values without binary floating-point drift."""
	total = Decimal("0")
	for row in rows:
		try:
			hours = Decimal(str(getattr(row, "hours", None) or 0))
		except InvalidOperation as exc:
			raise ValueError("Stunden müssen eine Zahl sein.") from exc
		if not hours.is_finite() or hours <= 0:
			raise ValueError("Jede Tätigkeit benötigt eine positive Stundenzahl.")
		total += hours
	return float(total.quantize(Decimal("0.01")))


def validate_activity_entries(rows: list[Any], period_start: Any, period_end: Any) -> float:
	"""Validate report dates and contents, then return the total hours."""
	start = date.fromisoformat(str(period_start)[:10]) if period_start else None
	end = date.fromisoformat(str(period_end)[:10]) if period_end else None
	if start and end and start > end:
		raise ValueError("Das Ende des Leistungszeitraums muss nach dem Beginn liegen.")
	for row in rows:
		if not getattr(row, "service_date", None):
			raise ValueError("Jede Tätigkeit benötigt ein Leistungsdatum.")
		if not (getattr(row, "activity_title", None) or "").strip():
			raise ValueError("Jede Tätigkeit benötigt eine Bezeichnung.")
		service_date = date.fromisoformat(str(row.service_date)[:10])
		if start and service_date < start:
			raise ValueError("Ein Leistungsdatum liegt vor dem Berichtszeitraum.")
		if end and service_date > end:
			raise ValueError("Ein Leistungsdatum liegt nach dem Berichtszeitraum.")
	return calculate_total_hours(rows)


def report_defaults_from_invoice(invoice: Any) -> dict[str, Any]:
	"""Copy only context from an invoice; detailed work remains report-owned."""
	period_start = getattr(invoice, "service_period_start", None) or invoice.posting_date
	period_end = getattr(invoice, "service_period_end", None) or invoice.posting_date
	return {
		"doctype": ACTIVITY_REPORT_DOCTYPE,
		"report_title": f"Tätigkeitsbericht zur Rechnung {invoice.name}",
		"customer": invoice.customer,
		"company": invoice.company,
		"sales_invoice": invoice.name,
		"period_start": period_start,
		"period_end": period_end,
		"report_date": _today(),
		"report_language": "Deutsch"
		if getattr(invoice, "loopjet_document_language", None) == "Deutsch"
		else "English",
		"customer_address": address_display_to_text(getattr(invoice, "address_display", None)),
	}


@_whitelist
def get_or_create_for_invoice(invoice_name: str) -> dict[str, Any]:
	"""Open the active report for an invoice or start a new editable draft."""
	if _frappe is None:
		raise RuntimeError("Frappe must be installed to create an activity report.")
	invoice = _frappe.get_doc("Sales Invoice", invoice_name)
	invoice.check_permission("read")
	if invoice.docstatus == 2:
		_frappe.throw(_frappe._("Für eine stornierte Rechnung kann kein Tätigkeitsbericht angelegt werden."))

	existing_name = _frappe.db.get_value(
		ACTIVITY_REPORT_DOCTYPE,
		{"sales_invoice": invoice.name, "docstatus": ["<", 2]},
		"name",
	)
	if existing_name:
		report = _frappe.get_doc(ACTIVITY_REPORT_DOCTYPE, existing_name)
		report.check_permission("read")
		return {"name": report.name, "created": False}

	report = _frappe.get_doc(report_defaults_from_invoice(invoice))
	report.insert()
	return {"name": report.name, "created": True}
