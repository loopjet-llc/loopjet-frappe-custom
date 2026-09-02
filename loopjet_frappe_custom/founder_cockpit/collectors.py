from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from urllib.parse import quote

DEFAULT_SETTINGS = {
	"critical_priority_score": 90,
	"high_priority_score": 75,
	"medium_priority_score": 50,
	"age_boost_days": 7,
	"max_cards": 100,
	"max_records_per_source": 100,
	"lead_stale_days": 5,
	"deal_stale_days": 7,
	"quotation_action_window_days": 3,
	"operational_lookback_hours": 48,
	"repeated_error_threshold": 2,
	"acknowledge_hours": 24,
	"sales_base_score": 76,
	"clients_base_score": 74,
	"finance_base_score": 82,
	"operations_base_score": 84,
	"team_base_score": 72,
	"ignored_error_methods": "Session Stopped\nfrappe.utils.change_log.check_for_update",
}


def settings_snapshot(settings_doc: Any) -> dict[str, Any]:
	settings = dict(DEFAULT_SETTINGS)
	for key in DEFAULT_SETTINGS:
		value = settings_doc.get(key) if settings_doc else None
		if value not in (None, ""):
			settings[key] = value
	return settings


def _limit(settings: dict[str, Any]) -> int:
	return max(20, min(int(settings.get("max_records_per_source") or 100), 500))


def _doctype_available(doctype: str) -> bool:
	import frappe

	return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "read"))


def _available_fields(doctype: str, required: list[str], optional: list[str] | None = None) -> list[str]:
	import frappe

	meta = frappe.get_meta(doctype)
	fields = list(required)
	for fieldname in optional or []:
		if meta.has_field(fieldname):
			fields.append(fieldname)
	return fields


def _safe_list(
	doctype: str,
	coverage: list[dict[str, str]],
	*,
	fields: list[str],
	filters: Any = None,
	order_by: str = "modified desc",
	limit: int = 100,
) -> list[dict[str, Any]]:
	import frappe

	if not _doctype_available(doctype):
		coverage.append({"source": doctype, "status": "unavailable", "reason": "Not installed or not permitted"})
		return []
	try:
		rows = frappe.get_list(
			doctype,
			fields=fields,
			filters=filters,
			order_by=order_by,
			limit_page_length=limit,
		)
	except (frappe.PermissionError, frappe.DoesNotExistError):
		coverage.append({"source": doctype, "status": "unavailable", "reason": "Not permitted"})
		return []
	except Exception:
		frappe.logger("founder_cockpit", allow_site=True).exception("Collector query failed: %s", doctype)
		coverage.append({"source": doctype, "status": "degraded", "reason": "Collector query failed"})
		return []
	coverage.append({"source": doctype, "status": "connected", "reason": "Permission-aware native query"})
	return rows


def _standard_source_url(doctype: str, name: str) -> str:
	custom_routes = {
		"CRM Lead": "/crm/leads/",
		"CRM Deal": "/crm/deals/",
		"HD Ticket": "/helpdesk/tickets/",
	}
	if doctype in custom_routes:
		return custom_routes[doctype] + quote(str(name), safe="")
	return f"/app/{quote(doctype.lower().replace(' ', '-'), safe='-')}/{quote(str(name), safe='')}"


def _candidate(
	*,
	domain: str,
	exception_type: str,
	condition: str,
	source_doctype: str,
	source_name: Any,
	title: Any,
	reason: str,
	recommended_action: str,
	base_score: int,
	needs_decision: bool = False,
	due_at: Any = None,
	occurred_at: Any = None,
	owner: Any = None,
	company: Any = None,
	dedupe_key: str | None = None,
) -> dict[str, Any]:
	name = str(source_name or "")
	return {
		"domain": domain,
		"exception_type": exception_type,
		"condition": condition,
		"source_doctype": source_doctype,
		"source_name": name,
		"title": str(title or f"{source_doctype} {name}")[:180],
		"reason": reason,
		"recommended_action": recommended_action,
		"base_score": base_score,
		"needs_decision": needs_decision,
		"due_at": due_at,
		"occurred_at": occurred_at,
		"owner": owner,
		"company": company,
		"source_url": _standard_source_url(source_doctype, name),
		"dedupe_key": dedupe_key,
	}


