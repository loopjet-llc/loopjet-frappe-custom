from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from email.utils import getaddresses, parseaddr
from typing import Any

try:
	import frappe
except ImportError:  # pragma: no cover - lets helper tests run outside a Frappe bench
	frappe = None  # type: ignore[assignment]

RESEND_RECEIVED_EMAIL_URL = "https://api.resend.com/emails/receiving/{email_id}"
RESEND_RECEIVED_ATTACHMENT_URL = "https://api.resend.com/emails/receiving/{email_id}/attachments/{attachment_id}"
HTTP_USER_AGENT = "Loopjet ERP/1.0 (+https://loopjet.io)"
SUPPORT_EMAIL_ACCOUNT = "Loopjet Support"
INBOUND_TOKEN_CONFIG_KEY = "loopjet_resend_inbound_token"
WEBHOOK_SECRET_CONFIG_KEY = "loopjet_resend_webhook_secret"
RECEIVING_API_KEY_CONFIG_KEY = "loopjet_resend_receiving_api_key"


def _as_list(value: Any) -> list[str]:
	if value is None:
		return []
	if isinstance(value, str):
		return [value]
	if isinstance(value, (list, tuple, set)):
		return [str(item) for item in value if item]
	return [str(value)]


def _clean_email(value: str | None) -> str:
	if not value:
		return ""
	_, address = parseaddr(value)
	return address or value.strip()


def _clean_email_list(value: Any) -> list[str]:
	return [_clean_email(item) for item in _as_list(value) if _clean_email(item)]


def _format_recipients(value: Any) -> str:
	return ", ".join(_clean_email_list(value))


def _first_present(*values: Any) -> Any:
	for value in values:
		if value not in (None, "", [], ()):
			return value
	return None


def _extract_email_from_header(value: str | None) -> str:
	if not value:
		return ""
	addresses = getaddresses([value])
	if not addresses:
		return _clean_email(value)
	return addresses[0][1] or _clean_email(value)


def _attachment_summary(attachments: Any) -> str:
	lines = []
	for attachment in attachments or []:
		if not isinstance(attachment, dict):
			continue
		filename = attachment.get("filename") or attachment.get("name") or "attachment"
		content_type = attachment.get("content_type") or attachment.get("content-type") or ""
		size = attachment.get("size")
		detail = filename
		if content_type:
			detail += f" ({content_type})"
		if size:
			detail += f", {size} bytes"
		lines.append(html.escape(detail))
	if not lines:
		return ""
	return "<p><strong>Attachments received:</strong></p><ul>" + "".join(f"<li>{line}</li>" for line in lines) + "</ul>"


def _fallback_description(email_data: dict[str, Any], fetch_error: str | None = None) -> str:
	lines = [
		"<p>This ticket was created from an inbound Resend email event.</p>",
		"<ul>",
	]
	for label, value in (
		("Resend email ID", email_data.get("email_id") or email_data.get("id")),
		("From", email_data.get("from")),
		("To", _format_recipients(email_data.get("to"))),
		("CC", _format_recipients(email_data.get("cc"))),
		("Message ID", email_data.get("message_id")),
	):
		if value:
			lines.append(f"<li><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</li>")
	if fetch_error:
		lines.append(f"<li><strong>Body fetch:</strong> {html.escape(fetch_error)}</li>")
	lines.append("</ul>")
	lines.append(_attachment_summary(email_data.get("attachments")))
	return "".join(lines)


