from __future__ import annotations

import json
from typing import Any

AI_SDR_USER_ROLE = "AI SDR User"
AI_SDR_MANAGER_ROLE = "AI SDR Manager"
AI_SDR_AGENT_ROLE = "AI SDR Agent"
AI_SDR_PAGE_URL = "/app/ai-sdr"
AI_SDR_SHORTCUT_LABEL = "AI SDR"
AI_SDR_SHORTCUT_BLOCK_ID = "loopjet-ai-sdr"

AI_SDR_DOCTYPES = (
	"AI SDR Research",
	"AI SDR Sequence",
	"AI SDR Enrollment",
	"AI SDR Activity",
	"AI SDR Suppression",
	"AI SDR Settings",
)

USER_PERMISSIONS = {
	"AI SDR Research": ("read", "write", "create", "report"),
	"AI SDR Sequence": ("read", "report"),
	"AI SDR Enrollment": ("read", "write", "create", "report"),
	"AI SDR Activity": ("read", "write", "create", "report"),
	"AI SDR Suppression": ("read", "report"),
}

MANAGER_PERMISSIONS = {
	doctype: ("read", "write", "create", "delete", "report", "export", "share", "print", "email")
	for doctype in AI_SDR_DOCTYPES
}

LEAD_FORM_SCRIPT_NAME = "Loopjet AI SDR Lead Actions"


def add_ai_sdr_shortcut_to_layout(content: str) -> tuple[str, bool]:
	layout: list[dict[str, Any]] = json.loads(content or "[]")
	if any(
		block.get("type") == "shortcut"
		and block.get("data", {}).get("shortcut_name") == AI_SDR_SHORTCUT_LABEL
		for block in layout
	):
		return content, False

	block = {
		"id": AI_SDR_SHORTCUT_BLOCK_ID,
		"type": "shortcut",
		"data": {"shortcut_name": AI_SDR_SHORTCUT_LABEL, "col": 3},
	}
	insert_at = next(
		(
			index + 1
			for index, item in enumerate(layout)
			if item.get("type") == "shortcut"
			and item.get("data", {}).get("shortcut_name") == "CRM Portal Page"
		),
		len(layout),
	)
	layout.insert(insert_at, block)
	return json.dumps(layout, separators=(",", ":")), True


def install_ai_sdr() -> bool:
	"""Install CRM-only AI SDR integration without affecting non-CRM sites."""
	import frappe

	if "crm" not in frappe.get_installed_apps() or not frappe.db.exists("DocType", "CRM Lead"):
		return False

	ensure_roles()
	ensure_permissions()
	ensure_crm_custom_fields()
	ensure_crm_form_script()
	ensure_crm_workspace_shortcut()
	ensure_starter_sequence()
	frappe.clear_cache()
	return True


def ensure_roles() -> None:
	import frappe

	for role_name in (AI_SDR_USER_ROLE, AI_SDR_MANAGER_ROLE, AI_SDR_AGENT_ROLE):
		desk_access = int(role_name != AI_SDR_AGENT_ROLE)
		if frappe.db.exists("Role", role_name):
			if frappe.db.get_value("Role", role_name, "desk_access") != desk_access:
				frappe.db.set_value("Role", role_name, "desk_access", desk_access)
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				# The agent role authorizes only the bounded whitelisted API. It
				# deliberately grants no generic CRM DocType permissions or Desk.
				"desk_access": desk_access,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)


def _ensure_role_permissions(doctype: str, role: str, permissions: tuple[str, ...]) -> None:
	import frappe
	from frappe.permissions import add_permission, update_permission_property

	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		add_permission(doctype, role, 0, "read")
	for permission in (
		"read",
		"write",
		"create",
		"delete",
		"report",
		"export",
		"share",
		"print",
		"email",
	):
		update_permission_property(doctype, role, 0, permission, int(permission in permissions))


def ensure_permissions() -> None:
	import frappe

	for doctype, permissions in USER_PERMISSIONS.items():
		if frappe.db.exists("DocType", doctype):
			_ensure_role_permissions(doctype, AI_SDR_USER_ROLE, permissions)
	for doctype, permissions in MANAGER_PERMISSIONS.items():
		if frappe.db.exists("DocType", doctype):
			_ensure_role_permissions(doctype, AI_SDR_MANAGER_ROLE, permissions)


