"""Narrow, API-key-friendly prospect operations for the Loopjet AI SDR.

The dedicated ``AI SDR Agent`` role has no generic CRM DocType permissions.
These whitelisted methods are its deliberately bounded write surface.
"""

from __future__ import annotations

import json
from datetime import date
from html import escape
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime, now, now_datetime, validate_email_address

from loopjet_frappe_custom.ai_sdr.domain import (
	canonical_company_website,
	icp_tier,
	normalize_company_domain,
	normalize_email,
	normalize_outbound_icp_score,
	split_person_name,
	validate_source_urls,
)
from loopjet_frappe_custom.ai_sdr.permissions import require_agent_api_access
from loopjet_frappe_custom.ai_sdr.services import is_suppressed

EMPLOYEE_RANGES = {"1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"}
CALL_STATUSES = {
	"New",
	"Researched",
	"Receptionist",
	"Contact Identified",
	"No Answer",
	"Connected",
	"Follow-up",
	"Qualified",
	"Rejected",
}
TERMINAL_CALL_STATUSES = {"Qualified", "Rejected"}
ACADEMY_TAG = "Learnlayer Academy"
ACADEMY_OUTBOUND_EVENT_PREFIX = "[Academy outbound |"
ACADEMY_OUTBOUND_EVENTS = {
	"reserved",
	"blocked",
	"provider_error",
	"provider_accepted",
	"sent",
	"delivered",
	"delivery_delayed",
	"bounced",
	"complained",
	"failed",
	"suppressed",
	"reply",
	"opt_out",
}
ACADEMY_SUPPRESSION_SCOPES = {"", "email", "global"}
ACADEMY_PROVIDER_OUTCOMES = {
	"provider_accepted": ("Accepted", "Accepted"),
	"sent": ("Sent", "Sent"),
	"delivered": ("Delivered", "Sent"),
	"delivery_delayed": ("Delivery Delayed", "Accepted"),
	"bounced": ("Bounced", "Failed"),
	"complained": ("Complained", "Failed"),
	"failed": ("Failed", "Failed"),
	"suppressed": ("Suppressed", "Failed"),
}


def _clean(value: Any, *, maximum: int = 1000) -> str:
	text = str(value or "").strip()
	if len(text) > maximum:
		frappe.throw(_("A supplied value exceeds the maximum length of {0} characters.").format(maximum))
	return text


def _plain_text_html(value: str) -> str:
	return f"<p>{escape(value).replace(chr(10), '<br>')}</p>" if value else ""


def _source_urls(value: Any) -> list[str]:
	if not value:
		return []
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
		except json.JSONDecodeError:
			parsed = value.splitlines()
		value = parsed if isinstance(parsed, list) else [parsed]
	return validate_source_urls(list(value) if isinstance(value, (list, tuple)) else [value])