def build_ticket_payload(email_data: dict[str, Any], fetch_error: str | None = None) -> dict[str, Any]:
	"""Build normalized ticket fields from Resend email metadata/content."""
	headers = email_data.get("headers") if isinstance(email_data.get("headers"), dict) else {}
	sender = _first_present(email_data.get("from"), headers.get("from"), headers.get("return-path"))
	body_html = email_data.get("html")
	body_text = email_data.get("text")
	if body_html:
		description = str(body_html)
	elif body_text:
		description = f"<pre style=\"white-space: pre-wrap; font-family: inherit;\">{html.escape(str(body_text))}</pre>"
	else:
		description = _fallback_description(email_data, fetch_error)

	attachment_summary = _attachment_summary(email_data.get("attachments"))
	if attachment_summary and attachment_summary not in description:
		description += attachment_summary

	message_id = _first_present(email_data.get("message_id"), headers.get("message-id"), email_data.get("email_id"), email_data.get("id"))
	subject = str(_first_present(email_data.get("subject"), "(No subject)"))

	return {
		"subject": subject[:140],
		"full_subject": subject,
		"sender": _extract_email_from_header(str(sender)) if sender else "",
		"sender_raw": str(sender or ""),
		"recipients": _format_recipients(email_data.get("to")),
		"cc": _format_recipients(email_data.get("cc")),
		"description": description,
		"text_content": str(body_text or ""),
		"message_id": str(message_id or ""),
		"email_id": str(_first_present(email_data.get("email_id"), email_data.get("id"), "")),
		"attachments": [item for item in (email_data.get("attachments") or []) if isinstance(item, dict)],
	}


def _header(request: Any, name: str) -> str:
	return request.headers.get(name, "") if getattr(request, "headers", None) else ""


def _constant_time_match(left: str | None, right: str | None) -> bool:
	if not left or not right:
		return False
	return hmac.compare_digest(str(left), str(right))


def _verify_svix_signature(raw_body: str, headers: dict[str, str], webhook_secret: str | None) -> bool:
	"""Verify Resend/Svix webhook signatures without requiring an extra dependency."""
	if not webhook_secret:
		return False

	svix_id = headers.get("svix-id") or headers.get("Svix-Id")
	svix_timestamp = headers.get("svix-timestamp") or headers.get("Svix-Timestamp")
	svix_signature = headers.get("svix-signature") or headers.get("Svix-Signature")
	if not (svix_id and svix_timestamp and svix_signature):
		return False

	secret = webhook_secret
	if secret.startswith("whsec_"):
		secret = secret.split("_", 1)[1]

	try:
		key = base64.b64decode(secret)
	except Exception:
		return False

	signed_content = f"{svix_id}.{svix_timestamp}.{raw_body}".encode()
	expected = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()

	for signature_part in re.split(r"\s+", svix_signature):
		if "," in signature_part:
			version, signature = signature_part.split(",", 1)
			if version == "v1" and hmac.compare_digest(signature, expected):
				return True
	return False


def _is_authorized(raw_body: str, form_token: str | None, request: Any, conf: Any) -> bool:
	configured_token = getattr(conf, INBOUND_TOKEN_CONFIG_KEY, None)
	webhook_secret = getattr(conf, WEBHOOK_SECRET_CONFIG_KEY, None)
	headers = {
		"svix-id": _header(request, "svix-id"),
		"svix-timestamp": _header(request, "svix-timestamp"),
		"svix-signature": _header(request, "svix-signature"),
	}
	return _constant_time_match(form_token, configured_token) or _verify_svix_signature(raw_body, headers, webhook_secret)


def _get_resend_api_key() -> str | None:
	import frappe

	configured_key = getattr(frappe.conf, RECEIVING_API_KEY_CONFIG_KEY, None)
	if configured_key:
		return configured_key

	if frappe.db.exists("Email Account", SUPPORT_EMAIL_ACCOUNT):
		return frappe.get_doc("Email Account", SUPPORT_EMAIL_ACCOUNT).get_password("password")

	account = frappe.db.get_value(
		"Email Account",
		{"smtp_server": "smtp.resend.com", "enable_outgoing": 1},
		"name",
	)
	if account:
		return frappe.get_doc("Email Account", account).get_password("password")
	return None


def _fetch_received_email(email_id: str, api_key: str | None) -> tuple[dict[str, Any] | None, str | None]:
	if not email_id:
		return None, "missing Resend email_id"
	if not api_key:
		return None, "missing Resend API key"

	request = urllib.request.Request(
		RESEND_RECEIVED_EMAIL_URL.format(email_id=email_id),
		headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json", "User-Agent": HTTP_USER_AGENT},
		method="GET",
	)
	try:
		with urllib.request.urlopen(request, timeout=20) as response:
			payload = response.read().decode()
	except urllib.error.HTTPError as exc:
		return None, f"Resend returned HTTP {exc.code}"
	except urllib.error.URLError as exc:
		return None, f"Resend request failed: {exc.reason}"
	except TimeoutError:
		return None, "Resend request timed out"

	try:
		data = json.loads(payload)
	except json.JSONDecodeError:
		return None, "Resend returned invalid JSON"
	if not isinstance(data, dict):
		return None, "Resend returned invalid email"
	return data, None


