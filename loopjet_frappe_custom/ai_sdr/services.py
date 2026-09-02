from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now, now_datetime, nowdate

from loopjet_frappe_custom.ai_sdr.client import AIProviderError, complete_json
from loopjet_frappe_custom.ai_sdr.domain import (
	REPLY_INTERESTED,
	REPLY_NEEDS_INFORMATION,
	REPLY_NOT_INTERESTED,
	REPLY_NOT_NOW,
	REPLY_OUT_OF_OFFICE,
	REPLY_REFERRAL,
	REPLY_UNKNOWN,
	REPLY_UNSUBSCRIBE,
	classify_reply_fallback,
	has_unresolved_template,
	next_action_at,
	normalize_domain,
	normalize_suppression_key,
	render_safe_template,
	suppression_candidates,
	validate_outreach_result,
	validate_reply_result,
	validate_source_urls,
)
from loopjet_frappe_custom.ai_sdr.prompts import (
	OUTREACH_PROMPT_VERSION,
	REPLY_PROMPT_VERSION,
	RESEARCH_PROMPT_VERSION,
	outreach_messages,
	reply_messages,
	research_messages,
)

ACTIVE_STATUSES = ("Active", "Paused")
REVIEW_TASK_CATEGORIES = {
	REPLY_INTERESTED,
	REPLY_NEEDS_INFORMATION,
	REPLY_REFERRAL,
	REPLY_UNKNOWN,
}
ACADEMY_TAG = "Learnlayer Academy"
ACADEMY_MANUAL_MESSAGE_VERSION = "academy-manual-v1"
ACADEMY_OUTBOUND_PATH = "/functions/v1/academy-outbound-email"


def get_settings():
	return frappe.get_single("AI SDR Settings")


def ai_credentials_present(settings=None) -> bool:
	settings = settings or get_settings()
	return bool(
		settings.ai_base_url
		and settings.ai_model
		and settings.get_password("ai_api_key", raise_exception=False)
	)


def ai_is_connected(settings=None) -> bool:
	settings = settings or get_settings()
	return bool(ai_credentials_present(settings) and settings.connection_status == "Connected")


def ai_is_configured(settings=None) -> bool:
	settings = settings or get_settings()
	return bool(settings.ai_enabled and ai_is_connected(settings))


def _provider_name(settings) -> str:
	return settings.ai_provider or urlparse(settings.ai_base_url).hostname or "OpenAI-compatible"


def _record_connection_state(status: str, *, error: str = "") -> None:
	frappe.db.set_single_value("AI SDR Settings", "connection_status", status)
	frappe.db.set_single_value("AI SDR Settings", "last_connection_test_at", now())
	frappe.db.set_single_value("AI SDR Settings", "last_connection_error", error[:1000])


def test_ai_connection() -> dict[str, Any]:
	settings = get_settings()
	api_key = settings.get_password("ai_api_key", raise_exception=False)
	missing = [
		label
		for value, label in (
			(settings.ai_base_url, _("AI Base URL")),
			(settings.ai_model, _("AI Model")),
			(api_key, _("AI API Key")),
		)
		if not value
	]
	if missing:
		error = _("Missing required settings: {0}.").format(", ".join(missing))
		_record_connection_state("Failed", error=error)
		return {"connected": False, "error": error}

	try:
		result, usage = complete_json(
			base_url=settings.ai_base_url,
			api_key=api_key,
			model=settings.ai_model,
			system_prompt=(
				"You are a connectivity test for Loopjet AI SDR. "
				'Return only this JSON object: {"connected": true}.'
			),
			user_prompt='Confirm the connection by returning {"connected": true}.',
			timeout_seconds=settings.ai_timeout_seconds or 60,
			provider=settings.ai_provider or "OpenRouter",
			app_url=frappe.utils.get_url(),
		)
		if result.get("connected") is not True:
			raise AIProviderError("The configured model returned an invalid connection-test result.")
	except Exception as exc:
		error = str(exc).replace(str(api_key), "[redacted]")[:1000]
		_record_connection_state("Failed", error=error)
		return {"connected": False, "error": error}

	_record_connection_state("Connected")
	return {
		"connected": True,
		"provider": _provider_name(settings),
		"model": settings.ai_model,
		"usage": usage,
	}


def _source_urls(value: str | None) -> list[str]:
	return validate_source_urls([line.strip() for line in (value or "").splitlines() if line.strip()])


def _source_urls_text(urls: list[str]) -> str:
	return "\n".join(validate_source_urls(urls))


def _complete_with_settings(settings, system_prompt: str, user_prompt: str):
	api_key = settings.get_password("ai_api_key", raise_exception=False)
	if not api_key:
		raise AIProviderError("AI API Key is not configured.")
	return complete_json(
		base_url=settings.ai_base_url,
		api_key=api_key,
		model=settings.ai_model,
		system_prompt=system_prompt,
		user_prompt=user_prompt,
		timeout_seconds=settings.ai_timeout_seconds or 60,
		provider=settings.ai_provider or "OpenRouter",
		app_url=frappe.utils.get_url(),
	)