def _meta_has(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _supported_values(doctype: str, values: dict[str, Any]) -> dict[str, Any]:
	meta = frappe.get_meta(doctype)
	return {fieldname: value for fieldname, value in values.items() if meta.has_field(fieldname)}


def _validate_link(doctype: str, value: str, label: str) -> str:
	if value and not frappe.db.exists(doctype, value):
		frappe.throw(_("Unknown {0}: {1}").format(label, value))
	return value


def _validate_employee_range(value: str) -> str:
	if value and value not in EMPLOYEE_RANGES:
		frappe.throw(_("No. of Employees must be one of: {0}").format(", ".join(sorted(EMPLOYEE_RANGES))))
	return value


def _validated_email(value: Any) -> str:
	email = normalize_email(_clean(value, maximum=320))
	if email:
		validate_email_address(email, throw=True)
	return email


def _new_lead_status() -> str | None:
	if frappe.db.exists("CRM Lead Status", "New"):
		return "New"
	return frappe.db.get_value("CRM Lead Status", {"type": "Open"}, "name")


def _organization_name_for_lead(lead) -> str | None:
	organization = lead.get("ai_sdr_organization") or lead.get("organization")
	if not organization:
		return None
	if frappe.db.exists("CRM Organization", organization):
		return organization
	return frappe.db.get_value("CRM Organization", {"organization_name": organization}, "name")


def _find_organization(*, domain: str = "", company_name: str = "") -> str | None:
	if domain and _meta_has("CRM Organization", "ai_sdr_company_domain"):
		name = frappe.db.get_value("CRM Organization", {"ai_sdr_company_domain": domain}, "name")
		if name:
			return name
	if domain:
		# Also protect organizations created before the normalized-domain field
		# existed. The final Python comparison avoids substring false positives.
		for row in frappe.get_all(
			"CRM Organization",
			filters={"website": ["like", f"%{domain}%"]},
			fields=["name", "website"],
			limit_page_length=100,
		):
			if normalize_company_domain(row.get("website")) == domain:
				return row.name
	if company_name:
		return frappe.db.get_value("CRM Organization", {"organization_name": company_name}, "name")
	return None


def _lead_names_for_organization(organization: str) -> list[str]:
	names: list[str] = []
	if _meta_has("CRM Lead", "ai_sdr_organization"):
		names.extend(
			frappe.get_all(
				"CRM Lead",
				filters={"ai_sdr_organization": organization},
				pluck="name",
				limit_page_length=100,
			)
		)
	for name in frappe.get_all(
		"CRM Lead",
		filters={"organization": organization},
		pluck="name",
		limit_page_length=100,
	):
		if name not in names:
			names.append(name)
	return names


def _latest_research(organization: str | None):
	if not organization:
		return None
	names = frappe.get_all(
		"AI SDR Research",
		filters={"organization": organization},
		pluck="name",
		order_by="modified desc",
		limit_page_length=1,
	)
	return frappe.get_doc("AI SDR Research", names[0]) if names else None


def _organization_payload(name: str | None) -> dict[str, Any] | None:
	if not name or not frappe.db.exists("CRM Organization", name):
		return None
	doc = frappe.get_doc("CRM Organization", name)
	return {
		"name": doc.name,
		"company_name": doc.get("organization_name"),
		"website": doc.get("website"),
		"company_domain": doc.get("ai_sdr_company_domain") or normalize_company_domain(doc.get("website")),
		"phone": doc.get("ai_sdr_phone"),
		"country": doc.get("ai_sdr_country"),
		"industry": doc.get("industry"),
		"no_of_employees": doc.get("no_of_employees"),
		"linkedin_url": doc.get("ai_sdr_linkedin_url"),
		"icp_score": doc.get("ai_sdr_icp_score"),
		"icp_tier": doc.get("ai_sdr_icp_tier"),
	}


def _lead_payload(name: str) -> dict[str, Any]:
	doc = frappe.get_doc("CRM Lead", name)
	return {
		"name": doc.name,
		"lead_name": doc.get("lead_name"),
		"first_name": doc.get("first_name"),
		"last_name": doc.get("last_name"),
		"email": doc.get("email"),
		"phone": doc.get("phone"),
		"mobile_no": doc.get("mobile_no"),
		"organization": _organization_name_for_lead(doc),
		"linkedin_url": doc.get("ai_sdr_linkedin_url"),
		"company_lead": bool(doc.get("ai_sdr_is_company_lead")),
		"call_status": doc.get("ai_sdr_call_status"),
		"next_call_at": doc.get("ai_sdr_next_call_at"),
		"do_not_contact": bool(doc.get("ai_sdr_do_not_contact")),
	}


def _academy_tags(lead) -> set[str]:
	return {tag.strip() for tag in _clean(lead.get("_user_tags"), maximum=2000).split(",") if tag.strip()}


def _academy_lead(name: str):
	name = _clean(name, maximum=140)
	if not name or not frappe.db.exists("CRM Lead", name):
		frappe.throw(_("Unknown CRM Lead."))
	lead = frappe.get_doc("CRM Lead", name)
	if ACADEMY_TAG not in _academy_tags(lead):
		frappe.throw(_("The CRM Lead is not in the LearnLayer Academy motion."), frappe.PermissionError)
	return lead


def _academy_lead_payload(lead) -> dict[str, Any]:
	return {
		"name": lead.name,
		"lead_name": lead.get("lead_name"),
		"first_name": lead.get("first_name"),
		"last_name": lead.get("last_name"),
		"email": lead.get("email"),
		"phone": lead.get("phone"),
		"mobile_no": lead.get("mobile_no"),
		"organization": _organization_name_for_lead(lead),
		"website": lead.get("website"),
		"job_title": lead.get("job_title"),
		"status": lead.get("status"),
		"_user_tags": lead.get("_user_tags"),
		"ai_sdr_do_not_contact": bool(lead.get("ai_sdr_do_not_contact")),
		"ai_sdr_call_status": lead.get("ai_sdr_call_status"),
	}


def _academy_event(note: str) -> str:
	if not note.startswith(ACADEMY_OUTBOUND_EVENT_PREFIX):
		frappe.throw(_("Academy outbound notes must start with the canonical event marker."))
	for line in note.splitlines():
		key, separator, value = line.partition(":")
		if separator and key.strip().casefold() == "academy_outbound_event":
			event = value.strip().casefold()
			if event not in ACADEMY_OUTBOUND_EVENTS:
				frappe.throw(_("Unsupported Academy outbound event."))
			return event
	frappe.throw(_("Academy outbound event is required."))


def _academy_marker(note: str, fieldname: str) -> str:
	for line in note.splitlines():
		key, separator, value = line.partition(":")
		if separator and key.strip().casefold() == fieldname.casefold():
			return value.strip()
	return ""


def _update_academy_manual_activity(lead: str, note: str, event: str) -> None:
	activity_name = _academy_marker(note, "academy_manual_activity")
	if not activity_name:
		return
	if not activity_name.startswith("SDR-ACT-") or len(activity_name) > 40:
		frappe.throw(_("Invalid Academy manual activity marker."))
	if not frappe.db.exists("AI SDR Activity", activity_name):
		frappe.throw(_("Unknown Academy manual activity."))
	activity = frappe.get_doc("AI SDR Activity", activity_name)
	if activity.lead != lead or activity.prompt_version != "academy-manual-v1":
		frappe.throw(_("Academy manual activity does not match the CRM Lead."))

	provider_id = _academy_marker(note, "resend_email_id")
	if activity.provider_message_id and provider_id and activity.provider_message_id != provider_id:
		frappe.throw(_("Academy provider message ID does not match the activity audit."))
	values: dict[str, Any] = {}
	if provider_id:
		values["provider_message_id"] = provider_id[:140]
	if event in ACADEMY_PROVIDER_OUTCOMES:
		provider_outcome, status = ACADEMY_PROVIDER_OUTCOMES[event]
		values.update({"provider_outcome": provider_outcome, "status": status})
		if event == "provider_accepted" and not activity.sent_at:
			values["sent_at"] = now()
	if event in {"bounced", "complained", "failed", "suppressed"}:
		values["last_error"] = (_academy_marker(note, "academy_provider_error") or event)[:1000]
	elif event in {"provider_accepted", "sent", "delivered"}:
		values["last_error"] = ""
	if values:
		activity.db_set(values, update_modified=True)


def _academy_comment(lead: str, note: str):
	return frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "CRM Lead",
			"reference_name": lead,
			"content": note,
		}
	).insert(ignore_permissions=True)