def _assigned_user(value: Any) -> str | None:
	if not value:
		return None
	if isinstance(value, list):
		return str(value[0]) if value else None
	try:
		parsed = json.loads(value)
	except (TypeError, json.JSONDecodeError):
		return str(value)
	return str(parsed[0]) if isinstance(parsed, list) and parsed else None


def _helpdesk_ticket_candidate(row: dict[str, Any], client_base: int, today: str) -> dict[str, Any] | None:
	"""Convert each native open-category ticket into a privacy-safe cockpit candidate."""
	status = str(row.get("status") or "Open").strip()
	status_category = str(row.get("status_category") or "").strip()
	if status_category:
		if status_category.casefold() != "open":
			return None
	elif status.casefold() not in {"new", "open"}:
		return None

	priority = str(row.get("priority") or "").strip()
	agreement_status = str(row.get("agreement_status") or "").strip()
	assigned = _assigned_user(row.get("_assign"))
	is_new = status.casefold() == "new"
	sla_failed = agreement_status == "Failed"
	response_due = bool(row.get("response_by") and str(row.get("response_by"))[:10] <= today)
	resolution_due = bool(row.get("resolution_by") and str(row.get("resolution_by"))[:10] <= today)

	reasons = [f"Helpdesk ticket is {status.lower()}"]
	if not assigned:
		reasons.append("no owner is assigned")
	if priority.casefold() in {"high", "urgent", "critical"}:
		reasons.append(f"priority is {priority.lower()}")
	if sla_failed:
		reasons.append("its SLA has failed")
	elif response_due:
		reasons.append("its first-response deadline is due")
	elif resolution_due:
		reasons.append("its resolution deadline is due")

	if not assigned:
		recommended_action = "Open the ticket, assign an owner, and confirm the first customer-safe response."
	else:
		recommended_action = "Open the ticket and confirm the next customer-safe action."

	base_score = client_base
	if is_new:
		base_score += 4
	if priority.casefold() in {"high", "urgent", "critical"}:
		base_score += 3
	if sla_failed:
		base_score += 8

	return _candidate(
		domain="Clients",
		exception_type="New helpdesk ticket" if is_new else "Open helpdesk ticket",
		condition=f"helpdesk-open:{status}:{priority}:{agreement_status}",
		source_doctype="HD Ticket",
		source_name=row.get("name"),
		title=row.get("subject") or f"Ticket {row.get('name')}",
		reason="; ".join(reasons) + ".",
		recommended_action=recommended_action,
		base_score=base_score,
		needs_decision=sla_failed or not assigned,
		due_at=row.get("response_by") or row.get("resolution_by"),
		occurred_at=row.get("creation") or row.get("modified"),
		owner=assigned,
		company=row.get("customer"),
	)