def analyze_research(research_name: str) -> str:
	research = frappe.get_doc("AI SDR Research", research_name)
	settings = get_settings()
	if not ai_is_configured(settings):
		frappe.throw(_("AI generation is not configured or enabled."))

	research.db_set({"status": "Analyzing", "last_error": ""}, update_modified=True)
	urls = _source_urls(research.source_urls)
	context = {
		"organization": research.organization,
		"website": research.website,
		"source_urls": urls,
		"reviewed_source_evidence": research.source_evidence,
		"existing_summary": research.company_summary,
	}
	system_prompt, user_prompt = research_messages(context)
	try:
		result, _usage = _complete_with_settings(settings, system_prompt, user_prompt)
		used_sources = [url for url in validate_source_urls(result.get("evidence_urls")) if url in set(urls)]
		research.update(
			{
				"company_summary": str(result.get("company_summary") or "").strip(),
				"current_trigger": str(result.get("current_trigger") or "").strip(),
				"pain_hypothesis": str(result.get("pain_hypothesis") or "").strip(),
				"outreach_angle": str(result.get("outreach_angle") or "").strip(),
				"fit_score": result.get("fit_score"),
				"trigger_score": result.get("trigger_score"),
				"persona_score": result.get("persona_score"),
				"data_quality_score": result.get("data_quality_score"),
				"ai_confidence": result.get("confidence"),
				"evidence_json": json.dumps(
					{"used_source_urls": used_sources, "analysis": result},
					ensure_ascii=False,
					indent=2,
					default=str,
				),
				"ai_provider": _provider_name(settings),
				"ai_model": settings.ai_model,
				"prompt_version": RESEARCH_PROMPT_VERSION,
				"researched_at": now(),
				"status": "Ready",
				"last_error": "",
			}
		)
		research.save(ignore_permissions=True)
		sync_research_to_organization(research)
		return research.name
	except Exception as exc:
		research.db_set(
			{"status": "Failed", "last_error": str(exc)[:1000]},
			update_modified=True,
		)
		frappe.log_error(frappe.get_traceback(), f"AI SDR research failed: {research.name}")
		raise


def sync_research_to_organization(research) -> None:
	if not research.organization or not frappe.db.exists("CRM Organization", research.organization):
		return
	meta = frappe.get_meta("CRM Organization")
	values = {}
	for fieldname, value in {
		"ai_sdr_research_status": research.status,
		"ai_sdr_icp_score": research.icp_score,
		"ai_sdr_icp_tier": research.icp_tier,
		"ai_sdr_last_researched_at": research.researched_at,
		"ai_sdr_linkedin_url": research.linkedin_company_url,
	}.items():
		if meta.has_field(fieldname):
			values[fieldname] = value
	if values:
		frappe.db.set_value("CRM Organization", research.organization, values)


def _find_research(organization: str | None):
	if not organization:
		return None
	names = frappe.get_all(
		"AI SDR Research",
		filters={"organization": organization, "status": "Ready"},
		pluck="name",
		order_by="researched_at desc, modified desc",
		limit=1,
	)
	return frappe.get_doc("AI SDR Research", names[0]) if names else None


def _lead_context(lead) -> dict[str, Any]:
	return {
		"name": lead.name,
		"first_name": lead.get("first_name"),
		"last_name": lead.get("last_name"),
		"lead_name": lead.get("lead_name"),
		"job_title": lead.get("job_title"),
		"organization": lead.get("ai_sdr_organization") or lead.get("organization"),
		"email": lead.get("email"),
		"persona": lead.get("ai_sdr_persona"),
		"preferred_language": lead.get("ai_sdr_language"),
		"source": lead.get("source"),
	}


def _research_context(research) -> dict[str, Any]:
	if not research:
		return {}
	return {
		"company_summary": research.company_summary,
		"current_trigger": research.current_trigger,
		"pain_hypothesis": research.pain_hypothesis,
		"outreach_angle": research.outreach_angle,
		"icp_score": research.icp_score,
		"icp_tier": research.icp_tier,
		"source_urls": _source_urls(research.source_urls),
		"reviewed_source_evidence": research.source_evidence,
	}


def _sequence_step(activity):
	if not activity.sequence or not activity.sequence_step:
		return None
	sequence = frappe.get_doc("AI SDR Sequence", activity.sequence)
	index = int(activity.sequence_step) - 1
	return sequence.steps[index] if 0 <= index < len(sequence.steps) else None


def _apply_fallback_template(activity, lead, step) -> None:
	if not step:
		return
	context = {
		"first_name": lead.get("first_name") or "",
		"last_name": lead.get("last_name") or "",
		"organization": lead.get("ai_sdr_organization") or lead.get("organization") or "",
		"job_title": lead.get("job_title") or "",
	}
	if step.subject_template:
		activity.subject = render_safe_template(
			step.subject_template,
			context,
			escape_values=False,
		)
	if step.body_template:
		activity.body = render_safe_template(step.body_template, context)
	if activity.body:
		activity.status = "Needs Approval"


