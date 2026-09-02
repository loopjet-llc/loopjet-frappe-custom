# Loopjet AI SDR agent API

This is the narrow integration surface for reviewed prospect data. It writes to
Frappe CRM, not ERPNext's legacy `Lead` DocType:

- `CRM Organization` stores the target company and normalized domain.
- `CRM Lead` stores the current contact person. Until one is known, the API
  creates a clearly flagged company placeholder so the account can enter the
  call list without inventing a person.
- `AI SDR Research` stores reviewed evidence, sources, the sales reason, and ICP
  scoring provenance.
- `FCRM Note` stores call notes in the CRM timeline; a dated follow-up also
  creates a `CRM Task`.

## Authentication and permissions

Create a dedicated enabled Frappe user, assign only the `AI SDR Agent` role,
then generate an API key and API secret for that user. The role has no Desk or
generic CRM DocType permissions. It authorizes only the methods in this module.

Send the credentials as:

```http
Authorization: token API_KEY:API_SECRET
```

Do not use an Administrator credential. Store the secret in the agent's secret
store and rotate it if it is ever exposed.

## Methods

The shared path prefix is:

```text
/api/method/loopjet_frappe_custom.ai_sdr.agent_api.
```

| Method | HTTP | Purpose |
| --- | --- | --- |
| `search_lead` | `GET` | Find a company/contact by normalized domain, email, or exact company name |
| `create_lead` | `POST` | Deduplicate and create the organization, company/contact lead, and research record |
| `create_outbound_lead` | `POST` | Descriptive alias of `create_lead` |
| `update_lead` | `POST` | Update only approved research, contact, owner, and call scheduling fields |
| `add_contact_person` | `POST` | Replace a company placeholder or add another person under the organization |
| `add_call_note` | `POST` | Add a timeline note, update call state, and optionally create a follow-up task |
| `get_next_call_list` | `GET` | Return due, non-suppressed prospects ordered by next call time |
| `get_academy_outbound_context` | `GET` | Return one tagged Academy lead and its CRM comments for gate evaluation |
| `get_academy_outbound_limits` | `GET` | Return bounded organization-window and business-day Academy audit rows for rate-limit checks |
| `record_academy_outbound_event` | `POST` | Append a canonical Academy sender event and optionally apply bounded suppression |

Every write method rejects `GET`. The API never sends an email or LinkedIn
message. LinkedIn research and sending remain human-approved manual actions.

The Academy sender methods do not grant generic CRM permissions. They refuse
leads without the exact `Learnlayer Academy` tag, accept only canonical
`[Academy outbound |` events, and restrict suppression to provider stop events
or explicit complaints/opt-outs. The email provider call remains in the
LearnLayer-owned sender, not this CRM integration.

## Manual Academy email from a CRM Lead

The standard CRM Lead form script exposes **Send LearnLayer Academy Email** only
to managers and only on a lead with the exact `Learnlayer Academy` tag. The
dialog accepts a subject and plain-text body, then requires a second explicit
send confirmation. Frappe calls the protected LearnLayer Edge sender
server-to-server; the shared secret and Resend key never reach the browser.

This path is disabled by default. A System Manager must configure
`academy_outbound_url`, the Password field `academy_outbound_secret`, and then
enable `academy_manual_sending_enabled`. The URL validator requires HTTPS, a
Supabase host, and the exact `/functions/v1/academy-outbound-email` path.

Before the external request, Frappe persists an `AI SDR Activity` containing
the author, lead, recipient, subject, body, approval time, idempotency key, and
`academy-manual-v1` version. The sender independently re-reads the CRM gate and
suppression state and applies the same dedupe, organization-window, reservation,
and daily-limit controls as automation. Provider ID, outcome, acceptance time,
and errors are written back to the activity; signed webhook events continue to
update that same audit record. A transport failure is recorded as outcome
unknown and must not be worked around by creating a second message.

## Create a researched company

The proposal's 0-10 ICP scale and the workspace's 0-100 scale are both
accepted; `9` is stored as `90`.

```bash
curl -X POST \
  https://erp.loopjet.io/api/method/loopjet_frappe_custom.ai_sdr.agent_api.create_lead \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Muster Maschinenbau GmbH",
    "website": "https://www.muster.de/about",
    "phone": "+49 711 123456",
    "country": "Germany",
    "industry": "Manufacturing",
    "no_of_employees": "201-500",
    "linkedin_url": "https://www.linkedin.com/company/muster",
    "icp_score": 9,
    "research_notes": "Operates three production sites in Germany.",
    "sales_reason": "Strong Workforce ICP because qualification processes appear decentralized.",
    "source_urls": ["https://www.muster.de/about"]
  }'
```

The stored company website becomes `https://muster.de` and the duplicate key is
`muster.de`. A second create returns `created: false` with
`reason: duplicate_domain` instead of creating another record.

## Add the responsible person

Pass the placeholder lead returned by `create_lead`. If it is still flagged as
a company lead, this updates that record rather than creating a duplicate.

```bash
curl -X POST \
  https://erp.loopjet.io/api/method/loopjet_frappe_custom.ai_sdr.agent_api.add_contact_person \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "lead": "CRM-LEAD-2026-00001",
    "first_name": "Anna",
    "last_name": "Beispiel",
    "job_title": "Head of Learning and Development",
    "email": "anna.beispiel@muster.de",
    "linkedin_url": "https://www.linkedin.com/in/anna-beispiel"
  }'
```

To add another person under the same account, call the method again with
`organization` and omit `lead`.

## Record a call and schedule the follow-up

```bash
curl -X POST \
  https://erp.loopjet.io/api/method/loopjet_frappe_custom.ai_sdr.agent_api.add_call_note \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "lead": "CRM-LEAD-2026-00001",
    "outcome": "Receptionist",
    "note": "Asked for the person responsible for workforce qualification.",
    "next_call_at": "2026-08-11 10:00:00"
  }'
```

Supported normalized call states are `New`, `Researched`, `Receptionist`,
`Contact Identified`, `No Answer`, `Connected`, `Follow-up`, `Qualified`, and
`Rejected`.

## Fetch the next call list

```bash
curl \
  'https://erp.loopjet.io/api/method/loopjet_frappe_custom.ai_sdr.agent_api.get_next_call_list?limit=30' \
  -H "Authorization: token API_KEY:API_SECRET"
```

Leads marked do-not-contact, explicitly suppressed, qualified, or rejected are
excluded. `limit` is capped at 100, and `assigned_to` can restrict the list to a
specific lead owner.