def collect_sales(settings: dict[str, Any], coverage: list[dict[str, str]]) -> list[dict[str, Any]]:
	from frappe.utils import add_days, now_datetime, nowdate

	candidates: list[dict[str, Any]] = []
	limit = _limit(settings)
	base = int(settings["sales_base_score"])

	if _doctype_available("AI SDR Activity"):
		replies = _safe_list(
			"AI SDR Activity",
			coverage,
			fields=[
				"name",
				"lead",
				"recipient_name",
				"assigned_to",
				"reply_classification",
				"reply_confidence",
				"modified",
			],
			filters={
				"direction": "Inbound",
				"status": "Received",
				"reply_classification": ["in", ["Interested", "Needs Information", "Referral", "Needs Review"]],
			},
			limit=limit,
		)
		for row in replies:
			classification = row.get("reply_classification") or "Needs Review"
			candidates.append(
				_candidate(
					domain="Sales",
					exception_type="Qualified inbound reply",
					condition=f"sales-reply:{classification}",
					source_doctype="AI SDR Activity",
					source_name=row.name,
					title=row.get("recipient_name") or row.get("lead") or "Inbound sales reply",
					reason=f"Reply classified as {classification}; the message body remains in its source record.",
					recommended_action="Open the classified reply and decide the next personal follow-up.",
					base_score=base + (8 if classification == "Interested" else 3),
					needs_decision=True,
					occurred_at=row.modified,
					owner=row.get("assigned_to"),
				)
			)

	lead_fields = _available_fields(
		"CRM Lead",
		["name", "lead_name", "lead_owner", "status", "modified"],
		["ai_sdr_priority", "ai_sdr_state", "ai_sdr_next_call_at", "ai_sdr_do_not_contact"],
	) if _doctype_available("CRM Lead") else []
	if lead_fields and "ai_sdr_priority" in lead_fields:
		priority_leads = _safe_list(
			"CRM Lead",
			coverage,
			fields=lead_fields,
			filters={"ai_sdr_priority": "High", "ai_sdr_do_not_contact": 0},
			limit=limit,
		)
		stale_cutoff = str(add_days(nowdate(), -int(settings["lead_stale_days"])))[:10]
		for row in priority_leads:
			if row.get("status") in {"Converted", "Lost"}:
				continue
			candidates.append(
				_candidate(
					domain="Sales",
					exception_type="Priority lead",
					condition="priority-lead",
					source_doctype="CRM Lead",
					source_name=row.name,
					title=row.get("lead_name") or row.name,
					reason="High-priority CRM lead is still active.",
					recommended_action="Confirm the next concrete call or follow-up step.",
					base_score=base,
					needs_decision=str(row.get("modified") or "")[:10] <= stale_cutoff,
					due_at=row.get("ai_sdr_next_call_at"),
					occurred_at=row.modified,
					owner=row.get("lead_owner"),
				)
			)
	if lead_fields and "ai_sdr_next_call_at" in lead_fields:
		calls = _safe_list(
			"CRM Lead",
			coverage,
			fields=lead_fields,
			filters={"ai_sdr_next_call_at": ["<=", now_datetime()], "ai_sdr_do_not_contact": 0},
			limit=limit,
		)
		for row in calls:
			candidates.append(
				_candidate(
					domain="Sales",
					exception_type="Call due",
					condition="sales-call-due",
					source_doctype="CRM Lead",
					source_name=row.name,
					title=row.get("lead_name") or row.name,
					reason="The CRM call date is due or overdue.",
					recommended_action="Open the lead, make the call, or reschedule it explicitly.",
					base_score=base + 3,
					due_at=row.get("ai_sdr_next_call_at"),
					occurred_at=row.modified,
					owner=row.get("lead_owner"),
				)
			)

	tasks = _safe_list(
		"CRM Task",
		coverage,
		fields=["name", "title", "priority", "status", "assigned_to", "due_date", "reference_doctype", "reference_docname", "modified"],
		filters={"status": ["not in", ["Done", "Canceled"]], "due_date": ["<=", now_datetime()]},
		limit=limit,
	)
	for row in tasks:
		candidates.append(
			_candidate(
				domain="Sales",
				exception_type="Sales task due",
				condition="crm-task-due",
				source_doctype="CRM Task",
				source_name=row.name,
				title=row.get("title") or row.name,
				reason="Open CRM task is due or overdue.",
				recommended_action="Complete it or schedule a realistic follow-up.",
				base_score=base + (4 if row.get("priority") == "High" else 0),
				due_at=row.get("due_date"),
				occurred_at=row.modified,
				owner=row.get("assigned_to"),
			)
		)

	deals = _safe_list(
		"CRM Deal",
		coverage,
		fields=["name", "organization_name", "status", "deal_owner", "next_step", "expected_closure_date", "closed_date", "modified"],
		filters={"closed_date": ["is", "not set"]},
		limit=limit,
	)
	stale_cutoff = add_days(nowdate(), -int(settings["deal_stale_days"]))
	for row in deals:
		if str(row.get("status") or "").casefold() in {"won", "lost"}:
			continue
		missing_next_step = not str(row.get("next_step") or "").strip()
		stale = str(row.get("modified") or "")[:10] <= stale_cutoff
		due = row.get("expected_closure_date") and str(row.expected_closure_date)[:10] <= nowdate()
		if not (missing_next_step or stale or due):
			continue
		reasons = []
		if missing_next_step:
			reasons.append("no next step")
		if stale:
			reasons.append(f"no update within {settings['deal_stale_days']} days")
		if due:
			reasons.append("expected close date reached")
		candidates.append(
			_candidate(
				domain="Sales",
				exception_type="Deal needs action",
				condition="deal-needs-action:" + ":".join(reasons),
				source_doctype="CRM Deal",
				source_name=row.name,
				title=row.get("organization_name") or row.name,
				reason="Deal has " + ", ".join(reasons) + ".",
				recommended_action="Set the next accountable step or decide whether to close the deal.",
				base_score=base + 2,
				needs_decision=missing_next_step or due,
				due_at=row.get("expected_closure_date"),
				occurred_at=row.modified,
				owner=row.get("deal_owner"),
			)
		)
	return candidates


