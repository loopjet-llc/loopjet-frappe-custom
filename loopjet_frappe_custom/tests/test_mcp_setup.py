import json
from pathlib import Path

from loopjet_frappe_custom.mcp_setup import build_connection_payload

ROOT = Path(__file__).resolve().parents[2]


def test_connection_payload_contains_chatgpt_and_claude_snippets() -> None:
	payload = build_connection_payload(
		"https://mcp.loopjet.io/mcp",
		api_key="key_123",
		api_secret="secret_456",
	)

	chatgpt_tool = json.loads(payload["chatgpt_api_tool_json"])
	assert chatgpt_tool["type"] == "mcp"
	assert chatgpt_tool["server_url"] == "https://mcp.loopjet.io/mcp"
	assert chatgpt_tool["authorization"] == "key_123:secret_456"
	assert chatgpt_tool["require_approval"] == "always"

	claude_config = json.loads(payload["claude_api_json"])
	assert claude_config["mcp_servers"][0]["type"] == "url"
	assert claude_config["mcp_servers"][0]["authorization_token"] == "key_123:secret_456"
	assert claude_config["tools"][0]["type"] == "mcp_toolset"
	assert claude_config["betas"] == ["mcp-client-2025-11-20"]

	assert "Authorization: Bearer key_123:secret_456" in payload["bearer_header"]
	assert "claude mcp add --transport http" in payload["claude_code_command"]
	assert "--header \"Authorization: Bearer key_123:secret_456\"" in payload["claude_code_command"]


def test_connection_payload_uses_placeholders_without_secret() -> None:
	payload = build_connection_payload("https://mcp.loopjet.io/mcp", api_key="key_123")

	assert payload["token_was_included"] is False
	assert "<frappe_api_key>:<frappe_api_secret>" in payload["chatgpt_api_tool_json"]
	assert "<frappe_api_key>:<frappe_api_secret>" in payload["claude_api_json"]


def test_mcp_setup_page_assets_exist() -> None:
	page_dir = ROOT / "loopjet_frappe_custom" / "loopjet_custom" / "page" / "mcp_setup"
	page_json = json.loads((page_dir / "mcp_setup.json").read_text())
	page_js = (page_dir / "mcp_setup.js").read_text()

	assert page_json["doctype"] == "Page"
	assert page_json["name"] == "mcp-setup"
	assert page_json["module"] == "Loopjet Custom"
	assert "loopjet_frappe_custom.mcp_setup.generate_mcp_api_key" in page_js
	assert "ChatGPT API / Responses API" in page_js
	assert "Claude Code" in page_js
