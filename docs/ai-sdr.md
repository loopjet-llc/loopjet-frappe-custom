# Loopjet AI SDR

The AI SDR runs inside the existing Frappe CRM site and uses the CRM records as
its source of truth:

- `CRM Organization` for target accounts
- `CRM Lead` for prospects
- `CRM Deal` for qualified opportunities
- `CRM Task` for human reply follow-up
- `Communication` for email replies

It does not create a second lead database or edit upstream Frappe CRM code.

## What the team gets

The `/app/ai-sdr` workspace shows research-ready accounts, active sequences,
drafts waiting for approval, approved messages, due follow-ups, and recent
replies. CRM Lead forms include actions to prepare an individual draft, open the
workspace, and—for managers—enroll the lead in an enabled sequence.

The workflow is:

1. A user records reviewed account evidence and source URLs in `AI SDR Research`.
2. The system computes a deterministic ICP score and tier from the reviewed
   fit, trigger, persona, and data-quality scores.
3. A manager enrolls a CRM Lead in an enabled `AI SDR Sequence`, or a user
   prepares a one-off Email, LinkedIn, or Call activity.
4. A connected AI model produces a draft from approved company context and
   reviewed evidence. If AI is not connected or is disabled, a safe fallback
   template or a manual draft is used and the workspace does not claim that AI
   is active.
5. A manager reviews and approves the exact recipient and content.
6. An approved email can be sent only when the delivery switch is enabled.
   Approved LinkedIn and call steps are completed manually.
7. Inbound email replies are classified, the sequence stops or pauses, and
   important replies create a CRM Task for a person.
8. A CRM Deal stops any remaining active enrollment for that lead.

## Roles

- `AI SDR User`: manage assigned research, drafts, enrollments, and manual
  LinkedIn/call completion.
- `AI SDR Manager`: manage all AI SDR records, enroll leads, approve or reject
  outreach, and send approved email.
- `AI SDR Agent`: API-only integration role for the bounded prospect research,
  contact, call-note, and call-list methods. It grants no Desk or generic CRM
  DocType access.
- `System Manager`: configure the provider, sender account, limits, and feature
  switches.

Assign the smallest role each person needs. Record-level query conditions keep
regular users limited to records they own or that are assigned to them.

For an external research agent, create a dedicated enabled Frappe user, assign
only `AI SDR Agent`, and generate that user's API key and secret. See
[AI SDR agent API](ai-sdr-agent-api.md) for the exact HTTP surface.

## Initial configuration

After installing the app or deploying an upgrade, run:

```bash
bench --site <crm-site> migrate
```

Then:

1. Assign `AI SDR User` and `AI SDR Manager` roles.
2. Review the disabled `Supervised B2B Outreach` starter sequence, add fallback
   templates if wanted, and enable it only when the steps are approved.
3. Open **AI SDR Settings**.
4. Enter reviewed facts in **Approved Company Context**.
5. Select **OpenRouter**, enter the exact OpenRouter model slug and API key, and
   keep the default base URL `https://openrouter.ai/api/v1`.
6. Click **Test OpenRouter Connection**. Loopjet records `Connected` only after
   it receives and validates a real model response.
7. Enable **AI Generation** only after the connection test and a draft-quality
   review.
8. Configure a dedicated Frappe `Email Account` that can send from the approved
   sales mailbox.
9. Keep **Approved Email Sending** disabled until sender identity, reply routing,
   daily limits, and unsubscribe behavior have been tested.

The provider endpoint is `<AI Base URL>/chat/completions`. The API key is stored
in a Frappe Password field. Changing the provider, base URL, model, or API key
invalidates the verified connection and requires another live test.

## How AI and lead sourcing are separated

The connected model is used for three bounded tasks: analyzing user-reviewed
account evidence, writing personalized outreach drafts, and classifying inbound
replies. The model is not treated as a lead database and does not invent contact
details.

Leads currently enter through existing `CRM Lead` records, manual creation, or
reviewed imports. Automated prospect discovery requires a separate lead-data or
enrichment provider with its own provenance, licensing, deduplication, and
verification rules. That provider is intentionally separate from OpenRouter:
OpenRouter supplies model inference, not verified prospect data.

## Reply handling

Frappe must create received email `Communication` records that reference the
related `CRM Lead` or `CRM Deal`. Explicit unsubscribe wording is handled first
by the local classifier even when no AI provider is configured. It immediately:

- creates or reactivates an email suppression record;
- stops the active sequence;
- marks the CRM Lead as replied; and
- prevents future enrollment or delivery to that address.

Interested, information-request, referral, and ambiguous replies stop the
sequence and create a CRM Task. Not-now and out-of-office replies pause it for a
bounded period.

## Safety boundaries

- AI generation defaults to off.
- AI is shown as active only after a successful live provider test.
- Email delivery defaults to off.
- Every outbound sequence step requires human approval.
- Approval is a protected server-side transition; editing the status field
  cannot bypass it.
- Approved recipient and content are immutable.
- Sending rechecks suppression and the daily email limit.
- Only known reviewed source URLs can be retained as model evidence.
- Fallback templates never execute Jinja or Python expressions.
- LinkedIn is not automated; the system prepares and records a manual action.
- Every activity records provider, model, prompt version, usage, approval,
  delivery, and reply information when applicable.

## Production rollout checklist

Before enabling delivery:

1. Restore a production backup into staging and run the migration twice.
2. Verify the AI SDR workspace, CRM Lead actions, roles, and record visibility.
3. Test one manual draft and one enabled sequence with an internal address.
4. Confirm approval, rejection, regeneration, and content immutability.
5. Confirm the sender mailbox and that replies reference the correct CRM record.
6. Send an unsubscribe test and verify both suppression and sequence stop.
7. Set a conservative daily limit and enable approved email delivery.
8. Monitor Frappe Error Logs, Email Queue, activity failures, and suppressions.