def generate_activity(activity_name: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.status not in {"Draft", "Generating", "Failed"}:
		return activity.name
	if not activity.lead or not frappe.db.exists("CRM Lead", activity.lead):
		frappe.throw(_("A valid CRM Lead is required to generate outreach."))

	lead = frappe.get_doc("CRM Lead", activity.lead)
	step = _sequence_step(activity)
	research = _find_research(activity.organization)
	settings = get_settings()
	activity.status = "Generating"
	activity.last_error = ""
	activity.save(ignore_permissions=True)

	if not ai_is_configured(settings):
		_apply_fallback_template(activity, lead, step)
		if not activity.body:
			activity.status = "Draft"
		activity.last_error = (
			"AI generation is disabled. Complete the draft manually or configure AI SDR Settings."
		)
		activity.save(ignore_permissions=True)
		return activity.name

	research_context = _research_context(research)
	allowed_sources = research_context.get("source_urls") or []
	context = {
		"channel": activity.channel,
		"activity_type": activity.activity_type,
		"language": lead.get("ai_sdr_language")
		or (
			frappe.get_doc("AI SDR Sequence", activity.sequence).default_language
			if activity.sequence
			else None
		)
		or settings.default_language,
		"sender_name": settings.default_sender_name,
		"approved_company_context": settings.company_context,
		"prospect": _lead_context(lead),
		"account_research": research_context,
		"drafting_instructions": activity.drafting_instructions or (step.instructions if step else ""),
		"previous_subject": activity.subject,
		"previous_body": activity.body,
	}
	system_prompt, user_prompt = outreach_messages(context)
	try:
		result, usage = _complete_with_settings(settings, system_prompt, user_prompt)
		validated = validate_outreach_result(result, allowed_sources)
		activity.update(
			{
				"subject": validated["subject"],
				"body": validated["body"],
				"ai_rationale": validated["rationale"],
				"source_urls": _source_urls_text(validated["evidence_urls"]),
				"personalization_evidence": research.source_evidence if research else "",
				"status": "Needs Approval",
				"ai_provider": _provider_name(settings),
				"ai_model": settings.ai_model,
				"prompt_version": OUTREACH_PROMPT_VERSION,
				"prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens") or 0,
				"completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens") or 0,
				"last_error": "",
			}
		)
		activity.save(ignore_permissions=True)
		return activity.name
	except Exception as exc:
		activity.db_set(
			{"status": "Failed", "last_error": str(exc)[:1000]},
			update_modified=True,
		)
		frappe.log_error(frappe.get_traceback(), f"AI SDR drafting failed: {activity.name}")
		raise


def _resolve_organization(lead) -> str | None:
	organization = lead.get("ai_sdr_organization") or lead.get("organization")
	if not organization:
		return None
	if frappe.db.exists("CRM Organization", organization):
		return organization
	return frappe.db.get_value("CRM Organization", {"organization_name": organization}, "name")


def create_manual_activity(
	lead_name: str,
	channel: str,
	instructions: str | None = None,
) -> str:
	lead = frappe.get_doc("CRM Lead", lead_name)
	if lead.get("ai_sdr_do_not_contact"):
		frappe.throw(_("This CRM Lead is marked Do Not Contact."))
	organization = _resolve_organization(lead)
	if is_suppressed(email=lead.email, lead=lead.name, organization=organization):
		frappe.throw(_("This prospect or organization is suppressed from outbound contact."))

	activity = frappe.get_doc(
		{
			"doctype": "AI SDR Activity",
			"lead": lead.name,
			"organization": organization,
			"assigned_to": lead.get("lead_owner") or frappe.session.user,
			"activity_type": "First Touch",
			"channel": channel,
			"direction": "Outbound",
			"status": "Draft",
			"recipient_name": lead.get("lead_name")
			or " ".join(filter(None, [lead.get("first_name"), lead.get("last_name")])),
			"recipient_email": lead.get("email"),
			"drafting_instructions": instructions,
			"idempotency_key": f"manual:{lead.name}:{uuid.uuid4().hex}",
		}
	).insert(ignore_permissions=True)
	frappe.enqueue(
		"loopjet_frappe_custom.ai_sdr.services.generate_activity",
		activity_name=activity.name,
		queue="long",
		enqueue_after_commit=True,
	)
	return activity.name


def enroll_lead(lead_name: str, sequence_name: str, assigned_to: str | None = None) -> str:
	lead = frappe.get_doc("CRM Lead", lead_name)
	sequence = frappe.get_doc("AI SDR Sequence", sequence_name)
	if not sequence.enabled:
		frappe.throw(_("The selected AI SDR Sequence is disabled."))
	if lead.get("ai_sdr_do_not_contact"):
		frappe.throw(_("This CRM Lead is marked Do Not Contact."))
	organization = _resolve_organization(lead)
	if is_suppressed(email=lead.email, lead=lead.name, organization=organization):
		frappe.throw(_("This prospect or organization is suppressed from outbound contact."))

	enrollment = frappe.get_doc(
		{
			"doctype": "AI SDR Enrollment",
			"lead": lead.name,
			"organization": organization,
			"sequence": sequence.name,
			"assigned_to": assigned_to or lead.get("lead_owner") or frappe.session.user,
			"status": "Active",
			"current_step": 0,
			"next_action_at": now(),
		}
	).insert(ignore_permissions=True)
	_sync_lead_state(enrollment, state="Ready")
	return enrollment.name


