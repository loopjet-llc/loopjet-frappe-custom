from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from loopjet_frappe_custom.customer_reports import is_customer_report_pdf


class LoopjetCustomerReport(Document):
	def validate(self) -> None:
		self.validate_report_file()

	def validate_report_file(self) -> None:
		if self.report_file and not is_customer_report_pdf(self.report_file):
			frappe.throw(_("Bitte einen PDF-Bericht anhängen."))