def ensure_crm_custom_fields() -> None:
	import frappe
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	custom_fields = {
		"CRM Lead": [
			{
				"fieldname": "ai_sdr_section",
				"fieldtype": "Section Break",
				"label": "AI SDR",
				"insert_after": "source",
				"collapsible": 1,
			},
			{
				"fieldname": "ai_sdr_organization",
				"fieldtype": "Link",
				"label": "Target Organization",
				"options": "CRM Organization",
				"insert_after": "ai_sdr_section",
			},
			{
				"fieldname": "ai_sdr_linkedin_url",
				"fieldtype": "Data",
				"label": "LinkedIn Profile URL",
				"insert_after": "ai_sdr_organization",
			},
			{
				"fieldname": "ai_sdr_persona",
				"fieldtype": "Select",
				"label": "Buyer Persona",
				"options": "\nExecutive\nHR / People\nLearning & Development\nOperations\nIT / Technical\nProcurement\nOther",
				"insert_after": "ai_sdr_linkedin_url",
			},
			{
				"fieldname": "ai_sdr_language",
				"fieldtype": "Select",
				"label": "Preferred Outreach Language",
				"options": "\nEnglish\nGerman",
				"insert_after": "ai_sdr_persona",
			},
			{
				"fieldname": "ai_sdr_priority",
				"fieldtype": "Select",
				"label": "Outreach Priority",
				"options": "\nLow\nMedium\nHigh",
				"insert_after": "ai_sdr_language",
			},
			{
				"fieldname": "ai_sdr_state",
				"fieldtype": "Select",
				"label": "AI SDR State",
				"options": "\nNew\nResearching\nReady\nContacting\nReplied\nNurture\nStopped",
				"insert_after": "ai_sdr_priority",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_is_company_lead",
				"fieldtype": "Check",
				"label": "Company Lead (Contact Not Identified)",
				"insert_after": "ai_sdr_state",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_call_status",
				"fieldtype": "Select",
				"label": "Outbound Call Status",
				"options": "\nNew\nResearched\nReceptionist\nContact Identified\nNo Answer\nConnected\nFollow-up\nQualified\nRejected",
				"insert_after": "ai_sdr_is_company_lead",
			},
			{
				"fieldname": "ai_sdr_last_call_outcome",
				"fieldtype": "Small Text",
				"label": "Last Call Outcome",
				"insert_after": "ai_sdr_call_status",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_last_call_at",
				"fieldtype": "Datetime",
				"label": "Last Call At",
				"insert_after": "ai_sdr_last_call_outcome",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_next_call_at",
				"fieldtype": "Datetime",
				"label": "Next Call At",
				"insert_after": "ai_sdr_last_call_at",
			},
			{
				"fieldname": "ai_sdr_do_not_contact",
				"fieldtype": "Check",
				"label": "Do Not Contact",
				"insert_after": "ai_sdr_next_call_at",
			},
			{
				"fieldname": "ai_sdr_last_contacted_at",
				"fieldtype": "Datetime",
				"label": "Last Contacted At",
				"insert_after": "ai_sdr_do_not_contact",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_next_action_at",
				"fieldtype": "Datetime",
				"label": "Next SDR Action At",
				"insert_after": "ai_sdr_last_contacted_at",
				"read_only": 1,
			},
		],
		"CRM Organization": [
			{
				"fieldname": "ai_sdr_section",
				"fieldtype": "Section Break",
				"label": "AI SDR",
				"insert_after": "exchange_rate",
				"collapsible": 1,
			},
			{
				"fieldname": "ai_sdr_company_domain",
				"fieldtype": "Data",
				"label": "Company Domain",
				"insert_after": "ai_sdr_section",
				"unique": 1,
			},
			{
				"fieldname": "ai_sdr_linkedin_url",
				"fieldtype": "Data",
				"label": "LinkedIn Company URL",
				"insert_after": "ai_sdr_company_domain",
			},
			{
				"fieldname": "ai_sdr_phone",
				"fieldtype": "Data",
				"label": "Main Phone",
				"options": "Phone",
				"insert_after": "ai_sdr_linkedin_url",
			},
			{
				"fieldname": "ai_sdr_country",
				"fieldtype": "Link",
				"label": "Country",
				"options": "Country",
				"insert_after": "ai_sdr_phone",
			},
			{
				"fieldname": "ai_sdr_research_notes",
				"fieldtype": "Long Text",
				"label": "Research Notes",
				"insert_after": "ai_sdr_country",
			},
			{
				"fieldname": "ai_sdr_sales_reason",
				"fieldtype": "Text Editor",
				"label": "Sales Reason",
				"insert_after": "ai_sdr_research_notes",
			},
			{
				"fieldname": "ai_sdr_research_agent",
				"fieldtype": "Link",
				"label": "Research Agent",
				"options": "User",
				"insert_after": "ai_sdr_sales_reason",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_research_status",
				"fieldtype": "Select",
				"label": "Research Status",
				"options": "\nDraft\nReady for Analysis\nAnalyzing\nReady\nStale\nRejected\nFailed",
				"insert_after": "ai_sdr_research_agent",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_icp_score",
				"fieldtype": "Int",
				"label": "ICP Score",
				"insert_after": "ai_sdr_research_status",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_icp_tier",
				"fieldtype": "Select",
				"label": "ICP Tier",
				"options": "\nA\nB\nC\nD",
				"insert_after": "ai_sdr_icp_score",
				"read_only": 1,
			},
			{
				"fieldname": "ai_sdr_last_researched_at",
				"fieldtype": "Datetime",
				"label": "Last Researched At",
				"insert_after": "ai_sdr_icp_tier",
				"read_only": 1,
			},
		],
	}
	create_custom_fields(custom_fields, ignore_validate=True)
	frappe.clear_cache(doctype="CRM Lead")
	frappe.clear_cache(doctype="CRM Organization")


