import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from loopjet_frappe_custom.ai_sdr.domain import ACTIVE_ENROLLMENT_STATUSES


class AISDREnrollment(Document):
	def before_validate(self) -> None:
		self.set_defaults()

	def validate(self) -> None:
		self.validate_unique_active_enrollment()

	def set_defaults(self) -> None:
		if self.is_new() and not self.started_at:
			self.started_at = now_datetime()
		if self.is_new() and not self.next_action_at:
			self.next_action_at = now_datetime()
		self.current_step = max(0, int(self.current_step or 0))

	def validate_unique_active_enrollment(self) -> None:
		if self.status not in ACTIVE_ENROLLMENT_STATUSES:
			return
		filters = {
			"lead": self.lead,
			"status": ["in", sorted(ACTIVE_ENROLLMENT_STATUSES)],
			"name": ["!=", self.name or ""],
		}
		if frappe.db.exists("AI SDR Enrollment", filters):
			frappe.throw(_("This lead already has an active or paused AI SDR enrollment."))
