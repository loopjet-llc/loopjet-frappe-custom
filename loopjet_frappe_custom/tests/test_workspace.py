import json

from loopjet_frappe_custom.workspace import (
	CUSTOMER_REPORTS_SHORTCUT_BLOCK_ID,
	CUSTOMER_REPORTS_SHORTCUT_LABEL,
	RAVEN_SHORTCUT_BLOCK_ID,
	RAVEN_SHORTCUT_LABEL,
	add_customer_reports_shortcut_to_layout,
	add_raven_shortcut_to_layout,
	customer_reports_sidebar_item_values,
	raven_sidebar_item_values,
	reconcile_customer_reports_sidebar_item,
	reconcile_raven_sidebar_item,
)


def test_raven_shortcut_is_inserted_after_shortcuts_header() -> None:
	content = json.dumps(
		[
			{"id": "onboarding", "type": "onboarding", "data": {}},
			{
				"id": "header",
				"type": "header",
				"data": {"text": "<span><b>Your Shortcuts</b></span>", "col": 12},
			},
			{"id": "item", "type": "shortcut", "data": {"shortcut_name": "Item", "col": 3}},
		]
	)

	updated, changed = add_raven_shortcut_to_layout(content)
	layout = json.loads(updated)

	assert changed is True
	assert layout[2] == {
		"id": RAVEN_SHORTCUT_BLOCK_ID,
		"type": "shortcut",
		"data": {"shortcut_name": RAVEN_SHORTCUT_LABEL, "col": 3},
	}


def test_raven_shortcut_layout_update_is_idempotent() -> None:
	content, first_changed = add_raven_shortcut_to_layout("[]")
	updated, second_changed = add_raven_shortcut_to_layout(content)

	assert first_changed is True
	assert second_changed is False
	assert updated == content


def test_raven_sidebar_item_values_open_raven_directly() -> None:
	assert raven_sidebar_item_values() == {
		"label": "Raven Chat",
		"type": "Link",
		"link_type": "URL",
		"link_to": "",
		"url": "/raven",
		"icon": "message-circle",
	}


def test_raven_sidebar_item_repair_is_idempotent() -> None:
	item = {"label": "Raven", "type": "Link", "link_type": "URL", "url": "/raven"}

	assert reconcile_raven_sidebar_item(item) is True
	assert item == raven_sidebar_item_values()
	assert reconcile_raven_sidebar_item(item) is False


def test_customer_reports_shortcut_follows_raven_when_available() -> None:
	content = json.dumps(
		[
			{"id": "raven", "type": "shortcut", "data": {"shortcut_name": RAVEN_SHORTCUT_LABEL, "col": 3}},
		]
	)

	updated, changed = add_customer_reports_shortcut_to_layout(content)
	layout = json.loads(updated)

	assert changed is True
	assert layout[1] == {
		"id": CUSTOMER_REPORTS_SHORTCUT_BLOCK_ID,
		"type": "shortcut",
		"data": {"shortcut_name": CUSTOMER_REPORTS_SHORTCUT_LABEL, "col": 3},
	}


def test_customer_reports_shortcut_layout_update_is_idempotent() -> None:
	content, first_changed = add_customer_reports_shortcut_to_layout("[]")
	updated, second_changed = add_customer_reports_shortcut_to_layout(content)

	assert first_changed is True
	assert second_changed is False
	assert updated == content


def test_customer_reports_sidebar_item_repair_is_idempotent() -> None:
	item = {"label": "Berichte", "type": "Link", "link_type": "URL", "url": "/reports"}

	assert reconcile_customer_reports_sidebar_item(item) is True
	assert item == customer_reports_sidebar_item_values()
	assert reconcile_customer_reports_sidebar_item(item) is False
