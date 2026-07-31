from __future__ import annotations

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


class AISDRSettings(Document):
	def validate(self) -> None:
		self.reset_connection_status_if_credentials_changed()
		self.validate_ai_configuration()
		self.validate_limits()

	def reset_connection_status_if_credentials_changed(self) -> None:
		if self.is_new():
			self.connection_status = self.connection_status or "Not Tested"
			return
		fields = ("ai_provider", "ai_base_url", "ai_model", "ai_api_key")
		if any(self.has_value_changed(fieldname) for fieldname in fields):
			self.connection_status = "Not Tested"
			self.last_connection_test_at = None
			self.last_connection_error = ""

	def validate_ai_configuration(self) -> None:
		if self.ai_base_url:
			parsed = urlparse(self.ai_base_url)
			is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
			if parsed.scheme != "https" and not (frappe.conf.developer_mode and is_local):
				frappe.throw(_("AI Base URL must use HTTPS outside local development."))
		if self.ai_provider == "OpenRouter" and self.ai_base_url:
			if self.ai_base_url.rstrip("/") != "https://openrouter.ai/api/v1":
				frappe.throw(
					_("OpenRouter must use the base URL https://openrouter.ai/api/v1.")
				)
		if self.ai_enabled:
			if not self.ai_base_url or not self.ai_model:
				frappe.throw(_("AI Base URL and AI Model are required when AI generation is enabled."))
			if not self.get_password("ai_api_key", raise_exception=False):
				frappe.throw(_("AI API Key is required when AI generation is enabled."))
			if self.connection_status != "Connected":
				frappe.throw(
					_("Test the AI connection successfully before enabling AI generation.")
				)

	def validate_limits(self) -> None:
		self.max_actions_per_run = max(1, min(int(self.max_actions_per_run or 1), 100))
		self.max_daily_emails = max(1, min(int(self.max_daily_emails or 1), 1000))
		self.ai_timeout_seconds = max(10, min(int(self.ai_timeout_seconds or 60), 180))
