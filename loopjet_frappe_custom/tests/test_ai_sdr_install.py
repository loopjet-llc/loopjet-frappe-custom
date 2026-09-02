from __future__ import annotations

import json
from pathlib import Path

from loopjet_frappe_custom.ai_sdr.install import (
	AI_SDR_AGENT_ROLE,
	AI_SDR_SHORTCUT_BLOCK_ID,
	AI_SDR_SHORTCUT_LABEL,
	_lead_form_script,
	add_ai_sdr_shortcut_to_layout,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "loopjet_frappe_custom"


def test_crm_workspace_shortcut_is_inserted_after_portal() -> None:
	content = json.dumps(
		[
			{
				"id": "portal",
				"type": "shortcut",
				"data": {"shortcut_name": "CRM Portal Page", "col": 3},
			},
			{
				"id": "leads",
				"type": "shortcut",
				"data": {"shortcut_name": "Leads", "col": 3},
			},
		]
	)

	updated, changed = add_ai_sdr_shortcut_to_layout(content)
	layout = json.loads(updated)

	assert changed is True
	assert layout[1] == {
		"id": AI_SDR_SHORTCUT_BLOCK_ID,
		"type": "shortcut",
		"data": {"shortcut_name": AI_SDR_SHORTCUT_LABEL, "col": 3},
	}


def test_crm_workspace_shortcut_install_is_idempotent() -> None:
	content, first_changed = add_ai_sdr_shortcut_to_layout("[]")
	updated, second_changed = add_ai_sdr_shortcut_to_layout(content)

	assert first_changed is True
	assert second_changed is False
	assert updated == content


def test_ai_sdr_doctype_manifests_are_present_and_safe_by_default() -> None:
	doctype_root = PACKAGE / "loopjet_custom" / "doctype"
	expected = {
		"ai_sdr_settings",
		"ai_sdr_sequence",
		"ai_sdr_sequence_step",
		"ai_sdr_research",
		"ai_sdr_enrollment",
		"ai_sdr_activity",
		"ai_sdr_suppression",
	}
	assert expected.issubset({path.name for path in doctype_root.iterdir() if path.is_dir()})

	settings = json.loads((doctype_root / "ai_sdr_settings" / "ai_sdr_settings.json").read_text())
	fields = {field["fieldname"]: field for field in settings["fields"]}
	assert fields["ai_enabled"]["default"] == "0"
	assert fields["sending_enabled"]["default"] == "0"
	assert fields["academy_manual_sending_enabled"]["default"] == "0"
	assert fields["academy_outbound_secret"]["fieldtype"] == "Password"
	assert fields["max_daily_emails"]["default"] == "25"
	assert fields["ai_provider"]["default"] == "OpenRouter"
	assert fields["ai_base_url"]["default"] == "https://openrouter.ai/api/v1"
	assert fields["connection_status"]["default"] == "Not Tested"
	assert fields["connection_status"]["read_only"] == 1


def test_ai_connection_requires_a_real_provider_probe() -> None:
	api = (PACKAGE / "ai_sdr" / "api.py").read_text()
	services = (PACKAGE / "ai_sdr" / "services.py").read_text()
	settings_script = (
		PACKAGE
		/ "loopjet_custom"
		/ "doctype"
		/ "ai_sdr_settings"
		/ "ai_sdr_settings.js"
	).read_text()

	assert "test_ai_connection_service()" in api
	assert '_record_connection_state("Connected")' in services
	assert "complete_json(" in services
	assert "Test {0} Connection" in settings_script


def test_all_outbound_sequence_steps_require_human_approval() -> None:
	controller = (
		PACKAGE / "loopjet_custom" / "doctype" / "ai_sdr_sequence" / "ai_sdr_sequence.py"
	).read_text()
	step_manifest = json.loads(
		(
			PACKAGE / "loopjet_custom" / "doctype" / "ai_sdr_sequence_step" / "ai_sdr_sequence_step.json"
		).read_text()
	)
	fields = {field["fieldname"]: field for field in step_manifest["fields"]}

	assert fields["requires_approval"]["default"] == "1"
	assert fields["requires_approval"]["read_only"] == 1
	assert "step.requires_approval = 1" in controller


def test_hooks_and_patch_register_ai_sdr() -> None:
	hooks = (PACKAGE / "hooks.py").read_text()
	patches = (PACKAGE / "patches.txt").read_text()

	assert "process_due_enrollments" in hooks
	assert "handle_received_communication" in hooks
	assert "stop_enrollments_for_deal" in hooks
	assert "loopjet_frappe_custom.patches.v0_2.install_ai_sdr" in patches
	assert "loopjet_frappe_custom.patches.v0_3.install_outbound_agent_api" in patches


def test_outbound_agent_api_is_bounded_and_post_protected() -> None:
	installer = (PACKAGE / "ai_sdr" / "install.py").read_text()
	agent_api = (PACKAGE / "ai_sdr" / "agent_api.py").read_text()

	assert AI_SDR_AGENT_ROLE == "AI SDR Agent"
	assert "desk_access = int(role_name != AI_SDR_AGENT_ROLE)" in installer
	for fieldname in (
		"ai_sdr_company_domain",
		"ai_sdr_research_notes",
		"ai_sdr_sales_reason",
		"ai_sdr_research_agent",
		"ai_sdr_call_status",
		"ai_sdr_next_call_at",
	):
		assert fieldname in installer
	for method in (
		"search_lead",
		"create_lead",
		"update_lead",
		"add_contact_person",
		"add_call_note",
		"get_next_call_list",
		"get_academy_outbound_context",
		"get_academy_outbound_limits",
		"record_academy_outbound_event",
	):
		assert f"def {method}(" in agent_api
	assert agent_api.count('@frappe.whitelist(methods=["POST"])') == 6
	assert agent_api.count('@frappe.whitelist(methods=["GET"])') == 4
	assert 'kwargs.pop("cmd", None)' in agent_api
	assert "require_agent_api_access()" in agent_api
	assert 'ACADEMY_TAG = "Learnlayer Academy"' in agent_api
	assert "ACADEMY_OUTBOUND_EVENT_PREFIX" in agent_api
	assert '"diagnostic_received"' in agent_api
	assert "frappe.sendmail" not in agent_api


def test_ai_sdr_page_never_sends_without_a_confirmation() -> None:
	page_script = (PACKAGE / "loopjet_custom" / "page" / "ai_sdr" / "ai_sdr.js").read_text()

	assert 'action === "send"' in page_script
	assert "await this.confirm" in page_script
	assert "send_activity" in page_script


def test_research_form_exposes_manager_only_ai_analysis_action() -> None:
	research_script = (
		PACKAGE
		/ "loopjet_custom"
		/ "doctype"
		/ "ai_sdr_research"
		/ "ai_sdr_research.js"
	).read_text()

	assert "AI SDR Manager" in research_script
	assert "Analyze with AI" in research_script
	assert "loopjet_frappe_custom.ai_sdr.api.analyze_research" in research_script


def test_crm_lead_actions_support_drafts_and_manager_enrollment() -> None:
	script = _lead_form_script()

	assert "Prepare AI Outreach" in script
	assert "formDialog" in script
	assert "get_access_context" in script
	assert "Enroll in AI SDR Sequence" in script
	assert "loopjet_frappe_custom.ai_sdr.api.enroll" in script
	assert "Send LearnLayer Academy Email" in script
	assert "Learnlayer Academy" in script
	assert "Ahmad El-Ali signature" in script
	assert "Ahmad Alali" not in script
	assert "window.confirm" in script
	assert "loopjet_frappe_custom.ai_sdr.api.send_academy_email" in script


def test_academy_manual_email_uses_the_protected_edge_sender_and_audits_provider_outcomes() -> None:
	api = (PACKAGE / "ai_sdr" / "api.py").read_text()
	services = (PACKAGE / "ai_sdr" / "services.py").read_text()
	agent_api = (PACKAGE / "ai_sdr" / "agent_api.py").read_text()
	activity_manifest = json.loads(
		(PACKAGE / "loopjet_custom" / "doctype" / "ai_sdr_activity" / "ai_sdr_activity.json").read_text()
	)
	fields = {field["fieldname"]: field for field in activity_manifest["fields"]}

	assert 'def send_academy_email(' in api
	assert "require_sdr_access(manager=True)" in api
	assert '"mode": "manual"' in services
	assert '"x-academy-outbound-secret": secret' in services
	assert "activity.flags.ai_sdr_approval_action = True" in services
	assert 'frappe.db.commit()' in services
	assert 'frappe.sendmail' not in services[
		services.index("def send_academy_manual_email"):services.index("def send_academy_internal_preview")
	]
	assert "def send_academy_internal_preview" in services
	assert "def send_loopjet_internal_preview" in services
	assert '"internalPreview": internal_preview' in services
	assert "LOOPJET_INTERNAL_PREVIEW_PROMPT" in services
	assert "_update_academy_manual_activity" in agent_api
	assert fields["provider_message_id"]["read_only"] == 1
	assert fields["provider_outcome"]["read_only"] == 1
	assert "Accepted" in fields["status"]["options"]


def test_standard_crm_form_script_updates_without_a_document_save() -> None:
	installer = (PACKAGE / "ai_sdr" / "install.py").read_text()

	assert 'frappe.db.set_value("CRM Form Script", LEAD_FORM_SCRIPT_NAME, updates)' in installer
