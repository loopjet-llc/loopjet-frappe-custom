from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from loopjet_frappe_custom.founder_cockpit.domain import (
	SURFACE_DECISION,
	SURFACE_TODAY,
	SURFACE_WATCHLIST,
	dedupe_and_prioritize,
	priority_band,
	roles_allow_cockpit,
	validate_safe_action,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "founder_cockpit_candidates.json"
SETTINGS = {
	"critical_priority_score": 90,
	"high_priority_score": 75,
	"medium_priority_score": 50,
	"age_boost_days": 7,
	"max_cards": 100,
}
NOW = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)


def fixture_candidates() -> list[dict]:
	return json.loads(FIXTURE.read_text())


def test_representative_fixture_covers_every_required_operating_domain() -> None:
	domains = {candidate["domain"] for candidate in fixture_candidates()}

	assert domains == {"Sales", "Clients", "Finance", "Operations", "Team"}


def test_exception_selection_is_deduplicated_and_surfaces_are_mutually_exclusive() -> None:
	surfaces = dedupe_and_prioritize(fixture_candidates(), SETTINGS, now=NOW)
	all_cards = [card for cards in surfaces.values() for card in cards]

	assert len(all_cards) == 5
	assert len({card["card_id"] for card in all_cards}) == 5
	assert len({(card["source_doctype"], card["source_name"]) for card in all_cards}) == 5
	lead = next(card for card in all_cards if card["source_name"] == "CRM-LEAD-DEMO-1")
	assert lead["surface"] == SURFACE_DECISION
	assert set(lead["conditions"]) == {"priority-lead", "missing-next-step"}
	assert "No next step" in lead["reason"]
	assert "High-priority" in lead["reason"]


def test_priority_and_due_state_route_cards_to_the_expected_surfaces() -> None:
	surfaces = dedupe_and_prioritize(fixture_candidates(), SETTINGS, now=NOW)

	assert {card["source_name"] for card in surfaces[SURFACE_DECISION]} == {
		"CRM-LEAD-DEMO-1",
		"ACC-SINV-DEMO-1",
	}
	assert {card["source_name"] for card in surfaces[SURFACE_TODAY]} == {
		"HD-TICKET-DEMO-1",
		"ERROR-DEMO-1",
	}
	assert {card["source_name"] for card in surfaces[SURFACE_WATCHLIST]} == {"TASK-DEMO-1"}
	assert priority_band(90, SETTINGS) == "Critical"
	assert priority_band(75, SETTINGS) == "High"
	assert priority_band(50, SETTINGS) == "Medium"


def test_multi_company_scope_is_preserved_on_each_visible_card() -> None:
	surfaces = dedupe_and_prioritize(fixture_candidates(), SETTINGS, now=NOW)
	cards = {card["source_name"]: card for items in surfaces.values() for card in items}

	assert cards["ACC-SINV-DEMO-1"]["company"] == "Loopjet LLC"
	assert cards["HD-TICKET-DEMO-1"]["company"] == "Loopjet Malaysia Sdn. Bhd."


def test_acknowledging_a_card_hides_only_that_stable_exception_set() -> None:
	first = dedupe_and_prioritize(fixture_candidates(), SETTINGS, now=NOW)
	invoice = next(card for card in first[SURFACE_DECISION] if card["source_name"] == "ACC-SINV-DEMO-1")
	second = dedupe_and_prioritize(
		fixture_candidates(),
		SETTINGS,
		now=NOW,
		acknowledged_card_ids=[invoice["card_id"]],
	)
	remaining = [card for cards in second.values() for card in cards]

	assert "ACC-SINV-DEMO-1" not in {card["source_name"] for card in remaining}
	assert "CRM-LEAD-DEMO-1" in {card["source_name"] for card in remaining}


def test_explicit_dedupe_key_groups_cross_source_operational_evidence_and_stabilizes_ack() -> None:
	candidates = [
		{
			"domain": "Operations",
			"exception_type": "Scheduled job failure",
			"condition": "scheduled-job:raven",
			"source_doctype": "Scheduled Job Log",
			"source_name": "JOB-LOG-LATEST",
			"title": "Raven job failed",
			"reason": "The scheduled job failed.",
			"recommended_action": "Inspect the job.",
			"base_score": 88,
			"dedupe_key": "operations:raven-notifications",
		},
		{
			"domain": "Operations",
			"exception_type": "Repeated application error",
			"condition": "error:raven-secret",
			"source_doctype": "Error Log",
			"source_name": "ERROR-LOG-LATEST",
			"title": "Raven integration failed",
			"reason": "The related error repeated.",
			"recommended_action": "Inspect the error.",
			"base_score": 92,
			"dedupe_key": "operations:raven-notifications",
		},
	]
	first = dedupe_and_prioritize(candidates, SETTINGS, now=NOW)
	cards = [card for surface in first.values() for card in surface]

	assert len(cards) == 1
	assert "scheduled job failed" in cards[0]["reason"].lower()
	assert "related error repeated" in cards[0]["reason"].lower()

	candidates[0]["source_name"] = "JOB-LOG-NEWER"
	candidates[1]["source_name"] = "ERROR-LOG-NEWER"
	second = dedupe_and_prioritize(candidates, SETTINGS, now=NOW)
	new_card = next(card for surface in second.values() for card in surface)
	assert new_card["card_id"] == cards[0]["card_id"]


def test_rbac_requires_an_explicit_cockpit_or_system_role() -> None:
	assert roles_allow_cockpit(["Founder Cockpit User"], "founder@example.com") is True
	assert roles_allow_cockpit(["System Manager"], "manager@example.com") is True
	assert roles_allow_cockpit(["Sales User"], "sales@example.com") is False
	assert roles_allow_cockpit([], "Administrator") is True


def test_safe_actions_reject_destructive_or_unbounded_requests() -> None:
	validate_safe_action("acknowledge", "Sales Invoice", "ACC-SINV-DEMO-1")
	validate_safe_action(
		"schedule_follow_up",
		"CRM Lead",
		"CRM-LEAD-DEMO-1",
		due_date="2026-09-03",
		today=date(2026, 9, 2),
	)

	with pytest.raises(ValueError, match="not allowed"):
		validate_safe_action("submit_invoice", "Sales Invoice", "ACC-SINV-DEMO-1")
	with pytest.raises(ValueError, match="past"):
		validate_safe_action(
			"schedule_follow_up",
			"CRM Lead",
			"CRM-LEAD-DEMO-1",
			due_date="2026-09-01",
			today=date(2026, 9, 2),
		)
	with pytest.raises(ValueError, match="identifier"):
		validate_safe_action("acknowledge", "CRM Lead", "x" * 141)
