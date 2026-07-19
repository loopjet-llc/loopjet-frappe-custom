import json

from loopjet_frappe_custom.workspace import (
	RAVEN_SHORTCUT_BLOCK_ID,
	RAVEN_SHORTCUT_LABEL,
	add_raven_shortcut_to_layout,
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
