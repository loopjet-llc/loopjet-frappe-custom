from __future__ import annotations

from loopjet_frappe_custom.ai_sdr.install import (
	AI_SDR_AGENT_ROLE,
	AI_SDR_MANAGER_ROLE,
	AI_SDR_USER_ROLE,
)


def has_sdr_access(user: str | None = None, *, manager: bool = False) -> bool:
	import frappe

	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if "System Manager" in roles or user == "Administrator":
		return True
	if manager:
		return AI_SDR_MANAGER_ROLE in roles
	return bool(roles.intersection({AI_SDR_USER_ROLE, AI_SDR_MANAGER_ROLE}))


def require_sdr_access(*, manager: bool = False) -> None:
	import frappe
	from frappe import _

	if not has_sdr_access(manager=manager):
		frappe.throw(
			_("AI SDR Manager permission is required." if manager else "AI SDR access is required."),
			frappe.PermissionError,
		)


def has_agent_api_access(user: str | None = None) -> bool:
	"""Authorize the bounded machine API without granting generic CRM access."""
	import frappe

	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	return bool(
		user == "Administrator"
		or "System Manager" in roles
		or AI_SDR_MANAGER_ROLE in roles
		or AI_SDR_AGENT_ROLE in roles
	)


def require_agent_api_access() -> None:
	import frappe
	from frappe import _

	if not has_agent_api_access():
		frappe.throw(_("AI SDR Agent permission is required."), frappe.PermissionError)


def _owned_query_condition(doctype: str, user: str | None = None) -> str:
	import frappe

	user = user or frappe.session.user
	if has_sdr_access(user, manager=True):
		return ""
	if not has_sdr_access(user):
		return "1=0"
	escaped_user = frappe.db.escape(user)
	return f"(`tab{doctype}`.`owner` = {escaped_user} or `tab{doctype}`.`assigned_to` = {escaped_user})"


def research_query_condition(user: str | None = None) -> str:
	return _owned_query_condition("AI SDR Research", user)


def enrollment_query_condition(user: str | None = None) -> str:
	return _owned_query_condition("AI SDR Enrollment", user)


def activity_query_condition(user: str | None = None) -> str:
	return _owned_query_condition("AI SDR Activity", user)


def has_owned_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	import frappe

	user = user or frappe.session.user
	if has_sdr_access(user, manager=True):
		return True
	if not has_sdr_access(user):
		return False
	return doc.owner == user or doc.get("assigned_to") == user