def _lead_form_script() -> str:
	return """class CRMLead {
	onLoad() {
		if (this.doc.__newDocument) return
		call("loopjet_frappe_custom.ai_sdr.api.get_access_context").then((access) => {
			this.setAISDRActions(access)
		}).catch(() => {})
	}
	setAISDRActions(access) {
		this.actions.push({
			label: __("Prepare AI Outreach"),
			icon: "zap",
			onClick: () => this.prepareOutreach()
		})
		this.actions.push({
			label: __("Open AI SDR"),
			onClick: () => window.open(`/app/ai-sdr?lead=${encodeURIComponent(this.doc.name)}`, "_blank")
		})
		if (access.can_manage) {
			this.actions.push({
				label: __("Enroll in AI SDR Sequence"),
				onClick: () => this.enrollInSequence()
			})
		}
	}
	async prepareOutreach() {
		const values = await this.formDialog({
			title: __("Prepare AI Outreach"),
			fields: [
				{
					fieldname: "channel",
					fieldtype: "Select",
					label: __("Channel"),
					options: "Email\\nLinkedIn\\nCall",
					default: "Email",
					reqd: 1
				},
				{
					fieldname: "instructions",
					fieldtype: "Small Text",
					label: __("Drafting Instructions")
				}
			],
			required: ["channel"],
			submitLabel: __("Create Draft"),
			cancelLabel: __("Cancel")
		})
		if (!values) return
		call(
			"loopjet_frappe_custom.ai_sdr.api.prepare_lead",
			{ lead: this.doc.name, channel: values.channel, instructions: values.instructions }
		).then((result) => {
			toast.success(__("AI SDR draft created"))
			window.open(`/app/ai-sdr?activity=${encodeURIComponent(result.name)}`, "_blank")
		}).catch((error) => {
			toast.error(error.messages?.[0] || __("Unable to prepare outreach"))
		})
	}
	async enrollInSequence() {
		const values = await this.formDialog({
			title: __("Enroll in AI SDR Sequence"),
			fields: [
				{
					fieldname: "sequence",
					fieldtype: "Link",
					label: __("Sequence"),
					options: "AI SDR Sequence",
					reqd: 1
				}
			],
			required: ["sequence"],
			submitLabel: __("Enroll"),
			cancelLabel: __("Cancel")
		})
		if (!values) return
		call(
			"loopjet_frappe_custom.ai_sdr.api.enroll",
			{ lead: this.doc.name, sequence: values.sequence }
		).then(() => {
			toast.success(__("Lead enrolled in AI SDR sequence"))
			window.open(`/app/ai-sdr?lead=${encodeURIComponent(this.doc.name)}`, "_blank")
		}).catch((error) => {
			toast.error(error.messages?.[0] || __("Unable to enroll lead"))
		})
	}
}
"""


