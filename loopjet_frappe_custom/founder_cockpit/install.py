from __future__ import annotations

import json
from typing import Any

FOUNDER_COCKPIT_ROLE = "Founder Cockpit User"
FOUNDER_COCKPIT_PAGE = "founder-cockpit"
FOUNDER_COCKPIT_LABEL = "Founder Cockpit"
FOUNDER_COCKPIT_WORKSPACE = "Founder Operations"
FOUNDER_COCKPIT_ICON = "command"


def _repair_completed_setup_home_page() -> bool:
	"""Break the setup-wizard redirect loop on already configured sites."""
	import frappe
	from frappe.cache_manager import clear_defaults_cache

	current_home_page = frappe.db.get_value(
		"DefaultValue",
		{"defkey": "desktop:home_page", "parent": "__default"},
		"defvalue",
	)
	if not frappe.is_setup_complete() or current_home_page != "setup-wizard":
		return False
	frappe.db.set_default("desktop:home_page", "desktop")
	clear_defaults_cache()
	return True


def _ensure_role() -> bool:
	import frappe

	if frappe.db.exists("Role", FOUNDER_COCKPIT_ROLE):
		return False
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": FOUNDER_COCKPIT_ROLE,
			"desk_access": 1,
			"is_custom": 1,
		}
	).insert(ignore_permissions=True)
	return True


def _ensure_permissions() -> bool:
	import frappe
	from frappe.permissions import add_permission, update_permission_property

	changed = False
	for doctype, role, permissions in (
		("Founder Cockpit Settings", "System Manager", ("read", "write", "create")),
		("Founder Cockpit State", "System Manager", ("read", "write", "create", "delete", "report")),
		("Founder Cockpit State", FOUNDER_COCKPIT_ROLE, ("read", "write", "create", "report")),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
			add_permission(doctype, role, 0, "read")
			changed = True
		for permission in ("read", "write", "create", "delete", "report", "export", "share", "print", "email"):
			expected = int(permission in permissions)
			current = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": doctype, "role": role, "permlevel": 0},
				permission,
			)
			if int(current or 0) != expected:
				update_permission_property(doctype, role, 0, permission, expected)
				changed = True
	return changed


def _workspace_values() -> dict[str, Any]:
	return {
		"label": FOUNDER_COCKPIT_WORKSPACE,
		"title": FOUNDER_COCKPIT_WORKSPACE,
		"module": "Loopjet Custom",
		"app": "loopjet_frappe_custom",
		"type": "Link",
		"link_type": "Page",
		"link_to": FOUNDER_COCKPIT_PAGE,
		"icon": FOUNDER_COCKPIT_ICON,
		"public": 1,
		"is_hidden": 0,
	}


def _ensure_workspace() -> bool:
	import frappe

	changed = False
	if frappe.db.exists("Workspace", FOUNDER_COCKPIT_WORKSPACE):
		workspace = frappe.get_doc("Workspace", FOUNDER_COCKPIT_WORKSPACE)
	else:
		workspace = frappe.new_doc("Workspace")
		workspace.name = FOUNDER_COCKPIT_WORKSPACE
		changed = True
	for fieldname, value in _workspace_values().items():
		if workspace.get(fieldname) != value:
			workspace.set(fieldname, value)
			changed = True

	expected_roles = {"System Manager", FOUNDER_COCKPIT_ROLE}
	current_roles = {row.role for row in workspace.get("roles") or []}
	if current_roles != expected_roles:
		workspace.set("roles", [])
		for role in sorted(expected_roles):
			workspace.append("roles", {"role": role})
		changed = True
	if changed:
		workspace.flags.ignore_permissions = True
		workspace.flags.ignore_links = True
		workspace.save() if not workspace.is_new() else workspace.insert()
	return changed


def _sidebar_values() -> dict[str, Any]:
	return {
		"label": FOUNDER_COCKPIT_LABEL,
		"type": "Link",
		"link_type": "Page",
		"link_to": FOUNDER_COCKPIT_PAGE,
		"url": "",
		"icon": FOUNDER_COCKPIT_ICON,
	}


def _ensure_cockpit_sidebar() -> bool:
	"""Provide the dedicated native sidebar target required by Desktop Icon."""
	import frappe

	if frappe.db.exists("Workspace Sidebar", FOUNDER_COCKPIT_LABEL):
		sidebar = frappe.get_doc("Workspace Sidebar", FOUNDER_COCKPIT_LABEL)
		changed = False
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = FOUNDER_COCKPIT_LABEL
		changed = True

	for fieldname, value in {
		"header_icon": FOUNDER_COCKPIT_ICON,
		"standard": 0,
		"app": "loopjet_frappe_custom",
	}.items():
		if sidebar.get(fieldname) != value:
			sidebar.set(fieldname, value)
			changed = True

	item = next(
		(
			row
			for row in sidebar.get("items") or []
			if row.label == FOUNDER_COCKPIT_LABEL
			or (row.link_type == "Page" and row.link_to == FOUNDER_COCKPIT_PAGE)
		),
		None,
	)
	if item is None:
		sidebar.append("items", _sidebar_values())
		changed = True
	else:
		for fieldname, value in _sidebar_values().items():
			if item.get(fieldname) != value:
				item.set(fieldname, value)
				changed = True

	if changed:
		sidebar.flags.ignore_permissions = True
		previous_in_import = frappe.flags.in_import
		try:
			frappe.flags.in_import = True
			sidebar.save() if not sidebar.is_new() else sidebar.insert()
		finally:
			frappe.flags.in_import = previous_in_import
	return changed


