from __future__ import annotations

import frappe

CUSTOMER_PORTAL_HOME = "helpdesk/my-tickets"
HELPDESK_HOME = "helpdesk"


def get_website_user_home_page(user: str) -> str:
	"""Send customers to the Helpdesk customer portal."""
	user_type = frappe.db.get_value("User", user, "user_type")
	return CUSTOMER_PORTAL_HOME if user_type == "Website User" else HELPDESK_HOME


def install_ticket_portal() -> None:
	"""Keep the public portal ticket-only and provision internal Helpdesk agents."""
	if "helpdesk" not in frappe.get_installed_apps():
		return

	_set_customer_portal_home()
	_disable_legacy_customer_portal_items()
	_provision_internal_agents()


def _set_customer_portal_home() -> None:
	if not frappe.db.exists("DocType", "Portal Settings"):
		return

	settings = frappe.get_single("Portal Settings")
	if settings.default_portal_home == f"/{CUSTOMER_PORTAL_HOME}":
		return

	settings.default_portal_home = f"/{CUSTOMER_PORTAL_HOME}"
	settings.save(ignore_permissions=True)


def _disable_legacy_customer_portal_items() -> None:
	if not frappe.db.exists("DocType", "Portal Menu Item"):
		return

	for item_name in frappe.get_all(
		"Portal Menu Item",
		filters={"role": "Customer", "enabled": 1},
		pluck="name",
	):
		frappe.db.set_value("Portal Menu Item", item_name, "enabled", 0, update_modified=False)


def _provision_internal_agents() -> None:
	if not frappe.db.exists("DocType", "HD Agent"):
		return

	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User"},
		fields=["name", "full_name", "user_image"],
	)
	for user in users:
		if frappe.db.exists("HD Agent", user.name):
			continue

		frappe.get_doc(
			{
				"doctype": "HD Agent",
				"user": user.name,
				"agent_name": user.full_name or user.name,
				"user_image": user.user_image,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