def _fetch_received_attachment(
	email_id: str, attachment_id: str, api_key: str | None
) -> tuple[dict[str, Any] | None, str | None]:
	if not email_id:
		return None, "missing Resend email_id"
	if not attachment_id:
		return None, "missing Resend attachment id"
	if not api_key:
		return None, "missing Resend API key"

	request = urllib.request.Request(
		RESEND_RECEIVED_ATTACHMENT_URL.format(
			email_id=urllib.parse.quote(email_id, safe=""),
			attachment_id=urllib.parse.quote(attachment_id, safe=""),
		),
		headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json", "User-Agent": HTTP_USER_AGENT},
		method="GET",
	)
	try:
		with urllib.request.urlopen(request, timeout=20) as response:
			payload = response.read().decode()
	except urllib.error.HTTPError as exc:
		return None, f"Resend returned HTTP {exc.code}"
	except urllib.error.URLError as exc:
		return None, f"Resend request failed: {exc.reason}"
	except TimeoutError:
		return None, "Resend request timed out"

	try:
		data = json.loads(payload)
	except json.JSONDecodeError:
		return None, "Resend returned invalid JSON"
	if not isinstance(data, dict):
		return None, "Resend returned invalid attachment"
	return data, None


def _download_attachment(download_url: str) -> tuple[bytes | None, str | None]:
	if not download_url:
		return None, "missing Resend attachment download URL"

	request = urllib.request.Request(download_url, headers={"Accept": "*/*", "User-Agent": HTTP_USER_AGENT}, method="GET")
	try:
		with urllib.request.urlopen(request, timeout=30) as response:
			return response.read(), None
	except urllib.error.HTTPError as exc:
		return None, f"Resend attachment download returned HTTP {exc.code}"
	except urllib.error.URLError as exc:
		return None, f"Resend attachment download failed: {exc.reason}"
	except TimeoutError:
		return None, "Resend attachment download timed out"


def _existing_ticket_for_message(message_id: str) -> str | None:
	import frappe

	if not message_id:
		return None
	return frappe.db.get_value(
		"Communication",
		{"message_id": message_id, "reference_doctype": "HD Ticket"},
		"reference_name",
	)


def _customer_for_sender(sender_email: str) -> str | None:
	import frappe

	if not sender_email:
		return None

	contact = frappe.db.get_value("Contact Email", {"email_id": sender_email}, "parent")
	if not contact:
		return None

	return frappe.db.get_value(
		"Dynamic Link",
		{
			"parenttype": "Contact",
			"parent": contact,
			"link_doctype": "HD Customer",
		},
		"link_name",
	)


def _attachment_filename(attachment: dict[str, Any]) -> str:
	filename = str(attachment.get("filename") or attachment.get("name") or "attachment").strip()
	return filename or "attachment"


def _attachment_id(attachment: dict[str, Any]) -> str:
	return str(attachment.get("id") or attachment.get("attachment_id") or "").strip()


def _set_if_field(doc: Any, fieldname: str, value: Any) -> None:
	if value in (None, ""):
		return
	if doc.meta.has_field(fieldname):
		doc.set(fieldname, value)