def _find_duplicate(
	*, domain: str = "", email: str = "", company_name: str = ""
) -> tuple[str | None, str | None, str | None]:
	if domain:
		organization = _find_organization(domain=domain)
		if organization:
			leads = _lead_names_for_organization(organization)
			return "duplicate_domain", organization, leads[0] if leads else None
	if email:
		lead = frappe.db.get_value("CRM Lead", {"email": email}, "name")
		if lead:
			doc = frappe.get_doc("CRM Lead", lead)
			return "duplicate_email", _organization_name_for_lead(doc), lead
	if company_name:
		organization = _find_organization(company_name=company_name)
		if organization:
			leads = _lead_names_for_organization(organization)
			return "duplicate_company", organization, leads[0] if leads else None
	return None, None, None


@frappe.whitelist(methods=["GET"])
def search_lead(
	domain: str | None = None,
	email: str | None = None,
	company_name: str | None = None,
) -> dict[str, Any]:
	"""Find an outbound prospect by normalized domain, email, or company name."""
	require_agent_api_access()
	normalized_domain = normalize_company_domain(domain)
	normalized_email = _validated_email(email)
	company_name = _clean(company_name, maximum=140)
	if not any((normalized_domain, normalized_email, company_name)):
		frappe.throw(_("Provide a domain, email, or company_name."))
	reason, organization, lead = _find_duplicate(
		domain=normalized_domain,
		email=normalized_email,
		company_name=company_name,
	)
	leads = _lead_names_for_organization(organization) if organization else ([lead] if lead else [])
	return {
		"found": bool(reason),
		"matched_by": reason.removeprefix("duplicate_") if reason else None,
		"organization": _organization_payload(organization),
		"leads": [_lead_payload(name) for name in leads],
	}