def collect_clients_and_team(
	settings: dict[str, Any], coverage: list[dict[str, str]], user: str
) -> list[dict[str, Any]]:
	from frappe.utils import nowdate

	candidates: list[dict[str, Any]] = []
	limit = _limit(settings)
	client_base = int(settings["clients_base_score"])
	team_base = int(settings["team_base_score"])

	ticket_fields = (
		_available_fields(
			"HD Ticket",
			["name", "subject", "status", "priority", "customer", "creation", "modified"],
			["status_category", "agreement_status", "response_by", "resolution_by", "_assign"],
		)
		if _doctype_available("HD Ticket")
		else []
	)
	ticket_filters = (
		{"status_category": "Open"}
		if "status_category" in ticket_fields
		else {"status": ["in", ["New", "Open"]]}
	)
	tickets = (
		_safe_list(
			"HD Ticket",
			coverage,
			fields=ticket_fields,
			filters=ticket_filters,
			limit=limit,
			order_by="creation desc",
		)
		if ticket_fields
		else []
	)
	for row in tickets:
		candidate = _helpdesk_ticket_candidate(row, client_base, nowdate())
		if candidate:
			candidates.append(candidate)

	todos = _safe_list(
		"ToDo",
		coverage,
		fields=["name", "priority", "status", "date", "allocated_to", "reference_type", "reference_name", "modified"],
		filters={"status": "Open", "allocated_to": user},
		limit=limit,
		order_by="date asc, modified desc",
	)
	for row in todos:
		due = row.get("date") and str(row.date)[:10] <= nowdate()
		if row.get("priority") != "High" and not due:
			continue
		reference_type = row.get("reference_type") or "ToDo"
		reference_name = row.get("reference_name") or row.name
		domain = "Sales" if reference_type in {"CRM Lead", "CRM Deal", "CRM Task"} else "Team"
		if reference_type in {"HD Ticket", "Project"}:
			domain = "Clients"
		candidates.append(
			_candidate(
				domain=domain,
				exception_type="Assigned follow-up",
				condition=f"todo:{row.name}",
				source_doctype=reference_type,
				source_name=reference_name,
				title=f"{reference_type} {reference_name}",
				reason="High-priority assignment is open." if row.get("priority") == "High" else "Assignment is due.",
				recommended_action="Open the source record and complete or reschedule the assignment.",
				base_score=team_base + (5 if row.get("priority") == "High" else 0),
				due_at=row.get("date"),
				occurred_at=row.modified,
				owner=user,
			)
		)

	tasks = _safe_list(
		"Task",
		coverage,
		fields=_available_fields(
			"Task",
			["name", "subject", "project", "status", "priority", "exp_end_date", "company", "modified"],
			["_assign"],
		),
		filters={"status": ["not in", ["Completed", "Cancelled", "Template"]]},
		limit=limit,
	) if _doctype_available("Task") else []
	for row in tasks:
		pending_review = row.get("status") == "Pending Review"
		due = row.get("exp_end_date") and str(row.exp_end_date)[:10] <= nowdate()
		high = row.get("priority") in {"High", "Urgent"}
		assigned = _assigned_user(row.get("_assign"))
		if assigned != user or not (pending_review or (due and high)):
			continue
		candidates.append(
			_candidate(
				domain="Team",
				exception_type="Development task needs founder attention",
				condition=f"project-task:{row.get('status')}:{row.get('priority')}",
				source_doctype="Task",
				source_name=row.name,
				title=row.get("subject") or row.name,
				reason="Task is awaiting review." if pending_review else "High-priority task is overdue.",
				recommended_action="Review the task and record the decision or next owner.",
				base_score=team_base + (5 if pending_review else 2),
				needs_decision=pending_review,
				due_at=row.get("exp_end_date"),
				occurred_at=row.modified,
				owner=assigned,
				company=row.get("company"),
			)
		)

	projects = _safe_list(
		"Project",
		coverage,
		fields=["name", "project_name", "customer", "company", "status", "priority", "percent_complete", "expected_end_date", "modified"],
		filters={"status": "Open", "expected_end_date": ["<", nowdate()]},
		limit=limit,
	)
	for row in projects:
		if float(row.get("percent_complete") or 0) >= 100:
			continue
		candidates.append(
			_candidate(
				domain="Clients",
				exception_type="Project milestone overdue",
				condition="project-overdue",
				source_doctype="Project",
				source_name=row.name,
				title=row.get("project_name") or row.name,
				reason="Open project has passed its expected end date.",
				recommended_action="Open the project and confirm the blocker, dependency, and revised owner/date.",
				base_score=client_base,
				due_at=row.get("expected_end_date"),
				occurred_at=row.modified,
				company=row.get("company") or row.get("customer"),
			)
		)
	return candidates


