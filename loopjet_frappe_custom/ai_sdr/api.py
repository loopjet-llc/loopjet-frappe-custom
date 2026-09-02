from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now, nowdate

from loopjet_frappe_custom.ai_sdr.permissions import require_sdr_access
from loopjet_frappe_custom.ai_sdr.services import (
	ai_credentials_present,
	ai_is_configured,
	ai_is_connected,
	create_manual_activity,
	enroll_lead,
	get_settings,
	mark_manual_activity_sent,
	send_academy_manual_email,
	send_approved_email,
)
from loopjet_frappe_custom.ai_sdr.services import (
	approve_activity as approve_activity_service,
)
from loopjet_frappe_custom.ai_sdr.services import (
	reject_activity as reject_activity_service,
)
from loopjet_frappe_custom.ai_sdr.services import (
	test_ai_connection as test_ai_connection_service,
)


def _can_manage() -> bool:
	roles = set(frappe.get_roles())
	return (
		"System Manager" in roles
		or "AI SDR Manager" in roles
		or frappe.session.user == "Administrator"
	)


def _owner_filters(filters: dict | None = None) -> dict:
	filters = dict(filters or {})
	if not _can_manage():
		filters["assigned_to"] = frappe.session.user
	return filters


def _count(doctype: str, filters: dict | None = None) -> int:
	return len(
		frappe.get_all(
			doctype,
			filters=_owner_filters(filters),
			pluck="name",
			limit_page_length=10000,
		)
	)


@frappe.whitelist()
def get_access_context() -> dict:
	require_sdr_access()
	return {"can_manage": _can_manage()}


@frappe.whitelist()
def get_dashboard_context() -> dict:
	require_sdr_access()
	settings = get_settings()
	activities = frappe.get_all(
		"AI SDR Activity",
		filters=_owner_filters({"status": ["in", ["Draft", "Needs Approval", "Approved", "Failed"]]}),
		fields=[
			"name",
			"modified",
			"lead",
			"recipient_name",
			"recipient_email",
			"channel",
			"activity_type",
			"status",
			"subject",
			"body",
			"ai_rationale",
			"last_error",
		],
		order_by="modified desc",
		limit=25,
	)
	replies = frappe.get_all(
		"AI SDR Activity",
		filters=_owner_filters({"direction": "Inbound", "status": "Received"}),
		fields=[
			"name",
			"modified",
			"lead",
			"recipient_name",
			"recipient_email",
			"subject",
			"reply_classification",
			"reply_confidence",
		],
		order_by="modified desc",
		limit=10,
	)
	return {
		"user": frappe.session.user,
		"can_manage": _can_manage(),
		"configuration": {
			"ai_provider": settings.ai_provider or "OpenRouter",
			"ai_model": settings.ai_model,
			"ai_enabled": bool(settings.ai_enabled),
			"ai_configured": ai_is_configured(settings),
			"ai_connected": ai_is_connected(settings),
			"ai_credentials_present": ai_credentials_present(settings),
			"connection_status": settings.connection_status or "Not Tested",
			"last_connection_test_at": settings.last_connection_test_at,
			"last_connection_error": settings.last_connection_error,
			"sending_enabled": bool(settings.sending_enabled),
			"sender_email_account": settings.sender_email_account,
			"max_daily_emails": settings.max_daily_emails,
		},
		"metrics": {
			"research_ready": _count("AI SDR Research", {"status": "Ready"}),
			"active_enrollments": _count("AI SDR Enrollment", {"status": "Active"}),
			"awaiting_approval": _count("AI SDR Activity", {"status": "Needs Approval"}),
			"approved_to_send": _count("AI SDR Activity", {"status": "Approved"}),
			"due_follow_ups": _count(
				"AI SDR Enrollment",
				{"status": "Active", "next_action_at": ["<=", now()]},
			),
			"replies_today": _count(
				"AI SDR Activity",
				{"direction": "Inbound", "creation": [">=", f"{nowdate()} 00:00:00"]},
			),
		},
		"activities": activities,
		"replies": replies,
	}


@frappe.whitelist()
def test_ai_connection() -> dict:
	require_sdr_access(manager=True)
	return test_ai_connection_service()


@frappe.whitelist()
def prepare_lead(lead: str, channel: str = "Email", instructions: str | None = None) -> dict:
	require_sdr_access()
	if channel not in {"Email", "LinkedIn", "Call"}:
		frappe.throw(_("Unsupported outreach channel."))
	if not frappe.has_permission("CRM Lead", "read", lead):
		frappe.throw(_("You do not have access to this CRM Lead."), frappe.PermissionError)
	name = create_manual_activity(lead, channel, instructions)
	return {"name": name, "status": "Draft"}


@frappe.whitelist(methods=["POST"])
def send_academy_email(lead: str, subject: str, body: str) -> dict:
	require_sdr_access(manager=True)
	if not frappe.has_permission("CRM Lead", "read", lead):
		frappe.throw(_("You do not have access to this CRM Lead."), frappe.PermissionError)
	return send_academy_manual_email(lead, subject, body)


@frappe.whitelist()
def enroll(lead: str, sequence: str, assigned_to: str | None = None) -> dict:
	require_sdr_access(manager=True)
	name = enroll_lead(lead, sequence, assigned_to)
	return {"name": name, "status": "Active"}


@frappe.whitelist()
def analyze_research(name: str) -> dict:
	require_sdr_access(manager=True)
	if not ai_is_configured():
		frappe.throw(_("AI generation is not configured or enabled."))
	research = frappe.get_doc("AI SDR Research", name)
	if research.status == "Analyzing":
		return {"name": name, "status": "Analyzing"}
	research.db_set({"status": "Analyzing", "last_error": ""}, update_modified=True)
	frappe.enqueue(
		"loopjet_frappe_custom.ai_sdr.services.analyze_research",
		research_name=name,
		queue="long",
		enqueue_after_commit=True,
	)
	return {"name": name, "status": "Analyzing"}


@frappe.whitelist()
def regenerate_activity(name: str) -> dict:
	require_sdr_access()
	activity = frappe.get_doc("AI SDR Activity", name)
	if not activity.has_permission("write"):
		frappe.throw(_("You do not have write access to this activity."), frappe.PermissionError)
	frappe.enqueue(
		"loopjet_frappe_custom.ai_sdr.services.generate_activity",
		activity_name=name,
		queue="long",
		enqueue_after_commit=True,
	)
	return {"name": name, "status": "Generating"}


@frappe.whitelist()
def approve_activity(name: str) -> dict:
	require_sdr_access(manager=True)
	approve_activity_service(name, frappe.session.user)
	return {"name": name, "status": "Approved"}


@frappe.whitelist()
def reject_activity(name: str, reason: str = "") -> dict:
	require_sdr_access(manager=True)
	reject_activity_service(name, frappe.session.user, reason)
	return {"name": name, "status": "Rejected"}


@frappe.whitelist()
def send_activity(name: str) -> dict:
	require_sdr_access(manager=True)
	send_approved_email(name)
	return {"name": name, "status": "Sent"}


@frappe.whitelist()
def mark_manual_sent(name: str) -> dict:
	require_sdr_access()
	activity = frappe.get_doc("AI SDR Activity", name)
	if not activity.has_permission("write"):
		frappe.throw(_("You do not have write access to this activity."), frappe.PermissionError)
	mark_manual_activity_sent(name)
	return {"name": name, "status": "Sent"}
