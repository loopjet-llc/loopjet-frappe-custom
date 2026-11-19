from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from loopjet_frappe_custom.activity_reports import ACTIVITY_REPORT_DOCTYPE, validate_activity_entries


class LoopjetActivityReport(Document):
	def validate(self) -> None:
		self.validate_period_and_rows()
		self.validate_invoice_link()

	def validate_period_and_rows(self) -> None:
		try:
			self.total_hours = validate_activity_entries(
				self.activities or [], self.period_start, self.period_end
			)
		except ValueError as exc:
			frappe.throw(_(str(exc)))

	def validate_invoice_link(self) -> None:
		if not self.sales_invoice:
			return
		invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
		invoice.check_permission("read")
		if invoice.docstatus == 2:
			frappe.throw(_("Eine stornierte Rechnung kann nicht verknüpft werden."))
		if invoice.customer != self.customer or invoice.company != self.company:
			frappe.throw(_("Kunde und eigene Firma müssen zur verknüpften Rechnung passen."))
		existing_name = frappe.db.get_value(
			ACTIVITY_REPORT_DOCTYPE,
			{"sales_invoice": self.sales_invoice, "docstatus": ["<", 2]},
			"name",
		)
		if existing_name and existing_name != self.name:
			frappe.throw(_("Diese Rechnung hat bereits einen aktiven Tätigkeitsbericht."))

	def before_submit(self) -> None:
		if not self.activities:
			frappe.throw(_("Vor der Freigabe muss mindestens eine Tätigkeit eingetragen sein."))
		if any(not (row.details or "").strip() for row in self.activities):
			frappe.throw(_("Vor der Freigabe benötigt jede Tätigkeit eine Beschreibung der Arbeiten."))
