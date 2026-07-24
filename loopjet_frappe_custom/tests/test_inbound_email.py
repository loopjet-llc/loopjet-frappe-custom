from loopjet_frappe_custom.inbound_email import build_recovery_ticket_payload, build_ticket_payload


def test_build_ticket_payload_prefers_html_body() -> None:
	payload = build_ticket_payload(
		{
			"from": "Client Success <client@example.com>",
			"to": ["support@loopjet.io"],
			"cc": ["team@example.com"],
			"subject": "Production API issue",
			"html": "<p>The API is returning 500s.</p>",
			"text": "The API is returning 500s.",
			"message_id": "<message-1@example.com>",
		}
	)

	assert payload["subject"] == "Production API issue"
	assert payload["sender"] == "client@example.com"
	assert payload["recipients"] == "support@loopjet.io"
	assert payload["cc"] == "team@example.com"
	assert payload["description"] == "<p>The API is returning 500s.</p>"
	assert payload["message_id"] == "<message-1@example.com>"


def test_build_ticket_payload_falls_back_to_resend_metadata() -> None:
	payload = build_ticket_payload(
		{
			"email_id": "email_123",
			"from": "sender@example.com",
			"to": ["support@loopjet.io"],
			"subject": "",
			"attachments": [{"filename": "screenshot.png", "content_type": "image/png", "size": 2048}],
		},
		fetch_error="Resend returned HTTP 404",
	)

	assert payload["subject"] == "(No subject)"
	assert payload["message_id"] == "email_123"
	assert "Resend returned HTTP 404" in payload["description"]
	assert "screenshot.png" in payload["description"]


def test_build_recovery_ticket_payload_preserves_message_metadata_without_attachments() -> None:
	payload = build_recovery_ticket_payload(
		{
			"email_id": "email_recovery_123",
			"message_id": "<recovery@example.com>",
			"from": "Sender Name <sender@example.com>",
			"to": ["support@inbound.loopjet.io"],
			"subject": "Attachment processing failed",
			"attachments": [{"id": "attachment_123", "filename": "broken.pdf"}],
		}
	)

	assert payload["subject"] == "Attachment processing failed"
	assert payload["sender"] == "sender@example.com"
	assert payload["recipients"] == "support@inbound.loopjet.io"
	assert payload["message_id"] == "<recovery@example.com>"
	assert payload["attachments"] == []
	assert "recovered from webhook metadata" in payload["description"]
	assert "broken.pdf" not in payload["description"]
