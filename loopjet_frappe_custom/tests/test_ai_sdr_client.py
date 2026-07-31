from __future__ import annotations

import json
from unittest.mock import patch

from loopjet_frappe_custom.ai_sdr.client import complete_json


class FakeResponse:
	def __init__(self, payload: dict) -> None:
		self.payload = payload

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, traceback):
		return False

	def read(self) -> bytes:
		return json.dumps(self.payload).encode()


def test_openai_compatible_client_returns_json_and_usage() -> None:
	response = FakeResponse(
		{
			"choices": [
				{"message": {"content": '{"subject":"Hello","body":"Reviewed draft","confidence":90}'}}
			],
			"usage": {"prompt_tokens": 10, "completion_tokens": 4},
		}
	)

	with patch("urllib.request.urlopen", return_value=response) as urlopen:
		result, usage = complete_json(
			base_url="https://ai.example/v1",
			api_key="secret",
			model="configured-model",
			system_prompt="System",
			user_prompt="User",
			provider="Custom OpenAI-compatible",
		)

	assert result["body"] == "Reviewed draft"
	assert usage["prompt_tokens"] == 10
	request = urlopen.call_args.args[0]
	assert request.full_url == "https://ai.example/v1/chat/completions"
	assert request.headers["Authorization"] == "Bearer secret"


def test_openrouter_client_adds_attribution_headers() -> None:
	response = FakeResponse(
		{
			"choices": [{"message": {"content": '{"connected":true}'}}],
			"usage": {},
		}
	)

	with patch("urllib.request.urlopen", return_value=response) as urlopen:
		result, _usage = complete_json(
			base_url="https://openrouter.ai/api/v1",
			api_key="secret",
			model="provider/model",
			system_prompt="System",
			user_prompt="User",
			provider="OpenRouter",
			app_url="https://crm.loopjet.io",
		)

	assert result == {"connected": True}
	request = urlopen.call_args.args[0]
	assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
	assert request.get_header("X-title") == "Loopjet AI SDR"
	assert request.get_header("Http-referer") == "https://crm.loopjet.io"
