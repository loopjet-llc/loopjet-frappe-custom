from __future__ import annotations

import json
from typing import Any

RAVEN_SHORTCUT_LABEL = "Raven Chat"
RAVEN_SHORTCUT_URL = "/raven"
RAVEN_SHORTCUT_BLOCK_ID = "loopjet-raven-chat"
RAVEN_SIDEBAR_ICON = "message-circle"


def raven_sidebar_item_values() -> dict[str, Any]:
	return {
		"label": RAVEN_SHORTCUT_LABEL,
		"type": "Link",
		"link_type": "URL",
		"link_to": "",
		"url": RAVEN_SHORTCUT_URL,
		"icon": RAVEN_SIDEBAR_ICON,
	}


def reconcile_raven_sidebar_item(item: Any) -> bool:
	"""Repair an existing Raven sidebar row and report whether it changed."""
	changed = False
	for fieldname, value in raven_sidebar_item_values().items():
		if item.get(fieldname) == value:
			continue
		if hasattr(item, "set"):
			item.set(fieldname, value)
		else:
			item[fieldname] = value
		changed = True
	return changed


def add_raven_shortcut_to_layout(content: str) -> tuple[str, bool]:
	"""Add the Raven shortcut block to a Workspace layout once."""
	layout: list[dict[str, Any]] = json.loads(content or "[]")
	if any(
		block.get("type") == "shortcut" and block.get("data", {}).get("shortcut_name") == RAVEN_SHORTCUT_LABEL
		for block in layout
	):
		return content, False

	block = {
		"id": RAVEN_SHORTCUT_BLOCK_ID,
		"type": "shortcut",
		"data": {"shortcut_name": RAVEN_SHORTCUT_LABEL, "col": 3},
	}
	insert_at = next(
		(
			index + 1
			for index, item in enumerate(layout)
			if item.get("type") == "header" and "Your Shortcuts" in item.get("data", {}).get("text", "")
		),
		len(layout),
	)
	layout.insert(insert_at, block)
	return json.dumps(layout, separators=(",", ":")), True


def install_raven_home_shortcut() -> bool:
	"""Expose Raven chat directly in the ERPNext Home workspace."""
	import frappe

	if "raven" not in frappe.get_installed_apps():
		return False

	changed = False
	if frappe.db.exists("Workspace", "Home"):
		workspace = frappe.get_doc("Workspace", "Home")
		shortcut = next(
			(row for row in workspace.shortcuts if row.label == RAVEN_SHORTCUT_LABEL),
			None,
		)
		values = {
			"type": "URL",
			"url": RAVEN_SHORTCUT_URL,
			"link_to": "",
			"label": RAVEN_SHORTCUT_LABEL,
			"icon": RAVEN_SIDEBAR_ICON,
			"color": "#7C3AED",
		}
		workspace_changed = False
		if shortcut is None:
			workspace.append("shortcuts", values)
			workspace_changed = True
		else:
			for fieldname, value in values.items():
				if shortcut.get(fieldname) != value:
					shortcut.set(fieldname, value)
					workspace_changed = True

		workspace.content, layout_changed = add_raven_shortcut_to_layout(workspace.content)
		workspace_changed = workspace_changed or layout_changed
		if workspace_changed:
			workspace.flags.ignore_permissions = True
			workspace.save()
			changed = True

	changed = install_raven_home_sidebar_link() or changed
	if changed:
		frappe.clear_cache()
	return changed


def install_raven_home_sidebar_link() -> bool:
	"""Add Raven to Frappe v16's dedicated Home sidebar, including user copies."""
	import frappe

	if not frappe.db.exists("Workspace Sidebar", "Home"):
		return False

	sidebar_names = ["Home"]
	sidebar_names.extend(
		frappe.get_all(
			"Workspace Sidebar",
			filters={"title": ["like", "Home-%"]},
			pluck="name",
		)
	)
	changed = False
	for sidebar_name in dict.fromkeys(sidebar_names):
		sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
		item = next(
			(
				row
				for row in sidebar.items
				if row.label == RAVEN_SHORTCUT_LABEL
				or (row.link_type == "URL" and row.url == RAVEN_SHORTCUT_URL)
			),
			None,
		)
		sidebar_changed = False
		if item is None:
			sidebar.append("items", raven_sidebar_item_values())
			sidebar_changed = True
		else:
			sidebar_changed = reconcile_raven_sidebar_item(item)

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
