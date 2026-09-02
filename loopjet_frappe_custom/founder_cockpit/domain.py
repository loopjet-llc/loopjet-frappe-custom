from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

SURFACE_DECISION = "needs_decision"
SURFACE_TODAY = "today"
SURFACE_WATCHLIST = "watchlist"
SURFACES = (SURFACE_DECISION, SURFACE_TODAY, SURFACE_WATCHLIST)
SAFE_ACTIONS = {"acknowledge", "schedule_follow_up", "open_source"}


def clamp(value: Any, minimum: int = 0, maximum: int = 100) -> int:
	try:
		numeric = round(float(value))
	except (TypeError, ValueError):
		numeric = minimum
	return max(minimum, min(maximum, numeric))


def parse_datetime(value: Any) -> datetime | None:
	if not value:
		return None
	if isinstance(value, datetime):
		return value if value.tzinfo else value.replace(tzinfo=UTC)
	if isinstance(value, date):
		return datetime(value.year, value.month, value.day, tzinfo=UTC)
	text = str(value).strip().replace("Z", "+00:00")
	try:
		parsed = datetime.fromisoformat(text)
	except ValueError:
		try:
			parsed_date = date.fromisoformat(text[:10])
		except ValueError:
			return None
		parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day)
	return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def priority_band(score: Any, settings: dict[str, Any]) -> str:
	value = clamp(score)
	if value >= clamp(settings.get("critical_priority_score", 90)):
		return "Critical"
	if value >= clamp(settings.get("high_priority_score", 75)):
		return "High"
	if value >= clamp(settings.get("medium_priority_score", 50)):
		return "Medium"
	return "Low"


def score_candidate(candidate: dict[str, Any], settings: dict[str, Any], now: datetime) -> int:
	score = clamp(candidate.get("base_score", 50))
	if candidate.get("needs_decision"):
		score += 8

	due_at = parse_datetime(candidate.get("due_at"))
	if due_at:
		days_until_due = (due_at.date() - now.date()).days
		if days_until_due < 0:
			score += min(14, 8 + abs(days_until_due))
		elif days_until_due == 0:
			score += 7
		elif days_until_due <= 2:
			score += 3

	occurred_at = parse_datetime(candidate.get("occurred_at"))
	if occurred_at:
		age_days = max(0, (now.date() - occurred_at.date()).days)
		candidate["age_days"] = age_days
		if age_days >= clamp(settings.get("age_boost_days", 7), 1, 365):
			score += min(8, age_days // max(1, clamp(settings.get("age_boost_days", 7), 1, 365)))

	return clamp(score)


def condition_fingerprint(candidate: dict[str, Any]) -> str:
	if candidate.get("dedupe_key"):
		parts = (
			str(candidate["dedupe_key"]),
			str(candidate.get("condition") or candidate.get("exception_type") or "exception"),
		)
		return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
	parts = (
		str(candidate.get("source_doctype") or ""),
		str(candidate.get("source_name") or ""),
		str(candidate.get("condition") or candidate.get("exception_type") or "exception"),
	)
	return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def source_key(candidate: dict[str, Any]) -> str:
	if candidate.get("dedupe_key"):
		return str(candidate["dedupe_key"])
	doctype = str(candidate.get("source_doctype") or "Exception")
	name = str(candidate.get("source_name") or condition_fingerprint(candidate))
	return f"{doctype}:{name}"


def card_fingerprint(candidates: Iterable[dict[str, Any]]) -> str:
	fingerprints = sorted(condition_fingerprint(candidate) for candidate in candidates)
	return hashlib.sha256("|".join(fingerprints).encode()).hexdigest()[:32]


def _surface_for(candidate: dict[str, Any], settings: dict[str, Any], now: datetime) -> str:
	if candidate.get("needs_decision"):
		return SURFACE_DECISION
	due_at = parse_datetime(candidate.get("due_at"))
	if due_at and due_at.date() <= now.date():
		return SURFACE_TODAY
	if candidate.get("priority") == "Critical":
		return SURFACE_TODAY
	return SURFACE_WATCHLIST


def dedupe_and_prioritize(
	candidates: Iterable[dict[str, Any]],
	settings: dict[str, Any],
	*,
	now: datetime | None = None,
	acknowledged_card_ids: Iterable[str] = (),
) -> dict[str, list[dict[str, Any]]]:
	current = now or datetime.now(tz=UTC)
	if not current.tzinfo:
		current = current.replace(tzinfo=UTC)
	acknowledged = set(acknowledged_card_ids)
	grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for raw_candidate in candidates:
		candidate = dict(raw_candidate)
		if not candidate.get("source_doctype") or not candidate.get("source_name"):
			continue
		candidate["priority_score"] = score_candidate(candidate, settings, current)
		candidate["priority"] = priority_band(candidate["priority_score"], settings)
		grouped[source_key(candidate)].append(candidate)

	surfaces: dict[str, list[dict[str, Any]]] = {surface: [] for surface in SURFACES}
	for group in grouped.values():
		group.sort(key=lambda item: (item["priority_score"], bool(item.get("needs_decision"))), reverse=True)
		card_id = card_fingerprint(group)
		if card_id in acknowledged:
			continue
		primary = dict(group[0])
		primary["card_id"] = card_id
		primary["needs_decision"] = any(item.get("needs_decision") for item in group)
		primary["conditions"] = [item.get("condition") for item in group if item.get("condition")]
		reasons = list(dict.fromkeys(str(item.get("reason") or "").strip() for item in group))
		primary["reason"] = " · ".join(reason for reason in reasons if reason)
		primary["surface"] = _surface_for(primary, settings, current)
		primary.pop("base_score", None)
		surfaces[primary["surface"]].append(primary)

	max_cards = clamp(settings.get("max_cards", 100), 10, 250)
	for surface in SURFACES:
		surfaces[surface].sort(
			key=lambda item: (
				-item["priority_score"],
				parse_datetime(item.get("due_at")) or datetime.max.replace(tzinfo=UTC),
				str(item.get("title") or ""),
			)
		)
		surfaces[surface] = surfaces[surface][:max_cards]
	return surfaces


def roles_allow_cockpit(roles: Iterable[str], user: str | None = None) -> bool:
	return user == "Administrator" or bool(set(roles).intersection({"System Manager", "Founder Cockpit User"}))


def validate_safe_action(
	action: str,
	source_doctype: str,
	source_name: str,
	*,
	due_date: Any = None,
	today: date | None = None,
) -> None:
	if action not in SAFE_ACTIONS:
		raise ValueError("This cockpit action is not allowed.")
	if not source_doctype or not source_name:
		raise ValueError("A source document is required.")
	if len(source_doctype) > 140 or len(source_name) > 140:
		raise ValueError("The source document identifier is invalid.")
	if not re.fullmatch(r"[A-Za-z0-9 _-]+", source_doctype):
		raise ValueError("The source document type is invalid.")
	if action != "schedule_follow_up":
		return
	parsed = parse_datetime(due_date)
	if not parsed:
		raise ValueError("A valid follow-up date is required.")
	current_date = today or date.today()
	if parsed.date() < current_date:
		raise ValueError("A follow-up cannot be scheduled in the past.")
	if (parsed.date() - current_date).days > 366:
		raise ValueError("A follow-up cannot be scheduled more than one year ahead.")
