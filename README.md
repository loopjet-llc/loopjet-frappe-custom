# Loopjet Frappe Custom

Upgrade-safe Loopjet extensions for Frappe Framework v16, ERPNext, Frappe HR,
Frappe CRM, and Frappe Helpdesk.

On ERPNext sites with Raven installed, the app keeps a **Raven Chat** URL
shortcut in both the public Home workspace and Frappe v16's dedicated Home
sidebar so colleagues can open `/raven` directly from the Desk.

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

## AI SDR for Frappe CRM

The CRM site includes a supervised AI SDR workspace at `/app/ai-sdr`. It adds
account research, deterministic ICP scoring, human-approved outreach drafts,
multi-step sequences, reply classification, suppression handling, and CRM task
handoff without copying or modifying Frappe CRM source. OpenRouter is the
first-class AI provider, and the workspace shows AI as active only after a real
model connection test succeeds.

Installation is safe by default: AI generation and approved email delivery are
both disabled until a System Manager configures and explicitly enables them.
LinkedIn and call steps are always manual, and every outbound step requires
recorded human approval.

See [AI SDR operations](docs/ai-sdr.md) for roles, configuration, daily use,
safety boundaries, and production rollout.
