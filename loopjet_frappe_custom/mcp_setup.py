from __future__ import annotations

import json
from typing import Any

try:
	import frappe
except ImportError:  # pragma: no cover - lets snippet tests run outside a Frappe bench
	frappe = None  # type: ignore[assignment]

DEFAULT_MCP_SERVER_URL = "https://mcp.loopjet.io/mcp"
MCP_SERVER_CONFIG_KEY = "loopjet_mcp_server_url"
MCP_SERVER_LABEL = "loopjet_frappe"
MCP_SERVER_NAME = "loopjet-frappe"
MCP_DESCRIPTION = "Loopjet Frappe ERPNext, CRM, HR, and Helpdesk control tools."


def _whitelist(func: Any) -> Any:
	if frappe is None:
		return func
	return frappe.whitelist(allow_guest=False)(func)


def get_mcp_server_url() -> str:
	if frappe is None:
		return DEFAULT_MCP_SERVER_URL
	configured = getattr(frappe.conf, MCP_SERVER_CONFIG_KEY, None)
	return str(configured or DEFAULT_MCP_SERVER_URL).rstrip("/")


def build_connection_payload(
	server_url: str,
	api_key: str | None = None,
	api_secret: str | None = None,
) -> dict[str, Any]:
	token = f"{api_key}:{api_secret}" if api_key and api_secret else "<frappe_api_key>:<frappe_api_secret>"

	chatgpt_api = {
		"type": "mcp",
		"server_label": MCP_SERVER_LABEL,
		"server_description": MCP_DESCRIPTION,
		"server_url": server_url,
		"authorization": token,
		"require_approval": "always",
	}
	claude_api = {
		"mcp_servers": [
			{
				"type": "url",
				"url": server_url,
				"name": MCP_SERVER_NAME,
				"authorization_token": token,
			}
		],
		"tools": [{"type": "mcp_toolset", "mcp_server_name": MCP_SERVER_NAME}],
		"betas": ["mcp-client-2025-11-20"],
	}
	claude_code = (
		f"claude mcp add --transport http {MCP_SERVER_NAME} {server_url} "
		f"--header \"Authorization: Bearer {token}\""
	)
	codex_config = {
		"mcp_servers": {
			MCP_SERVER_NAME: {
				"url": server_url,
				"headers": {"Authorization": f"Bearer {token}"},
			}
		}
	}

	return {
		"server_url": server_url,
		"bearer_header": f"Authorization: Bearer {token}",
		"chatgpt_api_tool_json": json.dumps(chatgpt_api, indent=2),
		"chatgpt_developer_mode": {
			"name": "Loopjet Frappe",
			"description": MCP_DESCRIPTION,
			"mcp_server_url": server_url,
			"note": (
				"ChatGPT developer-mode apps support streaming HTTP MCP. "
				"Private per-user ChatGPT web apps may need an OAuth wrapper; "
				"use the API snippet for static bearer-token testing."
			),
		},
		"claude_api_json": json.dumps(claude_api, indent=2),
		"claude_code_command": claude_code,
		"codex_config_json": json.dumps(codex_config, indent=2),
		"token_was_included": bool(api_key and api_secret),
	}


def _current_user() -> str:
	if frappe is None:
		msg = "Frappe is required for MCP key operations"
		raise RuntimeError(msg)
	user = frappe.session.user
	if user in {"Guest", None, ""}:
		frappe.throw("Please log in before creating an MCP connection.")
	return user


def _get_user_doc() -> Any:
	return frappe.get_doc("User", _current_user())


@_whitelist
def get_mcp_setup_context() -> dict[str, Any]:
	"""Return MCP connection metadata for the current Frappe user."""
	user = _get_user_doc()
	server_url = get_mcp_server_url()
	return {
		"user": user.name,
		"server_url": server_url,
		"api_key": user.api_key or None,
		"has_api_key": bool(user.api_key),
		"secret_visible": False,
		"connections": build_connection_payload(server_url, user.api_key or None, None),
		"warnings": [
			"Your API secret is only shown immediately after generation.",
			"Use a dedicated Frappe user or minimal roles for production agents.",
			"Delete, submit, and cancel MCP tools still require explicit confirm=true.",
		],
	}


@_whitelist
def generate_mcp_api_key() -> dict[str, Any]:
	"""Generate or rotate the current user's Frappe API key/secret for MCP."""
	user = _get_user_doc()
	api_secret = frappe.generate_hash(length=32)
	if not user.api_key:
		user.api_key = frappe.generate_hash(length=20)
	user.api_secret = api_secret
	user.save(ignore_permissions=True)
	frappe.db.commit()

	server_url = get_mcp_server_url()
	return {
		"user": user.name,
		"server_url": server_url,
		"api_key": user.api_key,
		"api_secret": api_secret,
		"has_api_key": True,
		"secret_visible": True,
		"connections": build_connection_payload(server_url, user.api_key, api_secret),
	}


@_whitelist
def revoke_mcp_api_key() -> dict[str, Any]:
	"""Revoke the current user's Frappe API key/secret used for MCP."""
	user = _get_user_doc()
	user.api_key = None
	user.save(ignore_permissions=True)
	frappe.db.delete("__Auth", {"doctype": "User", "name": user.name, "fieldname": "api_secret"})
	frappe.db.commit()
	return get_mcp_setup_context()