def _enrollment_step(enrollment):
	sequence = frappe.get_doc("AI SDR Sequence", enrollment.sequence)
	index = int(enrollment.current_step or 0)
	return sequence, (sequence.steps[index] if index < len(sequence.steps) else None)


def create_due_activity(enrollment_name: str) -> str | None:
	enrollment = frappe.get_doc("AI SDR Enrollment", enrollment_name)
	if enrollment.status != "Active":
		return None
	sequence, step = _enrollment_step(enrollment)
	if not step:
		enrollment.db_set(
			{"status": "Completed", "completed_at": now(), "next_action_at": None},
			update_modified=True,
		)
		_sync_lead_state(enrollment, state="Stopped")
		return None
	lead = frappe.get_doc("CRM Lead", enrollment.lead)
	if lead.get("ai_sdr_do_not_contact") or is_suppressed(
		email=lead.email,
		lead=lead.name,
		organization=enrollment.organization,
	):
		stop_enrollment(enrollment, "Suppression or Do Not Contact is active.")
		return None

	step_number = int(enrollment.current_step or 0) + 1
	idempotency_key = f"enrollment:{enrollment.name}:step:{step_number}"
	existing = frappe.db.exists("AI SDR Activity", {"idempotency_key": idempotency_key})
	if existing:
		return existing

	activity = frappe.get_doc(
		{
			"doctype": "AI SDR Activity",
			"enrollment": enrollment.name,
			"sequence": sequence.name,
			"sequence_step": step_number,
			"lead": enrollment.lead,
			"organization": enrollment.organization,
			"assigned_to": enrollment.assigned_to,
			"activity_type": step.action_type,
			"channel": step.channel,
			"direction": "Outbound",
			"status": "Draft",
			"recipient_name": lead.get("lead_name")
			or " ".join(filter(None, [lead.get("first_name"), lead.get("last_name")])),
			"recipient_email": lead.get("email"),
			"drafting_instructions": step.instructions,
			"idempotency_key": idempotency_key,
		}
	)
	_apply_fallback_template(activity, lead, step)
	activity.insert(ignore_permissions=True)
	enrollment.db_set({"last_activity": activity.name, "next_action_at": None}, update_modified=True)
	frappe.enqueue(
		"loopjet_frappe_custom.ai_sdr.services.generate_activity",
		activity_name=activity.name,
		queue="long",
		enqueue_after_commit=True,
	)
	return activity.name


def process_due_enrollments() -> int:
	if "crm" not in frappe.get_installed_apps() or not frappe.db.exists("DocType", "AI SDR Enrollment"):
		return 0
	resume_timed_pauses()
	settings = get_settings()
	names = frappe.get_all(
		"AI SDR Enrollment",
		filters={"status": "Active", "next_action_at": ["<=", now()]},
		pluck="name",
		order_by="next_action_at asc",
		limit=max(1, int(settings.max_actions_per_run or 20)),
	)
	created = 0
	for name in names:
		if create_due_activity(name):
			created += 1
	return created


def resume_timed_pauses() -> int:
	names = frappe.get_all(
		"AI SDR Enrollment",
		filters={"status": "Paused", "paused_until": ["<=", now()]},
		pluck="name",
		limit=100,
	)
	for name in names:
		enrollment = frappe.get_doc("AI SDR Enrollment", name)
		enrollment.db_set(
			{
				"status": "Active",
				"paused_until": None,
				"stop_reason": "",
				"next_action_at": now(),
			},
			update_modified=True,
		)
	return len(names)