def collect_finance(settings: dict[str, Any], coverage: list[dict[str, str]]) -> list[dict[str, Any]]:
	from frappe.utils import add_days, nowdate

	candidates: list[dict[str, Any]] = []
	limit = _limit(settings)
	base = int(settings["finance_base_score"])
	invoices = _safe_list(
		"Sales Invoice",
		coverage,
		fields=_available_fields(
			"Sales Invoice",
			["name", "customer_name", "company", "status", "docstatus", "currency", "grand_total", "outstanding_amount", "due_date", "modified"],
			["custom_versandstatus"],
		),
		filters={"docstatus": ["<", 2]},
		limit=limit,
	)
	for row in invoices:
		if int(row.get("docstatus") or 0) == 1 and float(row.get("outstanding_amount") or 0) > 0:
			if row.get("due_date") and str(row.due_date)[:10] < nowdate():
				candidates.append(
					_candidate(
						domain="Finance",
						exception_type="Overdue receivable",
						condition="receivable-overdue",
						source_doctype="Sales Invoice",
						source_name=row.name,
						title=f"{row.get('customer_name') or row.name} · {row.get('currency') or ''} {row.get('outstanding_amount') or 0}",
						reason="Submitted invoice is overdue with an outstanding balance.",
						recommended_action="Review payment status and choose a customer-appropriate collection step.",
						base_score=base + 3,
						needs_decision=True,
						due_at=row.get("due_date"),
						occurred_at=row.modified,
						company=row.get("company"),
					)
				)
		elif int(row.get("docstatus") or 0) == 0:
			candidates.append(
				_candidate(
					domain="Finance",
					exception_type="Draft invoice awaiting decision",
					condition="invoice-draft",
					source_doctype="Sales Invoice",
					source_name=row.name,
					title=f"{row.get('customer_name') or row.name} · {row.get('currency') or ''} {row.get('grand_total') or 0}",
					reason="Invoice remains in Draft and has not entered the controlled send/submission flow.",
					recommended_action="Review the invoice; submission and sending remain outside the cockpit.",
					base_score=base - 2,
					needs_decision=True,
					due_at=add_days(str(row.get("modified"))[:10], 1),
					occurred_at=row.modified,
					company=row.get("company"),
				)
			)

	quotations = _safe_list(
		"Quotation",
		coverage,
		fields=["name", "title", "party_name", "company", "status", "docstatus", "valid_till", "transaction_date", "grand_total", "currency", "modified"],
		filters={"docstatus": ["<", 2], "status": ["not in", ["Ordered", "Lost", "Cancelled"]]},
		limit=limit,
	)
	window_end = add_days(nowdate(), int(settings["quotation_action_window_days"]))
	for row in quotations:
		is_draft = int(row.get("docstatus") or 0) == 0
		expiring = row.get("valid_till") and str(row.valid_till)[:10] <= window_end
		if not (is_draft or expiring):
			continue
		candidates.append(
			_candidate(
				domain="Sales",
				exception_type="Proposal needs action",
				condition="quotation-draft" if is_draft else "quotation-expiring",
				source_doctype="Quotation",
				source_name=row.name,
				title=row.get("title") or row.get("party_name") or row.name,
				reason="Quotation is awaiting review." if is_draft else "Open quotation expires within the configured action window.",
				recommended_action="Review the quotation and decide the next step; submission or sending requires the source workflow.",
				base_score=base - (2 if is_draft else 4),
				needs_decision=is_draft,
				due_at=row.get("valid_till"),
				occurred_at=row.modified,
				company=row.get("company"),
			)
		)
	return candidates


