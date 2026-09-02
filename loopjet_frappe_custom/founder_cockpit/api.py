from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, now, now_datetime, nowdate

from loopjet_frappe_custom.founder_cockpit.collectors import collect_candidates, settings_snapshot
from loopjet_frappe_custom.founder_cockpit.domain import dedupe_and_prioritize, validate_safe_action
from loopjet_frappe_custom.founder_cockpit.permissions import require_cockpit_access

CARD_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def _settings_doc():
	return frappe.get_single("Founder Cockpit Settings")


def _active_acknowledgements(user: str) -> list[str]:
	return frappe.get_list(
		"Founder Cockpit State",
		filters={"user": user, "acknowledged_until": [">", now()]},
		pluck="card_id",
		limit_page_length=500,
	)


def build_context(*, user: str | None = None) -> dict[str, Any]:
	user = user or frappe.session.user
	settings_doc = _settings_doc()
	settings = settings_snapshot(settings_doc)
	candidates, coverage = collect_candidates(settings, user=user)
	surfaces = dedupe_and_prioritize(
		candidates,
		settings,
		now=now_datetime(),
		acknowledged_card_ids=_active_acknowledgements(user),
	)
	return {
		"user": user,
		"can_manage": "System Manager" in frappe.get_roles(user) or user == "Administrator",
		"generated_at": now(),
		"surfaces": surfaces,
		"counts": {surface: len(items) for surface, items in surfaces.items()},
		"coverage": coverage,
		"notification_mode": settings_doc.notification_mode or "Off",
		"daily_digest_enabled": bool(settings_doc.daily_digest_enabled),
	}


@frappe.whitelist(methods=["GET"])
def get_context() -> dict[str, Any]:
	require_cockpit_access()
	return build_context()


def _check_source_permission(source_doctype: str, source_name: str) -> None:
	if not frappe.db.exists("DocType", source_doctype) or not frappe.db.exists(source_doctype, source_name):
		frappe.throw(_("The source record no longer exists."), frappe.DoesNotExistError)
	if not frappe.has_permission(source_doctype, "read", source_name):
		frappe.throw(_("You do not have access to the source record."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def acknowledge(card_id: str, source_doctype: str, source_name: str) -> dict[str, Any]:
	require_cockpit_access()
	try:
		validate_safe_action("acknowledge", source_doctype, source_name)
	except ValueError as exc:
		frappe.throw(_(str(exc)))
	if not CARD_ID_PATTERN.fullmatch(card_id or ""):
		frappe.throw(_("The cockpit card identifier is invalid."))
	_check_source_permission(source_doctype, source_name)

	settings = settings_snapshot(_settings_doc())
	acknowledged_until = add_to_date(now_datetime(), hours=int(settings["acknowledge_hours"]), as_datetime=True)
	dedupe_key = hashlib.sha256(f"{frappe.session.user}|{card_id}".encode()).hexdigest()
	name = frappe.db.exists("Founder Cockpit State", {"dedupe_key": dedupe_key})
	values = {
		"user": frappe.session.user,
		"card_id": card_id,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"acknowledged_at": now(),
		"acknowledged_until": acknowledged_until,
	}
	if name:
		doc = frappe.get_doc("Founder Cockpit State", name)
		if doc.user != frappe.session.user and frappe.session.user != "Administrator":
			frappe.throw(_("You cannot update another user's cockpit state."), frappe.PermissionError)
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Founder Cockpit State", "dedupe_key": dedupe_key, **values}).insert()
	return {"acknowledged": True, "card_id": card_id, "until": doc.acknowledged_until}


@frappe.whitelist(methods=["POST"])
def schedule_follow_up(
	source_doctype: str,
	source_name: str,
	due_date: str,
	priority: str = "High",
) -> dict[str, Any]:
	require_cockpit_access()
	try:
		validate_safe_action(
			"schedule_follow_up",
			source_doctype,
			source_name,
			due_date=due_date,
			today=getdate(nowdate()),
		)
	except ValueError as exc:
		frappe.throw(_(str(exc)))
	_check_source_permission(source_doctype, source_name)
	if priority not in {"High", "Medium", "Low"}:
		frappe.throw(_("Unsupported follow-up priority."))

	existing = frappe.get_list(
		"ToDo",
		filters={
			"reference_type": source_doctype,
			"reference_name": source_name,
			"allocated_to": frappe.session.user,
			"status": "Open",
		},
		pluck="name",
		limit_page_length=1,
	)
	if existing:
		todo = frappe.get_doc("ToDo", existing[0])
		todo.date = getdate(due_date)
		todo.priority = priority
		todo.save()
	else:
		from frappe.desk.form.assign_to import add

		add(
			{
				"assign_to": json.dumps([frappe.session.user]),
				"doctype": source_doctype,
				"name": source_name,
				"description": _("Founder Cockpit follow-up for {0} {1}").format(source_doctype, source_name),
				"date": due_date,
				"priority": priority,
			}
		)
		existing = frappe.get_list(
			"ToDo",
			filters={
				"reference_type": source_doctype,
				"reference_name": source_name,
				"allocated_to": frappe.session.user,
				"status": "Open",
			},
			pluck="name",
			limit_page_length=1,
		)
	return {"scheduled": True, "todo": existing[0] if existing else None, "due_date": due_date}


def _digest_description(context: dict[str, Any]) -> str:
	counts = context["counts"]
	return _(
		"Founder Cockpit daily digest for {0}: {1} decisions, {2} due today, {3} watchlist. Open /app/founder-cockpit."
	).format(nowdate(), counts["needs_decision"], counts["today"], counts["watchlist"])


def prepare_daily_digest() -> bool:
	"""Create one native ToDo digest when explicitly enabled; never sends email."""
	settings_doc = _settings_doc()
	if not settings_doc.daily_digest_enabled or settings_doc.notification_mode != "Native ToDo":
		return False
	if now_datetime().hour != int(settings_doc.daily_digest_hour or 8):
		return False
	if str(settings_doc.last_digest_on or "") == nowdate():
		return False
	user = settings_doc.digest_user
	if not user or not frappe.db.get_value("User", user, "enabled"):
		frappe.log_error("Founder Cockpit digest user is missing or disabled.", "Founder Cockpit digest skipped")
		return False

	previous_user = frappe.session.user
	try:
		frappe.set_user(user)
		require_cockpit_access()
		context = build_context(user=user)
	finally:
		frappe.set_user(previous_user)

	description = _digest_description(context)
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": user,
			"assigned_by": user,
			"description": description,
			"priority": "High" if context["counts"]["needs_decision"] else "Medium",
			"status": "Open",
			"date": nowdate(),
		}
	).insert(ignore_permissions=True)
	frappe.db.set_single_value("Founder Cockpit Settings", "last_digest_on", nowdate())
	return True
