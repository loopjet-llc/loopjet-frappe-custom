from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from email.utils import parseaddr
from html import escape
from typing import Any
from urllib.parse import quote

try:
	import frappe
except ImportError:  # pragma: no cover - lets helper tests run outside a Frappe bench
	frappe = None  # type: ignore[assignment]


SUPPORT_SENDER = "Loopjet Support <support@loopjet.io>"
DEFAULT_HELPDESK_PORTAL_URL = "https://helpdesk.loopjet.io"
NOTIFICATION_HEADER = "loopjet-helpdesk-customer-update"
AGENT_ROLES = {"Agent", "Agent Manager", "System Manager"}

TRACKED_TICKET_FIELDS = (
	("subject", "Betreff"),
	("status", "Status"),
	("priority", "Priorität"),
	("ticket_type", "Ticket-Typ"),
)

DISPLAY_VALUES = {
	("status", "Open"): "Offen",
	("status", "Replied"): "Beantwortet",
	("status", "Resolved"): "Gelöst",
	("status", "Closed"): "Geschlossen",
	("status", "On Hold"): "Pausiert",
	("priority", "Low"): "Niedrig",
	("priority", "Medium"): "Mittel",
	("priority", "High"): "Hoch",
	("priority", "Urgent"): "Dringend",
	("ticket_type", "Bug"): "Fehler",
	("ticket_type", "Feature"): "Feature",
}

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _value(record: Any, fieldname: str) -> Any:
	if isinstance(record, Mapping):
		return record.get(fieldname)
	if hasattr(record, "get"):
		return record.get(fieldname)
	return getattr(record, fieldname, None)


def _display_value(fieldname: str, value: Any) -> str:
	if value in (None, ""):
		return "Nicht gesetzt"
	value = str(value)
	return DISPLAY_VALUES.get((fieldname, value), value)


def build_ticket_changes(before: Any, after: Any) -> list[dict[str, str]]:
	changes = []
	for fieldname, label in TRACKED_TICKET_FIELDS:
		old_value = _value(before, fieldname)
		new_value = _value(after, fieldname)
		if old_value == new_value:
			continue
		changes.append(
			{
				"fieldname": fieldname,
				"label": label,
				"old": _display_value(fieldname, old_value),
				"new": _display_value(fieldname, new_value),
			}
		)
	return changes


def normalize_email(value: Any) -> str:
	if not value:
		return ""
	_, address = parseaddr(str(value))
	address = address.strip().lower()
	if not EMAIL_PATTERN.fullmatch(address):
		return ""
	return address


def deduplicate_emails(values: Sequence[Any]) -> list[str]:
	result = []
	seen = set()
	for value in values:
		email = normalize_email(value)
		if not email or email in seen:
			continue
		seen.add(email)
		result.append(email)
	return result


def build_ticket_url(ticket_name: str, portal_url: str = DEFAULT_HELPDESK_PORTAL_URL) -> str:
	base_url = portal_url.rstrip("/")
	return f"{base_url}/helpdesk/my-tickets/{quote(str(ticket_name), safe='')}"


def build_notification_subject(ticket_name: str, ticket_subject: str, *, is_comment: bool = False) -> str:
	clean_subject = " ".join(str(ticket_subject or "").split())[:120]
	event = "Neuer Kommentar" if is_comment else "Ticket aktualisiert"
	return f"{event}: #{ticket_name} - {clean_subject}" if clean_subject else f"{event}: #{ticket_name}"