@frappe.whitelist(methods=["POST"])
def create_outbound_lead(
	company_name: str,
	website: str | None = None,
	company_domain: str | None = None,
	phone: str | None = None,
	email: str | None = None,
	country: str | None = None,
	industry: str | None = None,
	no_of_employees: str | None = None,
	linkedin_url: str | None = None,
	research_notes: str | None = None,
	sales_reason: str | None = None,
	icp_score: int | float | str | None = None,
	source_urls: list[str] | str | None = None,
	contact_name: str | None = None,
	contact_linkedin_url: str | None = None,
	job_title: str | None = None,
	lead_owner: str | None = None,
	next_call_at: str | None = None,
) -> dict[str, Any]:
	"""Create one deduplicated CRM Organization, CRM Lead, and research record."""
	require_agent_api_access()
	company_name = _clean(company_name, maximum=140)
	if not company_name:
		frappe.throw(_("Company Name is required."))
	domain = normalize_company_domain(company_domain or website or email)
	if not domain:
		frappe.throw(_("A valid company_domain, website, or company email is required."))
	website = canonical_company_website(website or domain)
	email = _validated_email(email)
	phone = _clean(phone, maximum=50)
	country = _validate_link("Country", _clean(country, maximum=140), "country")
	industry = _validate_link("CRM Industry", _clean(industry, maximum=140), "industry")
	no_of_employees = _validate_employee_range(_clean(no_of_employees, maximum=20))
	linkedin_url = _clean(linkedin_url, maximum=500)
	contact_linkedin_url = _clean(contact_linkedin_url, maximum=500)
	research_notes = _clean(research_notes, maximum=10000)
	sales_reason = _clean(sales_reason, maximum=10000)
	job_title = _clean(job_title, maximum=140)
	lead_owner = _validate_link("User", _clean(lead_owner, maximum=140), "lead owner")
	urls = _source_urls(source_urls)

	reason, organization, lead = _find_duplicate(
		domain=domain,
		email=email,
		company_name=company_name,
	)
	if reason:
		return {
			"created": False,
			"reason": reason,
			"organization": _organization_payload(organization),
			"lead": _lead_payload(lead) if lead else None,
		}

	has_score = icp_score is not None and str(icp_score).strip() != ""
	score = normalize_outbound_icp_score(icp_score) if has_score else 0
	ready = bool(research_notes or sales_reason or urls or has_score)
	organization_values = {
		"doctype": "CRM Organization",
		"organization_name": company_name,
		"website": website,
		"industry": industry or None,
		"no_of_employees": no_of_employees or None,
		**_supported_values(
			"CRM Organization",
			{
				"ai_sdr_company_domain": domain,
				"ai_sdr_linkedin_url": linkedin_url,
				"ai_sdr_phone": phone,
				"ai_sdr_country": country,
				"ai_sdr_research_notes": research_notes,
				"ai_sdr_sales_reason": _plain_text_html(sales_reason),
				"ai_sdr_research_agent": frappe.session.user,
				"ai_sdr_research_status": "Ready" if ready else "Draft",
				"ai_sdr_icp_score": score,
				"ai_sdr_icp_tier": icp_tier(score),
				"ai_sdr_last_researched_at": now() if ready else None,
			},
		),
	}
	frappe.db.savepoint("ai_sdr_outbound_create")
	try:
		organization_doc = frappe.get_doc(organization_values).insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		frappe.db.rollback(save_point="ai_sdr_outbound_create")
		reason, organization, lead = _find_duplicate(
			domain=domain,
			email=email,
			company_name=company_name,
		)
		if not reason:
			raise
		return {
			"created": False,
			"reason": reason,
			"organization": _organization_payload(organization),
			"lead": _lead_payload(lead) if lead else None,
		}
	else:
		frappe.db.release_savepoint("ai_sdr_outbound_create")

	first_name, last_name = split_person_name(contact_name)
	company_lead = not bool(first_name)
	first_name = first_name or company_name
	lead_doc = frappe.get_doc(
		{
			"doctype": "CRM Lead",
			"first_name": first_name,
			"last_name": last_name,
			"organization": organization_doc.name,
			"website": website,
			"phone": phone,
			"email": email,
			"industry": industry or None,
			"no_of_employees": no_of_employees or None,
			"job_title": job_title,
			"lead_owner": lead_owner or None,
			"status": _new_lead_status(),
			**_supported_values(
				"CRM Lead",
				{
					"ai_sdr_organization": organization_doc.name,
					"ai_sdr_linkedin_url": "" if company_lead else contact_linkedin_url,
					"ai_sdr_state": "Ready" if ready else "New",
					"ai_sdr_is_company_lead": int(company_lead),
					"ai_sdr_call_status": "Researched" if ready else "New",
					"ai_sdr_next_call_at": get_datetime(next_call_at) if next_call_at else now(),
				},
			),
		}
	).insert(ignore_permissions=True)

	research_doc = frappe.get_doc(
		{
			"doctype": "AI SDR Research",
			"organization": organization_doc.name,
			"assigned_to": lead_owner or frappe.session.user,
			"website": website,
			"linkedin_company_url": linkedin_url,
			"status": "Ready" if ready else "Draft",
			"source_urls": "\n".join(urls),
			"source_evidence": research_notes,
			"company_summary": _plain_text_html(research_notes),
			"outreach_angle": _plain_text_html(sales_reason),
			"fit_score": score,
			"trigger_score": score,
			"persona_score": score,
			"data_quality_score": score,
			"researched_at": now() if ready else None,
			"evidence_json": json.dumps(
				{
					"company_domain": domain,
					"phone": phone,
					"country": country,
					"industry": industry,
					"no_of_employees": no_of_employees,
					"source_urls": urls,
					"research_agent": frappe.session.user,
				},
				sort_keys=True,
			),
		}
	).insert(ignore_permissions=True)

	return {
		"created": True,
		"lead": _lead_payload(lead_doc.name),
		"organization": _organization_payload(organization_doc.name),
		"research": research_doc.name,
	}


