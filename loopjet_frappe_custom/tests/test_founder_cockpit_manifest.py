from __future__ import annotations

import json
from pathlib import Path

from loopjet_frappe_custom.founder_cockpit.install import _merge_desktop_layout

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "loopjet_frappe_custom"


def _manifest(doctype: str) -> dict:
	path = PACKAGE / "loopjet_custom" / "doctype" / doctype / f"{doctype}.json"
	return json.loads(path.read_text())


def test_settings_are_safe_and_quiet_by_default() -> None:
	settings = _manifest("founder_cockpit_settings")
	fields = {field["fieldname"]: field for field in settings["fields"]}

	assert settings["issingle"] == 1
	assert fields["notification_mode"]["default"] == "Off"
	assert fields["notification_mode"]["options"] == "Off\nNative ToDo"
	assert fields["daily_digest_enabled"]["default"] == "0"
	assert fields["ignored_error_methods"]["default"].startswith("Session Stopped")
	assert {permission["role"] for permission in settings["permissions"]} == {"System Manager"}


def test_acknowledgement_state_is_user_scoped_and_not_deletable_by_regular_cockpit_users() -> None:
	state = _manifest("founder_cockpit_state")
	permissions = {permission["role"]: permission for permission in state["permissions"]}

	assert permissions["Founder Cockpit User"]["read"] == 1
	assert permissions["Founder Cockpit User"]["write"] == 1
	assert permissions["Founder Cockpit User"].get("delete", 0) == 0
	assert permissions["System Manager"]["delete"] == 1


def test_page_install_and_hooks_register_rbac_workspace_and_disabled_digest_architecture() -> None:
	page = json.loads(
		(PACKAGE / "loopjet_custom" / "page" / "founder_cockpit" / "founder_cockpit.json").read_text()
	)
	workspace = json.loads(
		(PACKAGE / "loopjet_custom" / "workspace" / "founder_operations" / "founder_operations.json").read_text()
	)
	install = (PACKAGE / "founder_cockpit" / "install.py").read_text()
	hooks = (PACKAGE / "hooks.py").read_text()
	patches = (PACKAGE / "patches.txt").read_text()

	assert {row["role"] for row in page["roles"]} == {"System Manager", "Founder Cockpit User"}
	assert workspace["link_type"] == "Page"
	assert workspace["link_to"] == "founder-cockpit"
	assert {row["role"] for row in workspace["roles"]} == {"System Manager", "Founder Cockpit User"}
	assert '"link_type": "Page"' in install
	assert 'FOUNDER_COCKPIT_WORKSPACE = "Founder Operations"' in install
	assert '"link_type": "Workspace Sidebar"' in install
	assert '"desktop:home_page", "desktop"' in install
	assert '"Founder Cockpit State"' in hooks
	assert "prepare_daily_digest" in hooks
	assert "install_founder_cockpit" in patches


def test_saved_desktop_layout_keeps_existing_icons_and_adds_cockpit_once() -> None:
	original = json.dumps(
		[
			{
				"label": "Framework",
				"icon_type": "Link",
				"link_type": "Workspace Sidebar",
				"link_to": "Framework",
			}
		]
	)

	merged, changed = _merge_desktop_layout(original)
	assert changed is True
	layout = json.loads(merged)
	assert [row["label"] for row in layout] == ["Founder Cockpit", "Framework"]
	assert layout[0]["link_type"] == "Workspace Sidebar"
	assert layout[0]["link_to"] == "Founder Cockpit"
	assert layout[0]["restrict_removal"] == 1

	merged_again, changed_again = _merge_desktop_layout(merged)
	assert changed_again is False
	assert merged_again == merged


def test_cockpit_api_exposes_only_safe_page_mutations() -> None:
	api = (PACKAGE / "founder_cockpit" / "api.py").read_text()
	page = (PACKAGE / "loopjet_custom" / "page" / "founder_cockpit" / "founder_cockpit.js").read_text()

	assert api.count('@frappe.whitelist(methods=["POST"])') == 2
	assert "def acknowledge(" in api
	assert "def schedule_follow_up(" in api
	assert "submit_document" not in api
	assert "cancel_document" not in api
	assert "delete_document" not in api
	assert "frappe.sendmail" not in api
	assert "Open source" in page
	assert "Schedule follow-up" in page
	assert "Acknowledge" in page
	assert "@media (max-width: 760px)" in page
	assert "box-sizing: border-box" in page
	assert "padding: 0 24px 32px" in page
	assert '.toggleClass("is-single", cards.length === 1)' in page
	assert ".lj-cockpit-list.is-single .lj-cockpit-card" in page
	assert ".lj-cockpit-card:only-child" in page


def test_collectors_use_permission_aware_queries_and_never_return_message_or_error_payloads() -> None:
	collectors = (PACKAGE / "founder_cockpit" / "collectors.py").read_text()

	assert "frappe.get_list(" in collectors
	assert "frappe.get_all(" not in collectors
	assert '"body"' not in collectors
	assert '"description"' not in collectors
	assert '"request_headers"' not in collectors
	assert '"response_headers"' not in collectors
	assert '"output"' not in collectors