def _ensure_desktop_icon() -> bool:
	"""Expose the cockpit as a role-restricted, top-level Desk icon."""
	import frappe

	if frappe.db.exists("Desktop Icon", FOUNDER_COCKPIT_LABEL):
		icon = frappe.get_doc("Desktop Icon", FOUNDER_COCKPIT_LABEL)
		changed = False
	else:
		icon = frappe.new_doc("Desktop Icon")
		icon.label = FOUNDER_COCKPIT_LABEL
		changed = True

	for fieldname, value in {
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": FOUNDER_COCKPIT_LABEL,
		"parent_icon": "",
		"sidebar": FOUNDER_COCKPIT_LABEL,
		"standard": 0,
		"app": "loopjet_frappe_custom",
		"icon": FOUNDER_COCKPIT_ICON,
		"hidden": 0,
		"restrict_removal": 1,
		"bg_color": "blue",
	}.items():
		if icon.get(fieldname) != value:
			icon.set(fieldname, value)
			changed = True

	expected_roles = {"System Manager", FOUNDER_COCKPIT_ROLE}
	current_roles = {row.role for row in icon.get("roles") or []}
	if current_roles != expected_roles:
		icon.set("roles", [])
		for role in sorted(expected_roles):
			icon.append("roles", {"role": role})
		changed = True

	if changed:
		icon.flags.ignore_permissions = True
		icon.save() if not icon.is_new() else icon.insert()
	return changed


def _merge_desktop_layout(layout_json: str | None) -> tuple[str | None, bool]:
	"""Keep a saved desktop layout while adding the required cockpit icon."""
	if not layout_json:
		return layout_json, False
	try:
		layout = json.loads(layout_json)
	except (TypeError, ValueError):
		return layout_json, False
	if not isinstance(layout, list):
		return layout_json, False
	if any(
		isinstance(row, dict)
		and (
			row.get("label") == FOUNDER_COCKPIT_LABEL
			or (
				row.get("link_type") == "Workspace Sidebar"
				and row.get("link_to") == FOUNDER_COCKPIT_LABEL
			)
		)
		for row in layout
	):
		return layout_json, False

	layout.insert(
		0,
		{
			"app": "loopjet_frappe_custom",
			"bg_color": "blue",
			"child_icons": [],
			"hidden": 0,
			"icon": FOUNDER_COCKPIT_ICON,
			"icon_image": None,
			"icon_type": "Link",
			"idx": 0,
			"label": FOUNDER_COCKPIT_LABEL,
			"link": None,
			"link_to": FOUNDER_COCKPIT_LABEL,
			"link_type": "Workspace Sidebar",
			"logo_url": None,
			"name": FOUNDER_COCKPIT_LABEL,
			"parent_icon": "",
			"restrict_removal": 1,
			"standard": 0,
		},
	)
	return json.dumps(layout), True


def _ensure_saved_desktop_layouts() -> bool:
	"""Add the cockpit to eligible users whose custom layout replaces boot icons."""
	import frappe
	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

	changed = False
	allowed_roles = {"System Manager", FOUNDER_COCKPIT_ROLE}
	for user in frappe.get_all("Desktop Layout", pluck="name"):
		if not allowed_roles.intersection(frappe.get_roles(user)):
			continue
		layout_json = frappe.db.get_value("Desktop Layout", user, "layout")
		merged_layout, layout_changed = _merge_desktop_layout(layout_json)
		if not layout_changed:
			continue
		frappe.db.set_value("Desktop Layout", user, "layout", merged_layout, update_modified=False)
		clear_desktop_icons_cache(user=user)
		changed = True
	return changed


def _ensure_sidebar_link() -> bool:
	import frappe

	if not frappe.db.exists("Workspace Sidebar", "Home"):
		return False
	sidebar_names = ["Home"]
	sidebar_names.extend(
		frappe.get_all("Workspace Sidebar", filters={"title": ["like", "Home-%"]}, pluck="name")
	)
	changed = False
	for sidebar_name in dict.fromkeys(sidebar_names):
		sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
		item = next(
			(
				row
				for row in sidebar.items
				if row.label == FOUNDER_COCKPIT_LABEL
				or (row.link_type == "Page" and row.link_to == FOUNDER_COCKPIT_PAGE)
			),
			None,
		)
		sidebar_changed = False
		if item is None:
			sidebar.append("items", _sidebar_values())
			sidebar_changed = True
		else:
			for fieldname, value in _sidebar_values().items():
				if item.get(fieldname) != value:
					item.set(fieldname, value)
					sidebar_changed = True
		if sidebar_changed:
			sidebar.flags.ignore_permissions = True
			previous_in_import = frappe.flags.in_import
			try:
				frappe.flags.in_import = True
				sidebar.save()
			finally:
				frappe.flags.in_import = previous_in_import
			changed = True
	return changed


def install_founder_cockpit() -> bool:
	import frappe

	if not frappe.db.exists("DocType", "Founder Cockpit Settings"):
		return False
	changed = _repair_completed_setup_home_page()
	changed = _ensure_role() or changed
	changed = _ensure_permissions() or changed
	changed = _ensure_workspace() or changed
	changed = _ensure_cockpit_sidebar() or changed
	changed = _ensure_desktop_icon() or changed
	changed = _ensure_saved_desktop_layouts() or changed
	changed = _ensure_sidebar_link() or changed
	if changed:
		frappe.cache.delete_key("desktop_icons")
		frappe.cache.delete_key("bootinfo")
		frappe.clear_cache()
	return changed