def _ignored_error(method: str, settings: dict[str, Any]) -> bool:
	patterns = [line.strip().casefold() for line in str(settings.get("ignored_error_methods") or "").splitlines() if line.strip()]
	method_key = (method or "").casefold()
	return any(pattern in method_key for pattern in patterns)


def collect_operations(settings: dict[str, Any], coverage: list[dict[str, str]]) -> list[dict[str, Any]]:
	from frappe.utils import add_to_date, now_datetime

	candidates: list[dict[str, Any]] = []
	limit = _limit(settings) * 2
	base = int(settings["operations_base_score"])
	lookback = add_to_date(now_datetime(), hours=-int(settings["operational_lookback_hours"]), as_datetime=True)

	job_logs = _safe_list(
		"Scheduled Job Log",
		coverage,
		fields=["name", "scheduled_job_type", "status", "creation", "modified"],
		filters={"status": "Failed", "creation": [">=", lookback]},
		limit=limit,
	)
	jobs: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in job_logs:
		jobs[str(row.get("scheduled_job_type") or "Unknown job")].append(row)
	job_types = {}
	if jobs:
		job_type_rows = _safe_list(
			"Scheduled Job Type",
			coverage,
			fields=["name", "method"],
			filters={"name": ["in", list(jobs)]},
			limit=len(jobs),
		)
		job_types = {row.name: row.get("method") or row.name for row in job_type_rows}
	for job, rows in jobs.items():
		latest = rows[0]
		job_label = job_types.get(job, job)
		dedupe_key = "operations:raven-notifications" if "raven" in job_label.casefold() else f"operations:scheduled-job:{job}"
		candidates.append(
			_candidate(
				domain="Operations",
				exception_type="Scheduled job failure",
				condition=f"scheduled-job:{job}",
				source_doctype="Scheduled Job Log",
				source_name=latest.name,
				title=f"Scheduled job failed: {job_label}",
				reason=f"{len(rows)} failure(s) within the configured {settings['operational_lookback_hours']}-hour window.",
				recommended_action="Inspect the latest log and either repair the dependency or explicitly stop the job.",
				base_score=base + (4 if len(rows) > 1 else 0),
				needs_decision=len(rows) > 1,
				occurred_at=latest.creation,
				dedupe_key=dedupe_key,
			)
		)

	integrations = _safe_list(
		"Integration Request",
		coverage,
		fields=["name", "integration_request_service", "status", "reference_doctype", "reference_docname", "creation", "modified"],
		filters={"status": "Failed", "creation": [">=", lookback]},
		limit=limit,
	)
	for row in integrations:
		candidates.append(
			_candidate(
				domain="Operations",
				exception_type="Integration failure",
				condition=f"integration:{row.get('integration_request_service') or 'unknown'}",
				source_doctype="Integration Request",
				source_name=row.name,
				title=f"Integration request failed: {row.get('integration_request_service') or row.name}",
				reason="Native Integration Request is in Failed state; payload and error remain in the restricted source record.",
				recommended_action="Open the source record, identify the owning integration, and choose retry or repair.",
				base_score=base,
				occurred_at=row.creation,
			)
		)

	webhooks = _safe_list(
		"Webhook Request Log",
		coverage,
		fields=["name", "webhook", "reference_doctype", "reference_document", "creation", "modified"],
		filters={"error": ["is", "set"], "creation": [">=", lookback]},
		limit=limit,
	)
	for row in webhooks:
		candidates.append(
			_candidate(
				domain="Operations",
				exception_type="Webhook failure",
				condition=f"webhook:{row.get('webhook') or 'unknown'}",
				source_doctype="Webhook Request Log",
				source_name=row.name,
				title=f"Webhook failed: {row.get('webhook') or row.name}",
				reason="Webhook log contains an error; request and response bodies remain in the restricted source record.",
				recommended_action="Inspect the endpoint response and retry only after the root cause is understood.",
				base_score=base,
				occurred_at=row.creation,
			)
		)

	errors = _safe_list(
		"Error Log",
		coverage,
		fields=["name", "method", "reference_doctype", "reference_name", "creation", "modified"],
		filters={"creation": [">=", lookback]},
		limit=limit,
	)
	grouped_errors: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in errors:
		method = str(row.get("method") or "Unknown application error")
		if _ignored_error(method, settings):
			continue
		grouped_errors[method].append(row)
	threshold = max(1, int(settings["repeated_error_threshold"]))
	for method, rows in grouped_errors.items():
		important_once = any(keyword in method.casefold() for keyword in ("resend", "security", "permission"))
		if len(rows) < threshold and not important_once:
			continue
		latest = rows[0]
		if "raven" in method.casefold():
			title = "Raven notification integration is failing"
			dedupe_key = "operations:raven-notifications"
		elif "resend" in method.casefold():
			title = "Resend inbound recovery needs attention"
			dedupe_key = "operations:resend-inbound"
		else:
			title = "Application error is repeating"
			dedupe_key = f"operations:error:{method}"
		candidates.append(
			_candidate(
				domain="Operations",
				exception_type="Repeated application error",
				condition=f"error-method:{method}",
				source_doctype="Error Log",
				source_name=latest.name,
				title=title,
				reason=f"{len(rows)} matching error(s) occurred within the configured lookback; details remain restricted.",
				recommended_action="Open the latest Error Log, identify the owning service, and record the repair or accepted risk.",
				base_score=base + (4 if len(rows) >= threshold else 0),
				needs_decision=len(rows) >= threshold,
				occurred_at=latest.creation,
				dedupe_key=dedupe_key,
			)
		)
	return candidates


def collect_candidates(settings: dict[str, Any], *, user: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
	import frappe

	user = user or frappe.session.user
	coverage: list[dict[str, str]] = []
	candidates: list[dict[str, Any]] = []
	for collector in (
		lambda: collect_sales(settings, coverage),
		lambda: collect_clients_and_team(settings, coverage, user),
		lambda: collect_finance(settings, coverage),
		lambda: collect_operations(settings, coverage),
	):
		candidates.extend(collector())

	# These sources have no native Loopjet ERP record feed today. Keeping them explicit
	# prevents a green cockpit from being mistaken for end-to-end coverage.
	coverage.extend(
		[
			{"source": "n8n", "status": "not_connected", "reason": "No authenticated ERP failure feed is configured"},
			{"source": "Deployments", "status": "not_connected", "reason": "No deployment approval DocType or webhook feed exists"},
			{"source": "Payment provider events", "status": "not_connected", "reason": "No material payment-event feed exists"},
		]
	)
	# The same DocType can be queried by more than one rule. Report coverage once.
	unique_coverage = list({(item["source"], item["status"], item["reason"]): item for item in coverage}.values())
	return candidates, unique_coverage
