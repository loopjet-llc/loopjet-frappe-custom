# Loopjet Frappe Custom

Upgrade-safe Loopjet extensions for Frappe Framework v16, ERPNext, Frappe HR,
Frappe CRM, and Frappe Helpdesk.

## Design rules

- Never copy or edit upstream product code here.
- Prefer Frappe hooks, fixtures, custom DocTypes, workflows, and documented APIs.
- Keep integrations optional so the app can be installed on ERP, CRM, or Helpdesk sites.
- Every schema or data change must be represented by a patch and be safe to run twice.
- Export supported Desk customizations to fixtures before deploying them.

## Local checks

```bash
python -m compileall loopjet_frappe_custom
ruff check .
pytest
```

Full Frappe installation and migration tests live in the deployment repository.

## MCP setup UI

The Desk page `/app/mcp-setup` lets each signed-in Frappe user generate, rotate,
and revoke their own MCP API key. It shows ready-to-copy connection snippets for
Claude, ChatGPT/OpenAI API, Codex, MCP Inspector, and other remote HTTP MCP
clients. The API secret is only displayed immediately after generation.
