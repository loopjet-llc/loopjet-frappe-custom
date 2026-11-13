from __future__ import annotations

from loopjet_frappe_custom.founder_cockpit.domain import roles_allow_cockpit


def has_cockpit_access(user: str | None = None) -> bool:
	import frappe

	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	return roles_allow_cockpit(roles, user)


def require_cockpit_access(*, manager: bool = False) -> None:
	import frappe
	from frappe import _

	if manager:
		allowed = roles_allow_cockpit({"System Manager"} if "System Manager" in frappe.get_roles() else set(), frappe.session.user)
	else:
		allowed = has_cockpit_access()
	if not allowed:
		frappe.throw(
			_("System Manager permission is required." if manager else "Founder Cockpit access is required."),
			frappe.PermissionError,
		)


def state_query_condition(user: str | None = None) -> str:
	import frappe

	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	if not has_cockpit_access(user):
		return "1=0"
	escaped_user = frappe.db.escape(user)
	return f"`tabFounder Cockpit State`.`user` = {escaped_user}"


def has_owned_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	import frappe

	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	return has_cockpit_access(user) and doc.user == user