@frappe.whitelist(methods=["POST"])
def create_lead(**kwargs) -> dict[str, Any]:
	"""Short alias matching the agent-tool name in the architecture proposal."""
	# Frappe includes the dotted method path as ``cmd`` when the whitelisted
	# function accepts arbitrary keyword arguments. It is transport metadata,
	# not part of the outbound-lead payload.
	kwargs.pop("cmd", None)
	return create_outbound_lead(**kwargs)


@frappe.whitelist(methods=["POST"])
def update_lead(
	lead: str,
	website: str | None = None,
	company_domain: str | None = None,
	phone: str | None = None,
	email: str | None = None,
	country: str | None = None,
	industry: str | None = None,
	no_of_employees: str | None = None,
	linkedin_url: str | None = None,
	research_notes: str | None = None,
	sales_reason: str | None = None,
	icp_score: int | float | str | None = None,
	call_status: str | None = None,
	next_call_at: str | None = None,
	lead_owner: str | None = None,
) -> dict[str, Any]:
	"""Update only the approved outbound-research fields on an existing lead."""
	require_agent_api_access()
	lead_doc = frappe.get_doc("CRM Lead", _clean(lead, maximum=140))
	organization_name = _organization_name_for_lead(lead_doc)
	organization_doc = frappe.get_doc("CRM Organization", organization_name) if organization_name else None
	lead_values: dict[str, Any] = {}
	organization_values: dict[str, Any] = {}
	research_values: dict[str, Any] = {}

	if website is not None or company_domain is not None:
		domain = normalize_company_domain(company_domain or website)
		if not domain:
			frappe.throw(_("A valid company domain is required."))
		other = _find_organization(domain=domain)
		if other and other != organization_name:
			return {"updated": False, "reason": "duplicate_domain", "organization": other}
		canonical_website = canonical_company_website(website or domain)
		lead_values["website"] = canonical_website
		organization_values.update({"website": canonical_website, "ai_sdr_company_domain": domain})
		research_values["website"] = canonical_website
	if phone is not None:
		value = _clean(phone, maximum=50)
		lead_values["phone"] = value
		organization_values["ai_sdr_phone"] = value
	if email is not None:
		value = _validated_email(email)
		duplicate = frappe.db.get_value("CRM Lead", {"email": value}, "name") if value else None
		if duplicate and duplicate != lead_doc.name:
			return {"updated": False, "reason": "duplicate_email", "lead": duplicate}
		lead_values["email"] = value
	if country is not None:
		organization_values["ai_sdr_country"] = _validate_link(
			"Country", _clean(country, maximum=140), "country"
		)
	if industry is not None:
		value = _validate_link("CRM Industry", _clean(industry, maximum=140), "industry")
		lead_values["industry"] = value
		organization_values["industry"] = value
	if no_of_employees is not None:
		value = _validate_employee_range(_clean(no_of_employees, maximum=20))
		lead_values["no_of_employees"] = value
		organization_values["no_of_employees"] = value
	if linkedin_url is not None:
		value = _clean(linkedin_url, maximum=500)
		if lead_doc.get("ai_sdr_is_company_lead"):
			organization_values["ai_sdr_linkedin_url"] = value
			research_values["linkedin_company_url"] = value
		else:
			lead_values["ai_sdr_linkedin_url"] = value
	if research_notes is not None:
		value = _clean(research_notes, maximum=10000)
		organization_values["ai_sdr_research_notes"] = value
		research_values.update({"source_evidence": value, "company_summary": _plain_text_html(value)})
	if sales_reason is not None:
		value = _clean(sales_reason, maximum=10000)
		organization_values["ai_sdr_sales_reason"] = _plain_text_html(value)
		research_values["outreach_angle"] = _plain_text_html(value)
	if icp_score is not None and str(icp_score).strip() != "":
		score = normalize_outbound_icp_score(icp_score)
		organization_values.update({"ai_sdr_icp_score": score, "ai_sdr_icp_tier": icp_tier(score)})
		research_values.update(
			{
				"fit_score": score,
				"trigger_score": score,
				"persona_score": score,
				"data_quality_score": score,
			}
		)
	if call_status is not None:
		value = _clean(call_status, maximum=30)
		if value not in CALL_STATUSES:
			frappe.throw(_("Unsupported outbound call status: {0}").format(value))
		lead_values["ai_sdr_call_status"] = value
	if next_call_at is not None:
		lead_values["ai_sdr_next_call_at"] = get_datetime(next_call_at) if next_call_at else None
	if lead_owner is not None:
		lead_values["lead_owner"] = _validate_link("User", _clean(lead_owner, maximum=140), "lead owner")

	lead_doc.update(_supported_values("CRM Lead", lead_values))
	lead_doc.save(ignore_permissions=True)
	if organization_doc:
		organization_values["ai_sdr_research_agent"] = frappe.session.user
		if research_values:
			organization_values.update(
				{"ai_sdr_research_status": "Ready", "ai_sdr_last_researched_at": now()}
			)
		organization_doc.update(_supported_values("CRM Organization", organization_values))
		organization_doc.save(ignore_permissions=True)
	research = _latest_research(organization_name)
	if research_values and organization_name:
		if research:
			research.update(research_values)
			research.status = "Ready"
			research.researched_at = now()
			research.save(ignore_permissions=True)
		else:
			research = frappe.get_doc(
				{
					"doctype": "AI SDR Research",
					"organization": organization_name,
					"assigned_to": lead_doc.get("lead_owner") or frappe.session.user,
					"website": organization_doc.get("website") if organization_doc else "",
					"linkedin_company_url": organization_doc.get("ai_sdr_linkedin_url")
					if organization_doc
					else "",
					"status": "Ready",
					"researched_at": now(),
					**research_values,
				}
			).insert(ignore_permissions=True)
	return {
		"updated": True,
		"lead": _lead_payload(lead_doc.name),
		"organization": _organization_payload(organization_name),
		"research": research.name if research else None,
	}


