from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from loopjet_frappe_custom.ai_sdr.domain import (
	REPLY_INTERESTED,
	REPLY_UNSUBSCRIBE,
	classify_reply_fallback,
	compute_icp_score,
	extract_json_object,
	has_unresolved_template,
	icp_tier,
	next_action_at,
	normalize_suppression_key,
	render_safe_template,
	suppression_candidates,
	validate_outreach_result,
)


def test_icp_score_is_deterministic_and_tiered() -> None:
	score = compute_icp_score(100, 80, 60, 40)

	assert score == 81
	assert icp_tier(score) == "A"
	assert icp_tier(79) == "B"
	assert icp_tier(64) == "C"
	assert icp_tier(49) == "D"


def test_explicit_unsubscribe_wins_over_positive_language() -> None:
	result = classify_reply_fallback(
		"Interested",
		"Sounds interesting, but please unsubscribe me and do not email again.",
	)

	assert result.category == REPLY_UNSUBSCRIBE
	assert result.confidence == 99


def test_positive_german_reply_is_detected() -> None:
	result = classify_reply_fallback("Re: Qualifizierung", "Das klingt interessant. Gerne einen Termin.")

	assert result.category == REPLY_INTERESTED


def test_json_object_can_be_extracted_from_a_code_fence() -> None:
	assert extract_json_object('```json\n{"confidence": 88}\n```') == {"confidence": 88}


def test_invalid_ai_json_is_rejected() -> None:
	with pytest.raises(ValueError, match="JSON object"):
		extract_json_object("There is no structured response here.")


def test_outreach_result_only_keeps_known_evidence_urls() -> None:
	result = validate_outreach_result(
		{
			"subject": "A relevant question",
			"body": "Hello, this draft uses reviewed evidence.",
			"confidence": 91,
			"evidence_urls": ["https://known.example/source", "https://invented.example/claim"],
		},
		["https://known.example/source"],
	)

	assert result["evidence_urls"] == ["https://known.example/source"]


def test_suppression_normalization_covers_email_and_domain() -> None:
	assert normalize_suppression_key("Email", " Person@Example.COM ") == "person@example.com"
	assert normalize_suppression_key("Domain", "https://WWW.Example.COM/path") == "www.example.com"
	assert suppression_candidates(email="Person@Example.com", lead="CRM-LEAD-1") == [
		("Email", "person@example.com"),
		("Domain", "example.com"),
		("Lead", "CRM-LEAD-1"),
	]


def test_next_action_never_schedules_in_the_past() -> None:
	base = datetime(2026, 7, 1, tzinfo=UTC)
	current = datetime(2026, 7, 31, tzinfo=UTC)

	assert next_action_at(base, 2, now=current) == current


def test_fallback_templates_only_replace_reviewed_scalar_tokens() -> None:
	rendered = render_safe_template(
		"Hi {{ first_name }} from {{ lead.organization }}: {{ cycler.__init__ }}",
		{
			"first_name": "<Alex>",
			"organization": "Example & Co",
		},
	)

	assert rendered == (
		"Hi &lt;Alex&gt; from Example &amp; Co: {{ cycler.__init__ }}"
	)
	assert has_unresolved_template(rendered)


def test_plain_text_template_values_are_not_html_escaped() -> None:
	assert (
		render_safe_template(
			"Re: {{ organization }}",
			{"organization": "Example & Co"},
			escape_values=False,
		)
		== "Re: Example & Co"
	)


def test_structured_evidence_json_remains_serializable() -> None:
	payload = {"source": "https://example.com", "score": compute_icp_score(80, 70, 60, 50)}

	assert json.loads(json.dumps(payload))["score"] == 70
