from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any
from urllib.parse import urlparse

REPLY_INTERESTED = "Interested"
REPLY_NEEDS_INFORMATION = "Needs Information"
REPLY_REFERRAL = "Referral"
REPLY_NOT_NOW = "Not Now"
REPLY_NOT_INTERESTED = "Not Interested"
REPLY_OUT_OF_OFFICE = "Out of Office"
REPLY_UNSUBSCRIBE = "Unsubscribe"
REPLY_UNKNOWN = "Needs Review"

REPLY_CATEGORIES = {
	REPLY_INTERESTED,
	REPLY_NEEDS_INFORMATION,
	REPLY_REFERRAL,
	REPLY_NOT_NOW,
	REPLY_NOT_INTERESTED,
	REPLY_OUT_OF_OFFICE,
	REPLY_UNSUBSCRIBE,
	REPLY_UNKNOWN,
}

ACTIVE_ENROLLMENT_STATUSES = {"Active", "Paused"}
TERMINAL_ENROLLMENT_STATUSES = {"Completed", "Stopped"}

_UNSUBSCRIBE_PATTERNS = (
	r"\bunsubscribe\b",
	r"\bremove me\b",
	r"\bdo not (?:email|contact|message)\b",
	r"\bstop (?:emailing|contacting|messaging)\b",
	r"\bopt[ -]?out\b",
	r"\bkeine weiteren (?:e-?mails|nachrichten)\b",
	r"\bnicht mehr kontaktieren\b",
)
_OUT_OF_OFFICE_PATTERNS = (
	r"\bout of (?:the )?office\b",
	r"\bautomatic reply\b",
	r"\bauto(?:matic)? response\b",
	r"\babwesen(?:d|heit)\b",
	r"\burlaub\b",
)
_NOT_INTERESTED_PATTERNS = (
	r"\bnot interested\b",
	r"\bno interest\b",
	r"\bkein interesse\b",
	r"\bnicht interessiert\b",
	r"\bno thank(?:s| you)\b",
)
_REFERRAL_PATTERNS = (
	r"\bcontact (?:my|our|the)\b",
	r"\bspeak (?:with|to)\b",
	r"\breach out to\b",
	r"\bzuständig\b",
	r"\bwenden sie sich an\b",
)
_NEEDS_INFORMATION_PATTERNS = (
	r"\bmore (?:information|details)\b",
	r"\bsend (?:me|us) (?:information|details)\b",
	r"\bhow does\b",
	r"\bweitere informationen\b",
	r"\bmehr details\b",
)
_INTERESTED_PATTERNS = (
	r"\binterested\b",
	r"\blet'?s (?:talk|meet|schedule)\b",
	r"\bbook (?:a )?(?:call|meeting|demo)\b",
	r"\bsounds (?:good|interesting)\b",
	r"\bgerne\b",
	r"\btermin\b",
	r"\binteressant\b",
)
_NOT_NOW_PATTERNS = (
	r"\bnot (?:right )?now\b",
	r"\blater this (?:month|quarter|year)\b",
	r"\bcheck back\b",
	r"\bcurrently no\b",
	r"\bspäter\b",
	r"\bderzeit nicht\b",
)
_SAFE_TEMPLATE_TOKEN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")


@dataclass(frozen=True)
class ReplyClassification:
	category: str
	confidence: int
	reason: str


def clamp_score(value: Any, minimum: int = 0, maximum: int = 100) -> int:
	try:
		numeric = round(float(value))
	except (TypeError, ValueError):
		return minimum
	return max(minimum, min(maximum, numeric))


def compute_icp_score(
	fit_score: Any,
	trigger_score: Any,
	persona_score: Any,
	data_quality_score: Any,
) -> int:
	"""Return a deterministic 0-100 ICP score from reviewed component scores."""
	weighted = (
		clamp_score(fit_score) * 0.45
		+ clamp_score(trigger_score) * 0.25
		+ clamp_score(persona_score) * 0.20
		+ clamp_score(data_quality_score) * 0.10
	)
	return clamp_score(weighted)


