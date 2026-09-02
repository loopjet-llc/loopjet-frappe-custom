from __future__ import annotations

from loopjet_frappe_custom.founder_cockpit.collectors import _helpdesk_ticket_candidate


def test_new_unassigned_helpdesk_ticket_requires_a_decision_without_copying_body() -> None:
	row = {
		"name": "HD-TICKET-0001",
		"subject": "Cannot access account",
		"description": "private customer text",
		"status": "New",
		"status_category": "Open",
		"priority": "Medium",
		"creation": "2026-09-02 08:00:00",
		"modified": "2026-09-02 08:00:00",
		"_assign": "[]",
	}

	candidate = _helpdesk_ticket_candidate(row, 74, "2026-09-02")

	assert candidate is not None
	assert candidate["exception_type"] == "New helpdesk ticket"
	assert candidate["needs_decision"] is True
	assert candidate["source_url"] == "/helpdesk/tickets/HD-TICKET-0001"
	assert "assign an owner" in candidate["recommended_action"].lower()
	assert "private customer text" not in str(candidate)


def test_assigned_open_helpdesk_ticket_is_connected_without_forcing_founder_decision() -> None:
	row = {
		"name": "HD-TICKET-0002",
		"subject": "Invoice question",
		"status": "Open",
		"status_category": "Open",
		"priority": "Low",
		"creation": "2026-09-01 08:00:00",
		"modified": "2026-09-02 08:00:00",
		"_assign": '["agent@example.com"]',
	}

	candidate = _helpdesk_ticket_candidate(row, 74, "2026-09-02")

	assert candidate is not None
	assert candidate["exception_type"] == "Open helpdesk ticket"
	assert candidate["needs_decision"] is False
	assert candidate["owner"] == "agent@example.com"


def test_resolved_helpdesk_ticket_is_not_connected_as_open() -> None:
	row = {
		"name": "HD-TICKET-0003",
		"status": "Resolved",
		"status_category": "Resolved",
	}

	assert _helpdesk_ticket_candidate(row, 74, "2026-09-02") is None


def test_failed_sla_open_ticket_is_escalated_to_founder_decision() -> None:
	row = {
		"name": "HD-TICKET-0004",
		"subject": "Production unavailable",
		"status": "Open",
		"status_category": "Open",
		"priority": "Urgent",
		"agreement_status": "Failed",
		"resolution_by": "2026-09-02 07:00:00",
		"creation": "2026-09-01 08:00:00",
		"_assign": '["agent@example.com"]',
	}

	candidate = _helpdesk_ticket_candidate(row, 74, "2026-09-02")

	assert candidate is not None
	assert candidate["needs_decision"] is True
	assert candidate["base_score"] == 85
	assert "sla has failed" in candidate["reason"].lower()
