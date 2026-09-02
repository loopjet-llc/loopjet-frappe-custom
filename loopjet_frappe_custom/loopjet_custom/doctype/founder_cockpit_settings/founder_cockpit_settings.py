from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class FounderCockpitSettings(Document):
	def validate(self) -> None:
		self._validate_scores()
		self._validate_limits()
		self._validate_digest()

	def _validate_scores(self) -> None:
		self.critical_priority_score = max(1, min(int(self.critical_priority_score or 90), 100))
		self.high_priority_score = max(1, min(int(self.high_priority_score or 75), 100))
		self.medium_priority_score = max(1, min(int(self.medium_priority_score or 50), 100))
		if not self.critical_priority_score > self.high_priority_score > self.medium_priority_score:
			frappe.throw(_("Priority thresholds must descend from Critical to High to Medium."))
		for fieldname in (
			"sales_base_score",
			"clients_base_score",
			"finance_base_score",
			"operations_base_score",
			"team_base_score",
		):
			self.set(fieldname, max(1, min(int(self.get(fieldname) or 50), 100)))

	def _validate_limits(self) -> None:
		bounds = {
			"age_boost_days": (1, 365),
			"max_cards": (10, 250),
			"max_records_per_source": (20, 500),
			"lead_stale_days": (1, 90),
			"deal_stale_days": (1, 180),
			"quotation_action_window_days": (0, 60),
			"operational_lookback_hours": (1, 336),
			"repeated_error_threshold": (1, 100),
			"acknowledge_hours": (1, 720),
		}
		for fieldname, (minimum, maximum) in bounds.items():
			self.set(fieldname, max(minimum, min(int(self.get(fieldname) or minimum), maximum)))

	def _validate_digest(self) -> None:
		digest_hour = 8 if self.daily_digest_hour in (None, "") else int(self.daily_digest_hour)
		self.daily_digest_hour = max(0, min(digest_hour, 23))
		if self.daily_digest_enabled:
			if self.notification_mode != "Native ToDo":
				frappe.throw(_("Daily digest requires the Native ToDo notification mode."))
			if not self.digest_user:
				frappe.throw(_("Digest User is required when the daily digest is enabled."))
			if not frappe.db.get_value("User", self.digest_user, "enabled"):
				frappe.throw(_("Digest User must be enabled."))
