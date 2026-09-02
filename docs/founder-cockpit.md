# Founder Cockpit

The Founder Cockpit is a native Frappe Desk page at `/app/founder-cockpit`.
It aggregates actionable exceptions; it does not replace CRM, Helpdesk,
Accounts, Projects, assignments, or their timelines.

## First-release coverage

The server queries every source as the signed-in user with `frappe.get_list`.
Frappe DocType permissions, user permissions, company scope, customer scope,
and document sharing remain authoritative.

| Domain | Connected source | Exceptions included |
| --- | --- | --- |
| Sales | CRM Lead, CRM Deal, CRM Task, AI SDR Activity, Quotation | Qualified inbound replies, high-priority leads, calls/tasks due, stale or next-step-less deals, draft/expiring quotations |
| Clients | HD Ticket, Project, ToDo | All new/open tickets, with unassigned/SLA-failed tickets escalated; overdue projects; assigned client follow-ups |
| Finance | Sales Invoice | Overdue submitted receivables and draft invoices awaiting controlled review |
| Operations | Scheduled Job Log, Integration Request, Webhook Request Log, Error Log | Recent failures, grouped repeated errors, and Resend/Raven recovery signals without exposing payloads |
| Team | Task, ToDo | Pending-review or overdue high-priority tasks and founder assignments |

Each source document appears at most once. Multiple rules are combined into one
card. A single priority model routes each card to exactly one surface:
`Needs my decision`, `Today`, or `Watchlist`.

## Privacy and actions

Cards include only the source title/identifier, owner, scoped company/customer
label when present, generated reason, priority, due/age, and recommended next
action. The API never copies email bodies, ticket descriptions, request/response
payloads, stack traces, or credentials into the cockpit response.

The first release allows only:

- opening the permission-checked source record;
- temporarily acknowledging a stable exception condition; and
- creating or rescheduling a native ToDo for the signed-in user.

Invoice submission/sending, payments, client messages, retries, deployment
approvals, deletion, and other destructive or external actions remain in their
source workflows with their existing confirmations and permissions.

## Roles and settings

`System Manager` and `Founder Cockpit User` may open the page. The dedicated
role does not grant access to any source DocType; a user sees only records they
could already read. `Founder Cockpit State` rows are user-scoped. Only System
Managers may edit `Founder Cockpit Settings`.

Settings cover:

- priority bands and per-domain base scores;
- lead/deal/quotation age thresholds;
- operational lookback, repeated-error threshold, and ignored log methods;
- maximum records/cards and acknowledgement duration; and
- a default-off daily native ToDo digest.

External email, Raven, push, and chat notifications are intentionally not
available. When the native digest is explicitly enabled, the hourly scheduler
creates at most one count-only ToDo during the selected site-local hour.

## Unconnected sources

The page reports these gaps instead of silently treating them as healthy:

- n8n failures: no authenticated n8n-to-ERP failure feed is configured;
- deployment/release approvals: no native deployment DocType or webhook feed
  exists in the current Loopjet app;
- material subscription/payment-provider events: no provider event feed is
  currently stored in ERP.

Existing Resend inbound recovery is connected indirectly through native
Helpdesk tickets and restricted Error Logs. Existing LearnLayer Academy work is
connected through CRM Lead/Task and AI SDR Activity records already stored in
Loopjet CRM.

## Development verification

Run the fast suite before framework testing:

```bash
ruff check .
python3 -m compileall -q loopjet_frappe_custom
pytest -q
node --check loopjet_frappe_custom/loopjet_custom/page/founder_cockpit/founder_cockpit.js
```

For a Frappe development site, install or migrate the app, then run:

```bash
bench --site <development-site> migrate
bench --site <development-site> execute loopjet_frappe_custom.founder_cockpit.install.install_founder_cockpit
```

Verify the page at `/app/founder-cockpit` as a System Manager and as a user with
only `Founder Cockpit User` plus deliberately narrow source permissions. Keep
the digest disabled and use non-production fixtures for action tests.

Production requires a separately approved immutable app tag, deployment image,
database backup, migration, health checks, and authenticated UI acceptance.
