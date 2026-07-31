from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from loopjet_frappe_custom.ai_sdr.domain import extract_json_object


class AIProviderError(RuntimeError):
	"""Raised when a configured AI provider cannot return a usable response."""


def _completion_url(base_url: str) -> str:
	return f"{base_url.rstrip('/')}/chat/completions"


def complete_json(
	*,
	base_url: str,
	api_key: str,
	model: str,
	system_prompt: str,
	user_prompt: str,
	timeout_seconds: int = 60,
	provider: str = "OpenRouter",
	app_url: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
	payload = {
		"model": model,
		"temperature": 0.2,
		"messages": [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
	}
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
		"User-Agent": "Loopjet-AI-SDR/1.0",
	}
	if provider == "OpenRouter":
		headers["X-Title"] = "Loopjet AI SDR"
		if app_url and app_url.startswith(("https://", "http://")):
			headers["HTTP-Referer"] = app_url
	request = urllib.request.Request(
		_completion_url(base_url),
		data=json.dumps(payload).encode("utf-8"),
		headers=headers,
		method="POST",
	)
	try:
		with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
			response_payload = json.loads(response.read().decode("utf-8"))
	except urllib.error.HTTPError as exc:
		detail = exc.read().decode("utf-8", errors="replace")[:500]
		raise AIProviderError(f"AI provider returned HTTP {exc.code}: {detail}") from exc
	except (OSError, ValueError) as exc:
		raise AIProviderError(f"AI provider request failed: {exc}") from exc

	try:
		content = response_payload["choices"][0]["message"]["content"]
	except (KeyError, IndexError, TypeError) as exc:
		raise AIProviderError("AI provider response did not contain message content.") from exc
	if isinstance(content, list):
		content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
	if not isinstance(content, str):
		raise AIProviderError("AI provider message content was not text.")

	try:
		result = extract_json_object(content)
	except ValueError as exc:
		raise AIProviderError(str(exc)) from exc

	usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
	return result, usage