@frappe.whitelist(methods=["POST"])
def add_contact_person(
	first_name: str,
	lead: str | None = None,
	organization: str | None = None,
	last_name: str | None = None,
	email: str | None = None,
	phone: str | None = None,
	mobile_no: str | None = None,
	job_title: str | None = None,
	linkedin_url: str | None = None,
) -> dict[str, Any]:
	"""Replace a company placeholder or add another CRM Lead contact person."""
	require_agent_api_access()
	first_name = _clean(first_name, maximum=140)
	if not first_name:
		frappe.throw(_("First Name is required."))
	last_name = _clean(last_name, maximum=140)
	email = _validated_email(email)
	phone = _clean(phone, maximum=50)
	mobile_no = _clean(mobile_no, maximum=50)
	job_title = _clean(job_title, maximum=140)
	linkedin_url = _clean(linkedin_url, maximum=500)
	lead_doc = frappe.get_doc("CRM Lead", _clean(lead, maximum=140)) if lead else None
	organization_name = _clean(organization, maximum=140) or (
		_organization_name_for_lead(lead_doc) if lead_doc else None
	)
	if not organization_name or not frappe.db.exists("CRM Organization", organization_name):
		frappe.throw(_("A valid CRM Organization or lead is required."))
	if email:
		duplicate = frappe.db.get_value("CRM Lead", {"email": email}, "name")
		if duplicate and (not lead_doc or duplicate != lead_doc.name):
			return {"created": False, "reason": "duplicate_email", "lead": _lead_payload(duplicate)}

	values = {
		"first_name": first_name,
		"last_name": last_name,
		"email": email,
		"phone": phone,
		"mobile_no": mobile_no,
		"job_title": job_title,
		"organization": organization_name,
		"status": _new_lead_status(),
		"ai_sdr_organization": organization_name,
		"ai_sdr_linkedin_url": linkedin_url,
		"ai_sdr_is_company_lead": 0,
		"ai_sdr_state": "Ready",
		"ai_sdr_call_status": "Contact Identified",
		"ai_sdr_next_call_at": now(),
	}
	updated_placeholder = bool(lead_doc and lead_doc.get("ai_sdr_is_company_lead"))
	if updated_placeholder:
		lead_doc.update(_supported_values("CRM Lead", values))
		lead_doc.save(ignore_permissions=True)
	else:
		organization_doc = frappe.get_doc("CRM Organization", organization_name)
		values.update(
			{
				"doctype": "CRM Lead",
				"website": organization_doc.get("website"),
				"industry": organization_doc.get("industry"),
				"no_of_employees": organization_doc.get("no_of_employees"),
			}
		)
		lead_doc = frappe.get_doc(values).insert(ignore_permissions=True)
	return {
		"created": not updated_placeholder,
		"updated_placeholder": updated_placeholder,
		"lead": _lead_payload(lead_doc.name),
		"organization": _organization_payload(organization_name),
	}