def approve_activity(activity_name: str, user: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.status not in {"Draft", "Needs Approval", "Failed"}:
		frappe.throw(_("Only a draft or review item can be approved."))
	if activity.channel != "Call" and not (activity.body or "").strip():
		frappe.throw(_("Complete the message body before approval."))
	if has_unresolved_template(activity.subject) or has_unresolved_template(activity.body):
		frappe.throw(_("Resolve all unsupported template placeholders before approval."))
	activity.update(
		{
			"status": "Approved",
			"approved_by": user,
			"approved_at": now(),
			"rejection_reason": "",
			"last_error": "",
		}
	)
	activity.flags.ai_sdr_approval_action = True
	activity.save(ignore_permissions=True)
	return activity.name


def reject_activity(activity_name: str, user: str, reason: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.status not in {"Draft", "Generating", "Needs Approval", "Failed", "Approved"}:
		frappe.throw(_("This activity can no longer be rejected."))
	activity.update(
		{
			"status": "Rejected",
			"approved_by": "",
			"approved_at": None,
			"rejection_reason": (reason or "").strip() or f"Rejected by {user}",
		}
	)
	activity.flags.ai_sdr_rejection_action = True
	activity.save(ignore_permissions=True)
	if activity.enrollment:
		enrollment = frappe.get_doc("AI SDR Enrollment", activity.enrollment)
		enrollment.db_set(
			{
				"status": "Paused",
				"stop_reason": f"Activity {activity.name} was rejected.",
				"next_action_at": None,
			},
			update_modified=True,
		)
	return activity.name


def _email_sender(settings) -> str:
	if not settings.sender_email_account:
		frappe.throw(_("Configure a Sender Email Account in AI SDR Settings."))
	email_id = frappe.db.get_value("Email Account", settings.sender_email_account, "email_id")
	if not email_id:
		frappe.throw(_("The configured Sender Email Account has no email address."))
	return email_id


def _daily_email_count() -> int:
	return frappe.db.count(
		"AI SDR Activity",
		filters={
			"channel": "Email",
			"direction": "Outbound",
			"status": "Sent",
			"sent_at": [">=", f"{nowdate()} 00:00:00"],
		},
	)


def _academy_outbound_configuration(settings) -> tuple[str, str]:
	url = str(settings.get("academy_outbound_url") or "").strip()
	secret = settings.get_password("academy_outbound_secret", raise_exception=False)
	parsed = urlparse(url)
	if (
		parsed.scheme != "https"
		or not parsed.hostname
		or not parsed.hostname.endswith(".supabase.co")
		or parsed.username
		or parsed.password
		or parsed.path != ACADEMY_OUTBOUND_PATH
		or parsed.params
		or parsed.query
		or parsed.fragment
	):
		frappe.throw(_("Configure a valid HTTPS Academy outbound Edge endpoint."))
	if not secret:
		frappe.throw(_("Configure the Academy outbound shared secret."))
	return url, secret


def _academy_manual_message_values(subject: str, body: str) -> tuple[str, str]:
	subject = str(subject or "").strip()
	body = str(body or "").strip()
	if len(subject) < 5 or len(subject) > 120 or "\n" in subject or "\r" in subject:
		frappe.throw(_("Subject must be 5 to 120 characters on one line."))
	if len(body) < 10 or len(body) > 5000:
		frappe.throw(_("Message body must be 10 to 5,000 characters."))
	return subject, body


def send_academy_manual_email(lead_name: str, subject: str, body: str) -> dict[str, Any]:
	settings = get_settings()
	if not settings.get("academy_manual_sending_enabled"):
		frappe.throw(_("Manual Academy email sending is disabled in AI SDR Settings."))
	url, secret = _academy_outbound_configuration(settings)
	lead = frappe.get_doc("CRM Lead", lead_name)
	tags = {tag.strip() for tag in str(lead.get("_user_tags") or "").split(",") if tag.strip()}
	if ACADEMY_TAG not in tags:
		frappe.throw(_("This CRM Lead is not in the LearnLayer Academy motion."), frappe.PermissionError)
	organization = _resolve_organization(lead)
	if lead.get("ai_sdr_do_not_contact") or is_suppressed(
		email=lead.get("email"),
		lead=lead.name,
		organization=organization,
	):
		frappe.throw(_("Delivery blocked because the recipient is suppressed."))
	if not lead.get("email"):
		frappe.throw(_("Recipient Email is required."))
	subject, body = _academy_manual_message_values(subject, body)
	if _daily_email_count() >= int(settings.max_daily_emails or 0):
		frappe.throw(_("The AI SDR daily email limit has been reached."))

	activity = frappe.get_doc(
		{
			"doctype": "AI SDR Activity",
			"lead": lead.name,
			"organization": organization,
			"assigned_to": frappe.session.user,
			"activity_type": "First Touch",
			"channel": "Email",
			"direction": "Outbound",
			"status": "Approved",
			"recipient_name": lead.get("lead_name")
			or " ".join(filter(None, [lead.get("first_name"), lead.get("last_name")])),
			"recipient_email": lead.get("email"),
			"subject": subject,
			"body": body,
			"approved_by": frappe.session.user,
			"approved_at": now(),
			"prompt_version": ACADEMY_MANUAL_MESSAGE_VERSION,
			"idempotency_key": f"academy-manual:{lead.name}:{uuid.uuid4().hex}",
			"provider_outcome": "",
			"last_error": "",
		}
	).insert(ignore_permissions=True)
	# Persist the human-authored audit before the irreversible provider request.
	frappe.db.commit()

	try:
		response = requests.post(
			url,
			headers={
				"Content-Type": "application/json",
				"x-academy-outbound-secret": secret,
			},
			json={
				"lead": lead.name,
				"mode": "manual",
				"messageVersion": ACADEMY_MANUAL_MESSAGE_VERSION,
				"activity": activity.name,
				"subject": subject,
				"body": body,
				"author": frappe.session.user,
			},
			timeout=30,
		)
		result = response.json() if response.content else {}
		if not response.ok:
			detail = result.get("error") or ", ".join(result.get("reasons") or []) or "request_rejected"
			raise frappe.ValidationError(f"Academy outbound rejected the request: {detail}")
		provider_id = str(result.get("providerEmailId") or "").strip()
		if result.get("providerAccepted") is not True or not provider_id:
			raise frappe.ValidationError("Academy outbound did not confirm provider acceptance.")
	except requests.RequestException as exc:
		activity.db_set(
			{
				"status": "Failed",
				"last_error": f"Provider outcome unknown after transport failure: {exc}"[:1000],
			},
			update_modified=True,
		)
		frappe.db.commit()
		raise
	except Exception as exc:
		activity.db_set(
			{"status": "Failed", "last_error": str(exc)[:1000]},
			update_modified=True,
		)
		frappe.db.commit()
		raise

	activity.db_set(
		{
			"status": "Accepted",
			"provider_message_id": provider_id,
			"provider_outcome": "Accepted",
			"sent_at": now(),
			"last_error": "",
		},
		update_modified=True,
	)
	frappe.db.commit()
	return {
		"name": activity.name,
		"status": "Accepted",
		"provider_message_id": provider_id,
		"provider_outcome": "Accepted",
	}


def send_approved_email(activity_name: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	settings = get_settings()
	if not settings.sending_enabled:
		frappe.throw(_("Approved email sending is disabled in AI SDR Settings."))
	if activity.status != "Approved" or not activity.approved_by:
		frappe.throw(_("This email has not been approved."))
	if activity.channel != "Email":
		frappe.throw(_("Only email activities can use the email sender."))
	if not activity.recipient_email:
		frappe.throw(_("Recipient Email is required."))
	if is_suppressed(
		email=activity.recipient_email,
		lead=activity.lead,
		organization=activity.organization,
	):
		frappe.throw(_("Delivery blocked because the recipient is suppressed."))
	if _daily_email_count() >= int(settings.max_daily_emails or 0):
		frappe.throw(_("The AI SDR daily email limit has been reached."))

	try:
		frappe.sendmail(
			recipients=[activity.recipient_email],
			sender=_email_sender(settings),
			subject=activity.subject or "",
			message=activity.body,
			reference_doctype="CRM Lead" if activity.lead else None,
			reference_name=activity.lead,
			now=True,
		)
	except Exception as exc:
		activity.db_set(
			{"status": "Failed", "last_error": str(exc)[:1000]},
			update_modified=True,
		)
		raise
	_mark_activity_sent(activity)
	return activity.name


def mark_manual_activity_sent(activity_name: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.status != "Approved" or not activity.approved_by:
		frappe.throw(_("This activity has not been approved."))
	if activity.channel not in {"LinkedIn", "Call"}:
		frappe.throw(_("Only LinkedIn and Call activities can be marked manually sent or completed."))
	if is_suppressed(
		email=activity.recipient_email,
		lead=activity.lead,
		organization=activity.organization,
	):
		frappe.throw(_("Action blocked because the prospect is suppressed."))
	_mark_activity_sent(activity)
	return activity.name


def _mark_activity_sent(activity) -> None:
	activity.update({"status": "Sent", "sent_at": now(), "last_error": ""})
	activity.flags.ai_sdr_delivery_action = True
	activity.save(ignore_permissions=True)
	advance_enrollment(activity)


def advance_enrollment(activity) -> None:
	if not activity.enrollment:
		return
	enrollment = frappe.get_doc("AI SDR Enrollment", activity.enrollment)
	if enrollment.status not in ACTIVE_STATUSES or int(activity.sequence_step or 0) <= int(
		enrollment.current_step or 0
	):
		return
	sequence = frappe.get_doc("AI SDR Sequence", enrollment.sequence)
	completed_steps = int(activity.sequence_step)
	if completed_steps >= len(sequence.steps):
		enrollment.db_set(
			{
				"current_step": completed_steps,
				"status": "Completed",
				"completed_at": now(),
				"next_action_at": None,
				"stop_reason": "",
			},
			update_modified=True,
		)
		_sync_lead_state(enrollment, state="Stopped", contacted_at=activity.sent_at)
		return
	next_step = sequence.steps[completed_steps]
	next_at = next_action_at(get_datetime(activity.sent_at), next_step.delay_days, now=now_datetime())
	enrollment.db_set(
		{
			"current_step": completed_steps,
			"status": "Active",
			"next_action_at": next_at,
			"stop_reason": "",
		},
		update_modified=True,
	)
	enrollment.reload()
	_sync_lead_state(enrollment, state="Contacting", contacted_at=activity.sent_at)


def _sync_lead_state(enrollment, *, state: str, contacted_at=None) -> None:
	if not enrollment.lead or not frappe.db.exists("CRM Lead", enrollment.lead):
		return
	meta = frappe.get_meta("CRM Lead")
	values = {}
	if meta.has_field("ai_sdr_state"):
		values["ai_sdr_state"] = state
	if contacted_at and meta.has_field("ai_sdr_last_contacted_at"):
		values["ai_sdr_last_contacted_at"] = contacted_at
	if meta.has_field("ai_sdr_next_action_at"):
		values["ai_sdr_next_action_at"] = enrollment.next_action_at
	if values:
		frappe.db.set_value("CRM Lead", enrollment.lead, values)


def is_suppressed(
	*,
	email: str | None = None,
	domain: str | None = None,
	lead: str | None = None,
	organization: str | None = None,
) -> bool:
	candidates = suppression_candidates(
		email=email,
		lead=lead,
		organization=organization,
	)
	normalized_domain = normalize_domain(domain)
	if normalized_domain and ("Domain", normalized_domain) not in candidates:
		candidates.append(("Domain", normalized_domain))
	for suppression_type, key in candidates:
		names = frappe.get_all(
			"AI SDR Suppression",
			filters={
				"suppression_type": suppression_type,
				"suppression_key": key,
				"active": 1,
			},
			fields=["name", "expires_on"],
			limit=10,
		)
		if any(not row.expires_on or getdate(row.expires_on) >= getdate(nowdate()) for row in names):
			return True
	return False


def ensure_suppression(
	suppression_type: str,
	key: str,
	*,
	reason: str,
	source: str,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	notes: str | None = None,
) -> str:
	normalized = normalize_suppression_key(suppression_type, key)
	deduplication_key = f"{suppression_type}:{normalized.casefold()}"
	name = frappe.db.exists("AI SDR Suppression", {"deduplication_key": deduplication_key})
	if name:
		doc = frappe.get_doc("AI SDR Suppression", name)
		doc.update(
			{
				"active": 1,
				"reason": reason,
				"source": source,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"notes": notes,
			}
		)
		doc.save(ignore_permissions=True)
		return doc.name
	return (
		frappe.get_doc(
			{
				"doctype": "AI SDR Suppression",
				"suppression_type": suppression_type,
				"suppression_key": normalized,
				"reason": reason,
				"source": source,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"notes": notes,
				"active": 1,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def stop_enrollment(enrollment, reason: str) -> None:
	enrollment.db_set(
		{
			"status": "Stopped",
			"completed_at": now(),
			"next_action_at": None,
			"paused_until": None,
			"stop_reason": reason[:500],
		},
		update_modified=True,
	)
	enrollment.reload()
	_sync_lead_state(enrollment, state="Stopped")


def stop_enrollments_for_deal(doc, method: str | None = None) -> None:
	lead = doc.get("lead")
	if not lead:
		return
	for name in frappe.get_all(
		"AI SDR Enrollment",
		filters={"lead": lead, "status": ["in", list(ACTIVE_STATUSES)]},
		pluck="name",
	):
		stop_enrollment(frappe.get_doc("AI SDR Enrollment", name), f"CRM Deal {doc.name} was created.")


def _lead_from_communication(doc) -> str | None:
	if doc.reference_doctype == "CRM Lead":
		return doc.reference_name
	if doc.reference_doctype == "CRM Deal" and doc.reference_name:
		return frappe.db.get_value("CRM Deal", doc.reference_name, "lead")
	return None


def handle_received_communication(doc, method: str | None = None) -> None:
	if (
		doc.get("sent_or_received") != "Received"
		or doc.get("communication_medium") != "Email"
		or doc.get("reference_doctype") not in {"CRM Lead", "CRM Deal"}
	):
		return
	lead_name = _lead_from_communication(doc)
	if not lead_name:
		return
	enrollment_names = frappe.get_all(
		"AI SDR Enrollment",
		filters={"lead": lead_name, "status": ["in", list(ACTIVE_STATUSES)]},
		pluck="name",
		order_by="modified desc",
	)
	if not enrollment_names:
		return
	idempotency_key = f"communication:{doc.name}"
	if frappe.db.exists("AI SDR Activity", {"idempotency_key": idempotency_key}):
		return
	enrollment = frappe.get_doc("AI SDR Enrollment", enrollment_names[0])
	classification = classify_reply_fallback(doc.get("subject"), doc.get("content"))
	activity = frappe.get_doc(
		{
			"doctype": "AI SDR Activity",
			"enrollment": enrollment.name,
			"sequence": enrollment.sequence,
			"lead": lead_name,
			"organization": enrollment.organization,
			"assigned_to": enrollment.assigned_to,
			"activity_type": "Reply",
			"channel": "Email",
			"direction": "Inbound",
			"status": "Received",
			"recipient_name": doc.get("sender_full_name"),
			"recipient_email": doc.get("sender"),
			"subject": doc.get("subject"),
			"body": doc.get("content"),
			"communication": doc.name,
			"idempotency_key": idempotency_key,
			"reply_classification": classification.category,
			"reply_confidence": classification.confidence,
			"classification_reason": classification.reason,
		}
	).insert(ignore_permissions=True)
	_apply_reply_classification(activity, enrollment, classification)
	for enrollment_name in enrollment_names[1:]:
		other_enrollment = frappe.get_doc("AI SDR Enrollment", enrollment_name)
		if classification.category == REPLY_OUT_OF_OFFICE:
			_pause_enrollment(other_enrollment, "Out-of-office reply received.", days=7)
		elif classification.category == REPLY_NOT_NOW:
			_pause_enrollment(other_enrollment, "Prospect asked to revisit later.", days=30)
		else:
			stop_enrollment(
				other_enrollment,
				f"Reply received in {activity.name}; another active enrollment was stopped.",
			)
	if classification.category != REPLY_UNSUBSCRIBE and ai_is_configured():
		frappe.enqueue(
			"loopjet_frappe_custom.ai_sdr.services.classify_reply",
			activity_name=activity.name,
			queue="long",
			enqueue_after_commit=True,
		)


def classify_reply(activity_name: str) -> str:
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.direction != "Inbound" or activity.activity_type != "Reply":
		return activity.name
	if activity.reply_classification == REPLY_UNSUBSCRIBE:
		return activity.name
	settings = get_settings()
	if not ai_is_configured(settings):
		return activity.name
	system_prompt, user_prompt = reply_messages(
		{
			"subject": activity.subject,
			"body": activity.body,
			"sender": activity.recipient_email,
		}
	)
	try:
		result, usage = _complete_with_settings(settings, system_prompt, user_prompt)
		classification = validate_reply_result(result)
		activity.update(
			{
				"reply_classification": classification.category,
				"reply_confidence": classification.confidence,
				"classification_reason": classification.reason,
				"ai_provider": _provider_name(settings),
				"ai_model": settings.ai_model,
				"prompt_version": REPLY_PROMPT_VERSION,
				"prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens") or 0,
				"completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens") or 0,
				"last_error": "",
			}
		)
		activity.save(ignore_permissions=True)
		if activity.enrollment:
			_apply_reply_classification(
				activity,
				frappe.get_doc("AI SDR Enrollment", activity.enrollment),
				classification,
			)
		return activity.name
	except Exception as exc:
		activity.db_set({"last_error": str(exc)[:1000]}, update_modified=True)
		frappe.log_error(frappe.get_traceback(), f"AI SDR reply classification failed: {activity.name}")
		raise


def _apply_reply_classification(activity, enrollment, classification) -> None:
	category = classification.category
	if category == REPLY_UNSUBSCRIBE:
		if activity.recipient_email:
			ensure_suppression(
				"Email",
				activity.recipient_email,
				reason="Unsubscribe",
				source="Inbound Reply",
				reference_doctype="Communication",
				reference_name=activity.communication,
				notes=classification.reason,
			)
		stop_enrollment(enrollment, f"Unsubscribe reply received in {activity.name}.")
	elif category == REPLY_NOT_INTERESTED:
		ensure_suppression(
			"Lead",
			activity.lead,
			reason="Not Interested",
			source="Inbound Reply",
			reference_doctype="Communication",
			reference_name=activity.communication,
			notes=classification.reason,
		)
		stop_enrollment(enrollment, f"Not-interested reply received in {activity.name}.")
	elif category == REPLY_OUT_OF_OFFICE:
		_pause_enrollment(enrollment, "Out-of-office reply received.", days=7)
	elif category == REPLY_NOT_NOW:
		_pause_enrollment(enrollment, "Prospect asked to revisit later.", days=30)
	else:
		sequence = frappe.get_doc("AI SDR Sequence", enrollment.sequence)
		if sequence.stop_on_reply:
			stop_enrollment(enrollment, f"Reply received in {activity.name}; human follow-up required.")
		else:
			_pause_enrollment(enrollment, "Reply received; human review required.")
		if category in REVIEW_TASK_CATEGORIES:
			ensure_reply_task(activity, category)
	_sync_lead_reply_state(activity.lead, category)


def _pause_enrollment(enrollment, reason: str, days: int | None = None) -> None:
	enrollment.db_set(
		{
			"status": "Paused",
			"paused_until": add_days(now_datetime(), days) if days else None,
			"next_action_at": None,
			"stop_reason": reason,
		},
		update_modified=True,
	)


def _sync_lead_reply_state(lead_name: str | None, category: str) -> None:
	if not lead_name or not frappe.db.exists("CRM Lead", lead_name):
		return
	meta = frappe.get_meta("CRM Lead")
	values = {}
	if meta.has_field("ai_sdr_state"):
		values["ai_sdr_state"] = "Nurture" if category in {REPLY_NOT_NOW, REPLY_OUT_OF_OFFICE} else "Replied"
	if meta.has_field("ai_sdr_next_action_at"):
		values["ai_sdr_next_action_at"] = None
	if values:
		frappe.db.set_value("CRM Lead", lead_name, values)


def ensure_reply_task(activity, category: str) -> str | None:
	if not frappe.db.exists("DocType", "CRM Task"):
		return None
	title = f"Review AI SDR reply: {category}"
	existing = frappe.db.exists(
		"CRM Task",
		{
			"title": title,
			"reference_doctype": "CRM Lead",
			"reference_docname": activity.lead,
			"status": ["not in", ["Done", "Canceled"]],
		},
	)
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": title,
				"priority": "High" if category == REPLY_INTERESTED else "Medium",
				"assigned_to": activity.assigned_to or frappe.session.user,
				"status": "Todo",
				"due_date": now(),
				"description": (
					f"Review inbound Communication {activity.communication}. "
					f"Classification: {category}. Reason: {activity.classification_reason or ''}"
				),
				"reference_doctype": "CRM Lead",
				"reference_docname": activity.lead,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)
