import frappe
from frappe import _
from frappe.model.document import Document

from loopjet_frappe_custom.ai_sdr.domain import normalize_suppression_key


class AISDRSuppression(Document):
	def before_validate(self) -> None:
		self.normalize_key()

	def validate(self) -> None:
		self.validate_key()

	def normalize_key(self) -> None:
		self.suppression_key = normalize_suppression_key(self.suppression_type, self.suppression_key)
		self.deduplication_key = f"{self.suppression_type}:{self.suppression_key.casefold()}"

	def validate_key(self) -> None:
		if not self.suppression_key:
			frappe.throw(_("Suppression Key is required."))