def _save_attachments(
	ticket: Any,
	communication: Any,
	attachments: list[dict[str, Any]],
	email_id: str,
	api_key: str | None,
) -> list[dict[str, str]]:
	import frappe
	from frappe.utils.file_manager import save_file

	saved_files = []
	for attachment in attachments:
		if not isinstance(attachment, dict):
			continue

		attachment_detail = attachment
		if not attachment_detail.get("download_url"):
			attachment_detail, attachment_error = _fetch_received_attachment(
				email_id,
				_attachment_id(attachment),
				api_key,
			)
			if attachment_error:
				frappe.log_error(
					title="Loopjet Resend attachment fetch failed",
					message=f"{_attachment_filename(attachment)}: {attachment_error}",
				)
				continue

		content, download_error = _download_attachment(str(attachment_detail.get("download_url") or ""))
		if download_error or content is None:
			frappe.log_error(
				title="Loopjet Resend attachment download failed",
				message=f"{_attachment_filename(attachment_detail)}: {download_error}",
			)
			continue

		file_doc = save_file(
			_attachment_filename(attachment_detail),
			content,
			"Communication",
			communication.name,
			is_private=0,
		)
		saved_files.append(
			{
				"filename": file_doc.file_name,
				"file_url": file_doc.file_url,
			}
		)

	if saved_files:
		ticket.reload()
		file_links = "".join(
			f'<li><a href="{html.escape(file_info["file_url"])}">{html.escape(file_info["filename"])}</a></li>'
			for file_info in saved_files
		)
		ticket.description = (ticket.description or "") + f"<p><strong>Attached files:</strong></p><ul>{file_links}</ul>"
		ticket.save(ignore_permissions=True)
		if ticket.meta.has_field("attachment") and not ticket.get("attachment"):
			ticket.db_set("attachment", saved_files[0]["file_url"], update_modified=False)

	return saved_files


def _create_ticket(ticket_payload: dict[str, Any], api_key: str | None = None) -> str:
	import frappe
	from frappe.utils import now

	existing_ticket = _existing_ticket_for_message(ticket_payload["message_id"])
	if existing_ticket:
		return existing_ticket

	ticket = frappe.new_doc("HD Ticket")
	ticket.subject = ticket_payload["subject"]
	_set_if_field(ticket, "raised_by", ticket_payload["sender"])
	if frappe.db.exists("Email Account", SUPPORT_EMAIL_ACCOUNT):
		_set_if_field(ticket, "email_account", SUPPORT_EMAIL_ACCOUNT)
	_set_if_field(ticket, "via_customer_portal", 0)
	_set_if_field(ticket, "customer", _customer_for_sender(ticket_payload["sender"]))
	ticket.insert(ignore_permissions=True)
	ticket.db_set("description", ticket_payload["description"], update_modified=False)
	ticket.reload()

	communication = frappe.new_doc("Communication")
	communication.communication_type = "Communication"
	communication.communication_medium = "Email"
	communication.sent_or_received = "Received"
	communication.subject = ticket_payload["full_subject"]
	communication.sender = ticket_payload["sender_raw"] or ticket_payload["sender"]
	communication.recipients = ticket_payload["recipients"]
	communication.cc = ticket_payload["cc"]
	communication.content = ticket_payload["description"]
	communication.text_content = ticket_payload["text_content"]
	communication.reference_doctype = "HD Ticket"
	communication.reference_name = ticket.name
	communication.communication_date = now()
	communication.message_id = ticket_payload["message_id"]
	if frappe.db.exists("Email Account", SUPPORT_EMAIL_ACCOUNT):
		communication.email_account = SUPPORT_EMAIL_ACCOUNT
	communication.insert(ignore_permissions=True)

	_save_attachments(
		ticket,
		communication,
		ticket_payload.get("attachments") or [],
		ticket_payload.get("email_id") or "",
		api_key,
	)

	frappe.db.commit()
	return ticket.name


