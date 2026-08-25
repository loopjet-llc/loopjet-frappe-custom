from types import SimpleNamespace

import loopjet_frappe_custom.helpdesk_notifications as notifications
from loopjet_frappe_custom.helpdesk_notifications import (
	build_notification_message,
	build_notification_subject,
	build_ticket_changes,
	build_ticket_url,
	deduplicate_emails,
	get_ticket_customer_recipients,
)


def test_ticket_changes_include_only_customer_relevant_fields() -> None:
	before = {
		"subject": "API issue",
		"status": "Open",
		"priority": "Medium",
		"ticket_type": "Bug",
		"agent_group": "Support",
	}
	after = {
		"subject": "API issue",
		"status": "Replied",
		"priority": "High",
		"ticket_type": "Bug",
		"agent_group": "Engineering",
	}

	assert build_ticket_changes(before, after) == [
		{"fieldname": "status", "label": "Status", "old": "Offen", "new": "Beantwortet"},
		{"fieldname": "priority", "label": "Priorität", "old": "Mittel", "new": "Hoch"},
	]


def test_recipient_addresses_are_normalized_and_deduplicated() -> None:
	assert deduplicate_emails(
		[
			"Ioannis Voudouris <I.Voudouris@hochschulwerbung.de>",
			"i.voudouris@hochschulwerbung.de",
			"not-an-email",
			None,
		]
	) == ["i.voudouris@hochschulwerbung.de"]


def test_ticket_recipients_include_requester_and_enabled_company_portal_users(monkeypatch) -> None:
	class FakeDatabase:
		@staticmethod
		def get_value(doctype, name, fields, as_dict=False):
			assert (doctype, name, fields, as_dict) == (
				"Contact",
				"Mihaela Contact",
				["email_id", "user"],
				True,
			)
			return SimpleNamespace(email_id="mihaela@customer.example", user=None)

	class FakeFrappe:
		db = FakeDatabase()

		@staticmethod
		def get_all(doctype, filters, pluck=None, fields=None):
			if doctype == "Dynamic Link":
				assert filters["link_name"] == "DHW"
				return ["Ioannis Contact", "Info Contact", "Inactive Contact"]
			if doctype == "Contact":
				return [
					SimpleNamespace(email_id="ioannis@customer.example", user="ioannis@customer.example"),
					SimpleNamespace(email_id="info@customer.example", user=None),
					SimpleNamespace(email_id="inactive@customer.example", user="inactive@customer.example"),
				]
			if doctype == "User":
				assert filters["enabled"] == 1
				assert filters["user_type"] == "Website User"
				return ["ioannis@customer.example"]
			raise AssertionError(f"Unexpected DocType: {doctype}")

	monkeypatch.setattr(notifications, "frappe", FakeFrappe())
	recipients = get_ticket_customer_recipients(
		{
			"raised_by": "mihaela@customer.example",
			"contact": "Mihaela Contact",
			"customer": "DHW",
		}
	)

	assert recipients == ["mihaela@customer.example", "ioannis@customer.example"]


def test_ticket_link_uses_customer_portal_route() -> None:
	assert build_ticket_url("0047") == "https://helpdesk.loopjet.io/helpdesk/my-tickets/0047"


def test_change_email_contains_actor_diff_and_direct_ticket_link() -> None:
	message = build_notification_message(
		ticket_name="0047",
		ticket_subject="CloudMensa Rechtevergabe",
		actor_name="Ahmad El-Ali",
		ticket_url="https://helpdesk.loopjet.io/helpdesk/my-tickets/0047",
		changes=[{"label": "Priorität", "old": "Mittel", "new": "Hoch"}],
	)

	assert "Ahmad El-Ali" in message
	assert "Priorität" in message
	assert "Mittel" in message
	assert "Hoch" in message
	assert "https://helpdesk.loopjet.io/helpdesk/my-tickets/0047" in message
	assert build_notification_subject("0047", "CloudMensa Rechtevergabe") == (
		"Ticket aktualisiert: #0047 - CloudMensa Rechtevergabe"
	)


def test_comment_email_contains_comment_and_escapes_ticket_metadata() -> None:
	message = build_notification_message(
		ticket_name="<0047>",
		ticket_subject="Ticket <script>alert(1)</script>",
		actor_name="Ahmad <Support>",
		ticket_url="https://helpdesk.loopjet.io/helpdesk/my-tickets/0047?a=1&b=2",
		comment_html="<p>Die Anpassung ist jetzt live.</p>",
	)

	assert "<p>Die Anpassung ist jetzt live.</p>" in message
	assert "Ahmad &lt;Support&gt;" in message
	assert "Ticket &lt;script&gt;alert(1)&lt;/script&gt;" in message
	assert "a=1&amp;b=2" in message
	assert build_notification_subject("0047", "CloudMensa", is_comment=True) == (
		"Neuer Kommentar: #0047 - CloudMensa"
	)
