from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class FounderCockpitState(Document):
	def validate(self) -> None:
		if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
			if self.user != frappe.session.user:
				frappe.throw(_("Cockpit state can only be saved for the current user."), frappe.PermissionError)
		if not self.acknowledged_until:
			frappe.throw(_("Acknowledged Until is required."))
