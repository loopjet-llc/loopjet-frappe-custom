from frappe.model.document import Document

from loopjet_frappe_custom.ai_sdr.domain import compute_icp_score, icp_tier


class AISDRResearch(Document):
	def before_validate(self) -> None:
		self.calculate_score()

	def calculate_score(self) -> None:
		self.icp_score = compute_icp_score(
			self.fit_score,
			self.trigger_score,
			self.persona_score,
			self.data_quality_score,
		)
		self.icp_tier = icp_tier(self.icp_score)