def _call_status(outcome: str) -> str:
	aliases = {
		"reception": "Receptionist",
		"receptionist": "Receptionist",
		"contact identified": "Contact Identified",
		"no answer": "No Answer",
		"connected": "Connected",
		"follow-up": "Follow-up",
		"follow up": "Follow-up",
		"qualified": "Qualified",
		"not interested": "Rejected",
		"rejected": "Rejected",
	}
	return aliases.get(outcome.casefold(), "Connected")


@frappe.whitelist(methods=["POST"])
def add_call_note(
	lead: str,
	note: str,
	outcome: str | None = None,
	next_call_at: str | None = None,
) -> dict[str, Any]:
	"""Record a reviewed call result in the CRM timeline and schedule follow-up."""
	require_agent_api_access()
	lead_doc = frappe.get_doc("CRM Lead", _clean(lead, maximum=140))
	note = _clean(note, maximum=10000)
	if not note:
		frappe.throw(_("Call Note is required."))
	outcome = _clean(outcome, maximum=140) or "Connected"
	call_status = _call_status(outcome)
	timestamp = now()
	next_call = get_datetime(next_call_at) if next_call_at else None
	note_doc = frappe.get_doc(
		{
			"doctype": "FCRM Note",
			"title": f"Call: {outcome}"[:140],
			"content": _plain_text_html(note),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_doc.name,
		}
	).insert(ignore_permissions=True)
	lead_values = {
		"ai_sdr_call_status": call_status,
		"ai_sdr_last_call_outcome": outcome,
		"ai_sdr_last_call_at": timestamp,
		"ai_sdr_next_call_at": next_call,
		"ai_sdr_last_contacted_at": timestamp,
		"ai_sdr_state": "Stopped" if call_status in TERMINAL_CALL_STATUSES else "Contacting",
	}
	if call_status == "Qualified" and frappe.db.exists("CRM Lead Status", "Qualified"):
		lead_values["status"] = "Qualified"
	elif call_status == "Rejected" and frappe.db.exists("CRM Lead Status", "Unqualified"):
		lead_values["status"] = "Unqualified"
	elif call_status in {"Connected", "Follow-up"} and frappe.db.exists("CRM Lead Status", "Contacted"):
		lead_values["status"] = "Contacted"
	lead_doc.update(_supported_values("CRM Lead", lead_values))
	lead_doc.save(ignore_permissions=True)

	task = None
	if next_call and frappe.db.exists("DocType", "CRM Task"):
		task_values = {
			"doctype": "CRM Task",
			"title": f"Call {lead_doc.get('lead_name') or lead_doc.name}"[:140],
			"priority": "Medium",
			"status": "Todo",
			"start_date": next_call.date(),
			"due_date": next_call,
			"assigned_to": lead_doc.get("lead_owner") or None,
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_doc.name,
			"description": f"Follow up after call outcome: {escape(outcome)}",
		}
		task = frappe.get_doc(task_values).insert(ignore_permissions=True).name
	return {
		"created": True,
		"note": note_doc.name,
		"task": task,
		"lead": _lead_payload(lead_doc.name),
	}


@frappe.whitelist(methods=["GET"])
def get_next_call_list(
	limit: int | str = 30,
	as_of: str | None = None,
	assigned_to: str | None = None,
) -> dict[str, Any]:
	"""Return due, non-suppressed leads in deterministic calling order."""
	require_agent_api_access()
	try:
		limit = max(1, min(int(limit), 100))
	except (TypeError, ValueError):
		limit = 30
	cutoff = get_datetime(as_of) if as_of else now_datetime()
	filters: dict[str, Any] = {
		"ai_sdr_next_call_at": ["<=", cutoff],
		"ai_sdr_do_not_contact": 0,
		"ai_sdr_call_status": ["not in", list(TERMINAL_CALL_STATUSES)],
	}
	assigned_to = _clean(assigned_to, maximum=140)
	if assigned_to:
		filters["lead_owner"] = _validate_link("User", assigned_to, "lead owner")
	rows = frappe.get_all(
		"CRM Lead",
		filters=filters,
		fields=[
			"name",
			"lead_name",
			"first_name",
			"last_name",
			"email",
			"phone",
			"mobile_no",
			"job_title",
			"lead_owner",
			"organization",
			"ai_sdr_organization",
			"ai_sdr_linkedin_url",
			"ai_sdr_is_company_lead",
			"ai_sdr_call_status",
			"ai_sdr_last_call_outcome",
			"ai_sdr_last_call_at",
			"ai_sdr_next_call_at",
		],
		order_by="ai_sdr_next_call_at asc, modified asc",
		limit_page_length=limit,
	)
	call_list = []
	for row in rows:
		organization = row.get("ai_sdr_organization") or row.get("organization")
		company = _organization_payload(organization)
		if is_suppressed(
			email=row.get("email"),
			domain=(company or {}).get("company_domain"),
			lead=row.name,
			organization=organization,
		):
			continue
		call_list.append(
			{
				**dict(row),
				"company": company,
			}
		)
	return {"as_of": cutoff, "count": len(call_list), "leads": call_list}