def icp_tier(score: Any) -> str:
	value = clamp_score(score)
	if value >= 80:
		return "A"
	if value >= 65:
		return "B"
	if value >= 50:
		return "C"
	return "D"


def normalize_email(value: str | None) -> str:
	return (value or "").strip().casefold()


def normalize_domain(value: str | None) -> str:
	"""Return a canonical host value for suppression matching.

	Any path, port, credentials, or fragment is removed. Subdomains remain
	distinct so existing domain-suppression keys keep their original semantics.
	"""
	domain = (value or "").strip().casefold()
	if not domain:
		return ""
	if "@" in domain and "://" not in domain:
		domain = domain.rsplit("@", 1)[1]
	parsed = urlparse(domain if "://" in domain else f"//{domain}")
	domain = (parsed.hostname or "").strip(".")
	if not domain or any(character.isspace() for character in domain):
		return ""
	try:
		return domain.encode("idna").decode("ascii")
	except UnicodeError:
		return ""


def normalize_company_domain(value: str | None) -> str:
	"""Normalize a company duplicate key and ignore the presentation-only www prefix."""
	domain = normalize_domain(value)
	return domain[4:] if domain.startswith("www.") else domain


def canonical_company_website(value: str | None) -> str:
	"""Normalize a company website to a stable HTTPS origin."""
	domain = normalize_company_domain(value)
	return f"https://{domain}" if domain else ""


def normalize_outbound_icp_score(value: Any) -> int:
	"""Accept either the proposal's 0-10 score or the workspace's 0-100 score."""
	try:
		numeric = float(value)
	except (TypeError, ValueError):
		return 0
	if 0 <= numeric <= 10:
		numeric *= 10
	return clamp_score(numeric)


def split_person_name(value: str | None) -> tuple[str, str]:
	"""Split a reviewed display name without guessing titles or salutations."""
	parts = (value or "").strip().split(maxsplit=1)
	if not parts:
		return "", ""
	return parts[0], parts[1] if len(parts) > 1 else ""


def normalize_suppression_key(suppression_type: str, value: str | None) -> str:
	if suppression_type == "Email":
		return normalize_email(value)
	if suppression_type == "Domain":
		return normalize_domain(value)
	return (value or "").strip()


def suppression_candidates(
	*,
	email: str | None = None,
	lead: str | None = None,
	organization: str | None = None,
) -> list[tuple[str, str]]:
	candidates: list[tuple[str, str]] = []
	normalized_email = normalize_email(email)
	if normalized_email:
		candidates.append(("Email", normalized_email))
		domain = normalize_domain(normalized_email)
		if domain:
			candidates.append(("Domain", domain))
	if lead:
		candidates.append(("Lead", lead.strip()))
	if organization:
		candidates.append(("Organization", organization.strip()))
	return candidates


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
	return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_reply_fallback(subject: str | None, content: str | None) -> ReplyClassification:
	"""Conservative local classifier used before or without an AI provider."""
	text = " ".join(filter(None, [subject or "", strip_html(content or "")])).strip()
	if not text:
		return ReplyClassification(REPLY_UNKNOWN, 20, "The reply did not contain readable text.")
	if _matches_any(text, _UNSUBSCRIBE_PATTERNS):
		return ReplyClassification(REPLY_UNSUBSCRIBE, 99, "The reply contains an explicit stop request.")
	if _matches_any(text, _OUT_OF_OFFICE_PATTERNS):
		return ReplyClassification(
			REPLY_OUT_OF_OFFICE, 95, "The reply appears to be an automatic absence message."
		)
	if _matches_any(text, _NOT_INTERESTED_PATTERNS):
		return ReplyClassification(REPLY_NOT_INTERESTED, 92, "The reply explicitly declines the outreach.")
	if _matches_any(text, _REFERRAL_PATTERNS):
		return ReplyClassification(
			REPLY_REFERRAL, 78, "The reply appears to direct the sender to another person."
		)
	if _matches_any(text, _NEEDS_INFORMATION_PATTERNS):
		return ReplyClassification(
			REPLY_NEEDS_INFORMATION,
			82,
			"The reply asks for additional information.",
		)
	if _matches_any(text, _INTERESTED_PATTERNS):
		return ReplyClassification(
			REPLY_INTERESTED, 82, "The reply contains a positive meeting or interest signal."
		)
	if _matches_any(text, _NOT_NOW_PATTERNS):
		return ReplyClassification(REPLY_NOT_NOW, 78, "The reply asks to revisit the conversation later.")
	return ReplyClassification(REPLY_UNKNOWN, 35, "No high-confidence intent pattern was found.")