def ensure_crm_form_script() -> None:
	import frappe

	values = {
		"dt": "CRM Lead",
		"view": "Form",
		"script": _lead_form_script(),
		"enabled": 1,
		"is_standard": 1,
	}
	if frappe.db.exists("CRM Form Script", LEAD_FORM_SCRIPT_NAME):
		doc = frappe.get_doc("CRM Form Script", LEAD_FORM_SCRIPT_NAME)
		updates = {
			fieldname: value
			for fieldname, value in values.items()
			if doc.get(fieldname) != value
		}
		if updates:
			# Frappe CRM intentionally rejects normal saves to standard scripts
			# outside developer mode. App migrations use the same direct update
			# pattern as CRM's own standard-script installers.
			frappe.db.set_value("CRM Form Script", LEAD_FORM_SCRIPT_NAME, updates)
		return
	frappe.get_doc({"doctype": "CRM Form Script", "name": LEAD_FORM_SCRIPT_NAME, **values}).insert(
		ignore_permissions=True
	)


def ensure_crm_workspace_shortcut() -> None:
	import frappe

	if not frappe.db.exists("Workspace", "Frappe CRM"):
		return
	workspace = frappe.get_doc("Workspace", "Frappe CRM")
	if not workspace.type:
		workspace.type = "Workspace"
	shortcut = next((row for row in workspace.shortcuts if row.label == AI_SDR_SHORTCUT_LABEL), None)
	values = {
		"type": "URL",
		"url": AI_SDR_PAGE_URL,
		"link_to": "",
		"label": AI_SDR_SHORTCUT_LABEL,
		"icon": "zap",
		"color": "Grey",
	}
	changed = False
	if shortcut is None:
		workspace.append("shortcuts", values)
		changed = True
	else:
		for fieldname, value in values.items():
			if shortcut.get(fieldname) != value:
				shortcut.set(fieldname, value)
				changed = True
	workspace.content, layout_changed = add_ai_sdr_shortcut_to_layout(workspace.content)
	if changed or layout_changed:
		workspace.save(ignore_permissions=True)


def ensure_starter_sequence() -> None:
	import frappe

	name = "Supervised B2B Outreach"
	if frappe.db.exists("AI SDR Sequence", name):
		return
	sequence = frappe.get_doc(
		{
			"doctype": "AI SDR Sequence",
			"sequence_name": name,
			"enabled": 0,
			"default_language": "English",
			"description": "Starter sequence. Review every step and enable it only after approval.",
			"stop_on_reply": 1,
			"stop_on_deal": 1,
		}
	)
	for step in (
		{
			"step_name": "Personalized first email",
			"delay_days": 0,
			"channel": "Email",
			"action_type": "First Touch",
			"instructions": "Use one verified account signal and one role-relevant problem hypothesis.",
		},
		{
			"step_name": "LinkedIn follow-up",
			"delay_days": 2,
			"channel": "LinkedIn",
			"action_type": "Follow-up",
			"instructions": "Keep the note short and do not repeat the full email.",
		},
		{
			"step_name": "Useful email follow-up",
			"delay_days": 3,
			"channel": "Email",
			"action_type": "Follow-up",
			"instructions": "Add useful context; do not use a generic just-checking-in message.",
		},
		{
			"step_name": "Call preparation",
			"delay_days": 3,
			"channel": "Call",
			"action_type": "Call Preparation",
			"instructions": "Prepare three concise discovery questions based on verified evidence.",
		},
	):
		sequence.append("steps", {**step, "requires_approval": 1})
	sequence.insert(ignore_permissions=True)