def build_notification_message(
	*,
	ticket_name: str,
	ticket_subject: str,
	actor_name: str,
	ticket_url: str,
	changes: Sequence[Mapping[str, str]] = (),
	comment_html: str | None = None,
	comment_updated: bool = False,
) -> str:
	actor = escape(actor_name or "Loopjet Support")
	name = escape(str(ticket_name))
	subject = escape(ticket_subject or "Ohne Betreff")
	url = escape(ticket_url, quote=True)

	sections = [
		'<div style="font-family:Arial,Helvetica,sans-serif;color:#14161c;line-height:1.55;max-width:680px">',
		'<div style="height:4px;background:#22d3ee;margin-bottom:24px"></div>',
		f'<p style="font-size:14px;color:#5d6470;margin:0 0 8px">Helpdesk-Ticket #{name}</p>',
		f'<h2 style="font-size:22px;line-height:1.3;margin:0 0 18px">{subject}</h2>',
	]

	if comment_html is not None:
		comment_label = "Kommentar aktualisiert" if comment_updated else "Neuer Kommentar"
		sections.extend(
			[
				f"<p><strong>{actor}</strong> hat einen Kommentar hinterlassen.</p>"
				if not comment_updated
				else f"<p><strong>{actor}</strong> hat einen Kommentar aktualisiert.</p>",
				f'<div style="margin:18px 0;padding:16px 18px;background:#f6f7fa;border-left:4px solid #38bdf8">'
				f'<div style="font-size:12px;font-weight:700;color:#5d6470;margin-bottom:8px">{comment_label}</div>'
				f"{comment_html}</div>",
			]
		)

	if changes:
		rows = []
		for change in changes:
			rows.append(
				"<tr>"
				f'<td style="padding:10px 12px;border-top:1px solid #e5e7eb;font-weight:700">{escape(change["label"])}</td>'
				f'<td style="padding:10px 12px;border-top:1px solid #e5e7eb;color:#5d6470">{escape(change["old"])}</td>'
				f'<td style="padding:10px 12px;border-top:1px solid #e5e7eb">{escape(change["new"])}</td>'
				"</tr>"
			)
		sections.extend(
			[
				f"<p><strong>{actor}</strong> hat das Ticket aktualisiert.</p>",
				'<table role="presentation" style="width:100%;border-collapse:collapse;margin:18px 0;border:1px solid #e5e7eb">',
				'<thead><tr style="background:#f6f7fa">'
				'<th style="padding:10px 12px;text-align:left">Änderung</th>'
				'<th style="padding:10px 12px;text-align:left">Vorher</th>'
				'<th style="padding:10px 12px;text-align:left">Jetzt</th>'
				"</tr></thead>",
				f"<tbody>{''.join(rows)}</tbody></table>",
			]
		)

	sections.extend(
		[
			'<p style="margin:24px 0">'
			f'<a href="{url}" style="display:inline-block;background:#14161c;color:#ffffff;text-decoration:none;'
			'padding:11px 18px;border-radius:8px;font-weight:700">Ticket im Helpdesk öffnen</a></p>',
			'<p style="font-size:12px;color:#8b94a6;margin-top:28px">'
			"Diese Nachricht wurde automatisch vom Loopjet Helpdesk gesendet. "
			"Weitere Details und Antworten findest du direkt im Ticket.</p>",
			"</div>",
		]
	)
	return "".join(sections)


def get_ticket_customer_recipients(ticket: Any) -> list[str]:
	if frappe is None:  # pragma: no cover - runtime guard
		raise RuntimeError("Frappe is required to resolve Helpdesk recipients")
	if isinstance(ticket, str):
		ticket = frappe.get_doc("HD Ticket", ticket)

	candidates = [_value(ticket, "raised_by")]
	contact_name = _value(ticket, "contact")
	if contact_name:
		contact = frappe.db.get_value("Contact", contact_name, ["email_id", "user"], as_dict=True)
		if contact:
			candidates.extend([contact.email_id, contact.user])
		else:
			candidates.append(contact_name)

	customer = _value(ticket, "customer")
	if customer:
		contact_names = frappe.get_all(
			"Dynamic Link",
			filters={
				"parenttype": "Contact",
				"parentfield": "links",
				"link_doctype": "HD Customer",
				"link_name": customer,
			},
			pluck="parent",
		)
		if contact_names:
			contacts = frappe.get_all(
				"Contact",
				filters={"name": ["in", contact_names]},
				fields=["email_id", "user"],
			)
			users = [contact.user for contact in contacts if contact.user]
			enabled_portal_users = set()
			if users:
				enabled_portal_users = set(
					frappe.get_all(
						"User",
						filters={"name": ["in", users], "enabled": 1, "user_type": "Website User"},
						pluck="name",
					)
				)
			for contact in contacts:
				if contact.user in enabled_portal_users:
					candidates.extend([contact.email_id, contact.user])

	return deduplicate_emails(candidates)