def migrate_legacy_inbound_issues() -> list[dict[str, str]]:
	"""Move tickets created by the old Resend integration from Issue to HD Ticket."""
	import frappe

	if not frappe.db.exists("DocType", "HD Ticket"):
		return []

	legacy_communications = frappe.get_all(
		"Communication",
		filters={
			"reference_doctype": "Issue",
			"email_account": SUPPORT_EMAIL_ACCOUNT,
			"message_id": ["is", "set"],
		},
		fields=[
			"name",
			"reference_name",
			"message_id",
			"subject",
			"sender",
			"recipients",
			"cc",
			"content",
			"text_content",
		],
		order_by="creation asc",
	)

	migrated = []
	for communication in legacy_communications:
		if not frappe.db.exists("Issue", communication.reference_name):
			continue

		existing_ticket = _existing_ticket_for_message(communication.message_id)
		if existing_ticket:
			continue

		issue = frappe.get_doc("Issue", communication.reference_name)
		ticket_payload = {
			"subject": issue.subject or communication.subject or "(No subject)",
			"full_subject": communication.subject or issue.subject or "(No subject)",
			"sender": _extract_email_from_header(communication.sender or issue.raised_by),
			"sender_raw": communication.sender or issue.raised_by,
			"recipients": communication.recipients or "",
			"cc": communication.cc or "",
			"description": issue.description or communication.content or "",
			"text_content": communication.text_content or "",
			"message_id": communication.message_id,
			"email_id": "",
			"attachments": [],
		}

		ticket = frappe.new_doc("HD Ticket")
		ticket.subject = ticket_payload["subject"][:140]
		_set_if_field(ticket, "raised_by", ticket_payload["sender"])
		_set_if_field(ticket, "customer", _customer_for_sender(ticket_payload["sender"]))
		_set_if_field(ticket, "email_account", SUPPORT_EMAIL_ACCOUNT)
		_set_if_field(ticket, "via_customer_portal", 0)
		ticket.insert(ignore_permissions=True)
		ticket.db_set("description", ticket_payload["description"], update_modified=False)

		frappe.db.set_value(
			"Communication",
			communication.name,
			{
				"reference_doctype": "HD Ticket",
				"reference_name": ticket.name,
			},
			update_modified=False,
		)

		files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Issue",
				"attached_to_name": issue.name,
			},
			fields=["name", "file_url"],
		)
		for file_info in files:
			frappe.db.set_value(
				"File",
				file_info.name,
				{
					"attached_to_doctype": "Communication",
					"attached_to_name": communication.name,
				},
				update_modified=False,
			)
		if files and ticket.meta.has_field("attachment"):
			ticket.db_set("attachment", files[0].file_url, update_modified=False)

		migrated.append({"issue": issue.name, "ticket": ticket.name})

	if migrated:
		frappe.db.commit()
	return migrated


def _extract_event_data(event: dict[str, Any]) -> dict[str, Any]:
	data = event.get("data")
	return data if isinstance(data, dict) else {}


if frappe:
	resend_whitelist = frappe.whitelist(allow_guest=True)
else:
	def resend_whitelist(function: Any) -> Any:
		return function


@resend_whitelist
def resend_inbound() -> dict[str, Any]:
	"""Receive Resend inbound email webhooks and create Helpdesk tickets."""
	import frappe

	request = frappe.local.request
	if request.method != "POST":
		frappe.local.response.http_status_code = 405
		return {"ok": False, "error": "method_not_allowed"}

	raw_body = request.get_data(as_text=True) or "{}"
	form_token = frappe.form_dict.get("token") or request.args.get("token")
	if not _is_authorized(raw_body, form_token, request, frappe.conf):
		frappe.local.response.http_status_code = 403
		return {"ok": False, "error": "forbidden"}

	frappe.set_user("Administrator")

	try:
		event = json.loads(raw_body)
	except json.JSONDecodeError:
		frappe.local.response.http_status_code = 400
		return {"ok": False, "error": "invalid_json"}

	if event.get("type") != "email.received":
		return {"ok": True, "ignored": True, "event_type": event.get("type")}

	event_data = _extract_event_data(event)
	email_id = str(event_data.get("email_id") or event_data.get("id") or "")
	api_key = _get_resend_api_key()
	received_email, fetch_error = _fetch_received_email(email_id, api_key)
	email_data = {**event_data, **(received_email or {})}
	if email_id and "email_id" not in email_data:
		email_data["email_id"] = email_id

	ticket_payload = build_ticket_payload(email_data, fetch_error)
	existing_ticket = _existing_ticket_for_message(ticket_payload["message_id"])
	if existing_ticket:
		return {"ok": True, "duplicate": True, "ticket": existing_ticket}

	ticket_name = _create_ticket(ticket_payload, api_key)
	return {"ok": True, "ticket": ticket_name, "body_fetched": not bool(fetch_error)}
