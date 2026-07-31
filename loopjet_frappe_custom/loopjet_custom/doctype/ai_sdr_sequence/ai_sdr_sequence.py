import frappe
from frappe import _
from frappe.model.document import Document


class AISDRSequence(Document):
	def validate(self) -> None:
		self.validate_steps()

	def validate_steps(self) -> None:
		if not self.steps:
			frappe.throw(_("At least one sequence step is required."))
		for index, step in enumerate(self.steps, start=1):
			step.idx = index
			step.delay_days = max(0, int(step.delay_days or 0))
			step.requires_approval = 1