def _is_helpdesk_agent(user: str) -> bool:
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	if frappe.db.exists("HD Agent", {"name": user, "is_active": 1}):
		return True
	return bool(AGENT_ROLES.intersection(frappe.get_roles(user)))


def _actor_name(user: str) -> str:
	if user in {"Administrator", "Guest", ""}:
		return "Loopjet Support"
	return frappe.db.get_value("User", user, "full_name") or user


def _portal_url() -> str:
	return frappe.conf.get("loopjet_helpdesk_portal_url") or DEFAULT_HELPDESK_PORTAL_URL


def _send_customer_notification(
	ticket: Any,
	*,
	actor_user: str,
	changes: Sequence[Mapping[str, str]] = (),
	comment_html: str | None = None,
	comment_updated: bool = False,
) -> None:
	recipients = get_ticket_customer_recipients(ticket)
	actor_email = normalize_email(actor_user)
	recipients = [recipient for recipient in recipients if recipient != actor_email]
	if not recipients:
		return

	ticket_url = build_ticket_url(ticket.name, _portal_url())
	message = build_notification_message(
		ticket_name=ticket.name,
		ticket_subject=ticket.subject,
		actor_name=_actor_name(actor_user),
		ticket_url=ticket_url,
		changes=changes,
		comment_html=comment_html,
		comment_updated=comment_updated,
	)
	frappe.sendmail(
		recipients=recipients,
		sender=SUPPORT_SENDER,
		subject=build_notification_subject(
			ticket.name,
			ticket.subject,
			is_comment=comment_html is not None,
		),
		message=message,
		reference_doctype="HD Ticket",
		reference_name=ticket.name,
		queue_separately=True,
		is_notification=True,
		add_unsubscribe_link=False,
		email_headers={"X-Auto-Generated": NOTIFICATION_HEADER},
	)


def _log_notification_error(ticket_name: str) -> None:
	frappe.log_error(
		frappe.get_traceback(),
		f"Helpdesk customer update notification failed for ticket {ticket_name}",
	)


def notify_ticket_update(doc: Any, method: str | None = None) -> None:
	if frappe is None:  # pragma: no cover - runtime guard
		return
	try:
		before = doc.get_doc_before_save()
		if not before:
			return
		changes = build_ticket_changes(before, doc)
		actor_user = frappe.session.user
		if not changes or not _is_helpdesk_agent(actor_user):
			return
		_send_customer_notification(doc, actor_user=actor_user, changes=changes)
	except Exception:
		_log_notification_error(getattr(doc, "name", "unknown"))


def _notify_comment(doc: Any, *, actor_user: str, comment_updated: bool) -> None:
	if not _is_helpdesk_agent(actor_user):
		return
	ticket = frappe.get_doc("HD Ticket", doc.reference_ticket)
	comment_html = frappe.utils.sanitize_html(doc.content or "")
	_send_customer_notification(
		ticket,
		actor_user=actor_user,
		comment_html=comment_html,
		comment_updated=comment_updated,
	)


def notify_ticket_comment(doc: Any, method: str | None = None) -> None:
	if frappe is None:  # pragma: no cover - runtime guard
		return
	try:
		_notify_comment(
			doc,
			actor_user=doc.commented_by or frappe.session.user,
			comment_updated=False,
		)
	except Exception:
		_log_notification_error(getattr(doc, "reference_ticket", "unknown"))


def notify_ticket_comment_update(doc: Any, method: str | None = None) -> None:
	if frappe is None:  # pragma: no cover - runtime guard
		return
	try:
		before = doc.get_doc_before_save()
		if not before or before.content == doc.content:
			return
		_notify_comment(doc, actor_user=frappe.session.user, comment_updated=True)
	except Exception:
		_log_notification_error(getattr(doc, "reference_ticket", "unknown"))