@frappe.whitelist(methods=["GET"])
def get_academy_outbound_context(lead: str) -> dict[str, Any]:
	"""Return one Academy lead and its CRM audit comments to the sender."""
	require_agent_api_access()
	lead_doc = _academy_lead(lead)
	comments = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": "CRM Lead",
			"reference_name": lead_doc.name,
			"comment_type": "Comment",
		},
		fields=["name", "reference_name", "creation", "content"],
		order_by="creation asc",
		limit_page_length=500,
	)
	return {
		"lead": _academy_lead_payload(lead_doc),
		"comments": [dict(comment) for comment in comments],
	}


@frappe.whitelist(methods=["GET"])
def get_academy_outbound_limits(
	organization_key: str,
	business_date: str,
) -> dict[str, Any]:
	"""Return only the Academy audit rows needed for sender rate limits."""
	require_agent_api_access()
	organization_key = normalize_company_domain(organization_key)
	if not organization_key:
		frappe.throw(_("A valid organization_key domain is required."))
	business_date = _clean(business_date, maximum=10)
	try:
		parsed_business_date = date.fromisoformat(business_date)
	except ValueError:
		frappe.throw(_("business_date must use YYYY-MM-DD."))
	if parsed_business_date.isoformat() != business_date:
		frappe.throw(_("business_date must use YYYY-MM-DD."))

	base_filters = {
		"reference_doctype": "CRM Lead",
		"comment_type": "Comment",
	}
	fields = ["name", "reference_name", "creation", "content"]
	organization_comments = frappe.get_all(
		"Comment",
		filters={
			**base_filters,
			"content": ["like", f"%academy_organization_key: {organization_key}%"],
		},
		fields=fields,
		order_by="creation asc",
		limit_page_length=500,
	)
	daily_comments = frappe.get_all(
		"Comment",
		filters={
			**base_filters,
			"content": ["like", f"%academy_business_date: {business_date}%"],
		},
		fields=fields,
		order_by="creation asc",
		limit_page_length=500,
	)
	return {
		"organization_key": organization_key,
		"business_date": business_date,
		"organization_comments": [dict(comment) for comment in organization_comments],
		"daily_comments": [dict(comment) for comment in daily_comments],
	}


@frappe.whitelist(methods=["POST"])
def record_academy_outbound_event(
	lead: str,
	note: str,
	suppression_scope: str | None = None,
) -> dict[str, Any]:
	"""Append a canonical sender event and apply only its bounded suppression."""
	require_agent_api_access()
	lead_doc = _academy_lead(lead)
	note = _clean(note, maximum=10000)
	event = _academy_event(note)
	suppression_scope = _clean(suppression_scope, maximum=20).casefold()
	if suppression_scope not in ACADEMY_SUPPRESSION_SCOPES:
		frappe.throw(_("Unsupported Academy suppression scope."))
	if suppression_scope == "email" and event not in {"bounced", "failed", "suppressed"}:
		frappe.throw(_("Email suppression requires a provider stop event."))
	if suppression_scope == "global" and event not in {"complained", "opt_out"}:
		frappe.throw(_("Global suppression requires a complaint or explicit opt-out."))

	if suppression_scope == "email":
		lead_doc.add_tag("Academy Email Suppression")
		lead_doc.reload()
	elif suppression_scope == "global":
		lead_doc.add_tag("Academy Suppressed")
		lead_values = _supported_values(
			"CRM Lead",
			{
				"ai_sdr_do_not_contact": 1,
				"ai_sdr_call_status": "Rejected",
				"ai_sdr_state": "Stopped",
			},
		)
		if frappe.db.exists("CRM Lead Status", "Unqualified"):
			lead_values["status"] = "Unqualified"
		lead_doc.update(lead_values)
		lead_doc.save(ignore_permissions=True)
		lead_doc.reload()
	elif event == "reply":
		lead_values = _supported_values(
			"CRM Lead",
			{
				"ai_sdr_call_status": "Follow-up",
				"ai_sdr_state": "Contacting",
				"ai_sdr_last_contacted_at": now(),
			},
		)
		if frappe.db.exists("CRM Lead Status", "Contacted"):
			lead_values["status"] = "Contacted"
		lead_doc.update(lead_values)
		lead_doc.save(ignore_permissions=True)
		lead_doc.reload()

	comment = _academy_comment(lead_doc.name, note)
	_update_academy_manual_activity(lead_doc.name, note, event)
	return {
		"created": True,
		"event": event,
		"comment": comment.name,
		"lead": _academy_lead_payload(lead_doc),
	}