def strip_html(value: str) -> str:
	text = re.sub(r"<[^>]+>", " ", value)
	return re.sub(r"\s+", " ", text).strip()


def render_safe_template(
	template: str | None,
	context: dict[str, Any],
	*,
	escape_values: bool = True,
) -> str:
	"""Render reviewed scalar placeholders without evaluating Jinja or Python expressions."""
	allowed = {
		"first_name": context.get("first_name"),
		"last_name": context.get("last_name"),
		"organization": context.get("organization"),
		"job_title": context.get("job_title"),
	}
	allowed.update({f"lead.{key}": value for key, value in allowed.items()})

	def replace(match: re.Match[str]) -> str:
		token = match.group(1)
		if token not in allowed:
			return match.group(0)
		value = str(allowed[token] or "")
		return escape(value, quote=True) if escape_values else value

	return _SAFE_TEMPLATE_TOKEN.sub(replace, template or "")


def has_unresolved_template(value: str | None) -> bool:
	return bool(re.search(r"{{.*?}}", value or "", flags=re.DOTALL))


def extract_json_object(value: str) -> dict[str, Any]:
	"""Parse a model response containing JSON, optionally wrapped in a code fence."""
	text = (value or "").strip()
	if text.startswith("```"):
		text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
		text = re.sub(r"\s*```$", "", text)
	try:
		parsed = json.loads(text)
	except json.JSONDecodeError:
		start = text.find("{")
		end = text.rfind("}")
		if start < 0 or end <= start:
			raise ValueError("The AI provider did not return a JSON object.") from None
		try:
			parsed = json.loads(text[start : end + 1])
		except json.JSONDecodeError as exc:
			raise ValueError("The AI provider returned invalid JSON.") from exc
	if not isinstance(parsed, dict):
		raise ValueError("The AI provider response must be a JSON object.")
	return parsed


def validate_source_urls(urls: list[Any] | tuple[Any, ...] | None) -> list[str]:
	validated: list[str] = []
	for value in urls or []:
		url = str(value).strip()
		parsed = urlparse(url)
		if parsed.scheme not in {"http", "https"} or not parsed.netloc:
			continue
		if url not in validated:
			validated.append(url)
	return validated


def validate_outreach_result(result: dict[str, Any], allowed_sources: list[str]) -> dict[str, Any]:
	body = str(result.get("body") or "").strip()
	if not body:
		raise ValueError("The AI provider returned an empty outreach body.")
	used_sources = [
		url for url in validate_source_urls(result.get("evidence_urls")) if url in set(allowed_sources)
	]
	return {
		"subject": str(result.get("subject") or "").strip(),
		"body": body,
		"rationale": str(result.get("rationale") or "").strip(),
		"evidence_urls": used_sources,
		"confidence": clamp_score(result.get("confidence")),
	}


def validate_reply_result(result: dict[str, Any]) -> ReplyClassification:
	category = str(result.get("category") or "").strip()
	if category not in REPLY_CATEGORIES:
		category = REPLY_UNKNOWN
	return ReplyClassification(
		category=category,
		confidence=clamp_score(result.get("confidence")),
		reason=str(result.get("reason") or "").strip() or "AI classification",
	)


def next_action_at(
	base: datetime,
	delay_days: Any,
	*,
	now: datetime | None = None,
) -> datetime:
	current = now or datetime.now(tz=base.tzinfo or UTC)
	candidate = base + timedelta(days=max(0, clamp_score(delay_days, 0, 365)))
	return max(candidate, current)
