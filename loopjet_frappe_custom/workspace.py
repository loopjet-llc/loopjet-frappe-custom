from __future__ import annotations

import json
from typing import Any

RAVEN_SHORTCUT_LABEL = "Raven Chat"
RAVEN_SHORTCUT_URL = "/raven"
RAVEN_SHORTCUT_BLOCK_ID = "loopjet-raven-chat"


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

	if "raven" not in frappe.get_installed_apps() or not frappe.db.exists("Workspace", "Home"):
		return False

	workspace = frappe.get_doc("Workspace", "Home")
	changed = False
	shortcut = next(
		(row for row in workspace.shortcuts if row.label == RAVEN_SHORTCUT_LABEL),
		None,
	)
	values = {
		"type": "URL",
		"url": RAVEN_SHORTCUT_URL,
		"link_to": "",
		"label": RAVEN_SHORTCUT_LABEL,
		"icon": "message-circle",
		"color": "#7C3AED",
	}
	if shortcut is None:
		workspace.append("shortcuts", values)
		changed = True
	else:
		for fieldname, value in values.items():
			if shortcut.get(fieldname) != value:
				shortcut.set(fieldname, value)
				changed = True

	workspace.content, layout_changed = add_raven_shortcut_to_layout(workspace.content)
	changed = changed or layout_changed
	if changed:
		workspace.flags.ignore_permissions = True
		workspace.save()
		frappe.clear_cache()
	return changed
