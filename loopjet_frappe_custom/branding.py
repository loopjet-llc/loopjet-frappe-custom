from __future__ import annotations

import frappe

PRINT_FORMAT_NAME_BY_DOCTYPE = {
	"Sales Invoice": "Loopjet Invoice",
	"Quotation": "Loopjet Offer",
}

LETTER_HEAD_NAME = "Loopjet Letterhead"
LEGACY_PRINT_FORMATS_TO_DISABLE = (
	"Sales Invoice Standard",
	"Sales Invoice with Item Image",
	"Quotation Standard",
	"Quotation with Item Image",
)


LOOPJET_MARK = """
<svg class="lj-logo-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 24" aria-label="Loopjet">
  <circle cx="14" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="3"></circle>
  <circle cx="26" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="3"></circle>
</svg>
"""


PRINT_CSS = """
:root {
	--lj-cyan: #22d3ee;
	--lj-blue: #38bdf8;
	--lj-violet: #8b5cf6;
	--lj-ink: #0a0c12;
	--lj-text: #14161c;
	--lj-muted: #5d6470;
	--lj-faint: #8b94a6;
	--lj-border: rgba(20, 22, 28, 0.10);
	--lj-border-strong: rgba(20, 22, 28, 0.16);
	--lj-surface: #ffffff;
	--lj-page: #f3f4f7;
	--lj-soft: #f6f7fa;
	--lj-wash: #ecf6fb;
	--lj-grad: linear-gradient(110deg, #22d3ee 0%, #38bdf8 38%, #8b5cf6 100%);
}

@page {
	size: A4;
	margin: 12mm;
}

.print-format {
	background: var(--lj-page) !important;
	padding: 0 !important;
}

.print-format * {
	box-sizing: border-box;
}

.lj-doc {
	color: var(--lj-text);
	font-family: Inter, "Helvetica Neue", Arial, sans-serif;
	font-size: 12.5px;
	line-height: 1.5;
	background: #ffffff;
	padding: 0;
	min-height: 270mm;
}

.lj-sheet {
	background: #ffffff;
	border: 1px solid rgba(20, 22, 28, 0.09);
	border-radius: 18px;
	box-shadow: none;
	overflow: hidden;
}

.lj-hero {
	position: relative;
	background-color: #ffffff;
	color: var(--lj-text);
	padding: 24px 28px 20px;
}

.lj-hero::after {
	content: "";
	position: absolute;
	left: 0;
	right: 0;
	bottom: 0;
	height: 4px;
	background: var(--lj-grad);
}

.lj-topline {
	display: table;
	width: 100%;
}

.lj-brand,
.lj-doc-title {
	display: table-cell;
	vertical-align: top;
}

.lj-doc-title {
	text-align: right;
}

.lj-brand-lockup {
	display: inline-table;
	color: var(--lj-text);
}

.lj-logo-mark {
	width: 40px;
	height: 24px;
	margin-right: 10px;
	vertical-align: middle;
}

.lj-wordmark {
	display: inline-block;
	font-family: "Space Grotesk", Inter, "Helvetica Neue", Arial, sans-serif;
	font-size: 24px;
	font-weight: 700;
	letter-spacing: -0.04em;
	vertical-align: middle;
}

.lj-company-sub {
	margin-top: 6px;
	max-width: 320px;
	color: var(--lj-muted);
	font-size: 12px;
}

.lj-eyebrow {
	display: inline-block;
	padding: 5px 9px;
	border-radius: 999px;
	background: rgba(34, 211, 238, 0.12);
	border: 1px solid rgba(34, 211, 238, 0.26);
	color: #0e7490;
	font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
	font-size: 9px;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
}

.lj-number {
	margin: 8px 0 0;
	color: var(--lj-text);
	font-family: "Space Grotesk", Inter, "Helvetica Neue", Arial, sans-serif;
	font-size: 24px;
	font-weight: 700;
	letter-spacing: -0.04em;
}

.lj-status {
	display: inline-block;
	margin-top: 10px;
	padding: 5px 10px;
	border-radius: 999px;
	background: rgba(34, 211, 238, 0.12);
	color: #0e7490;
	border: 1px solid rgba(34, 211, 238, 0.24);
	font-size: 11px;
	font-weight: 700;
}

.lj-content {
	padding: 22px 28px 24px;
}

.lj-grid {
	display: table;
	width: 100%;
	margin-bottom: 22px;
	table-layout: fixed;
}

.lj-card {
	display: table-cell;
	width: 50%;
	padding: 18px;
	background: #ffffff;
	border: 1px solid var(--lj-border);
	border-radius: 18px;
	vertical-align: top;
}

.lj-card + .lj-card {
	border-left: 12px solid transparent;
	background-clip: padding-box;
}

.lj-label {
	margin-bottom: 8px;
	color: var(--lj-faint);
	font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
	font-size: 9px;
	font-weight: 700;
	letter-spacing: 0.15em;
	text-transform: uppercase;
}

.lj-name {
	margin-bottom: 6px;
	font-family: "Space Grotesk", Inter, "Helvetica Neue", Arial, sans-serif;
	font-size: 16px;
	font-weight: 700;
	letter-spacing: -0.02em;
}

.lj-muted {
	color: var(--lj-muted);
}

.lj-meta-row {
	display: table;
	width: 100%;
	padding: 6px 0;
	border-bottom: 1px solid rgba(20, 22, 28, 0.06);
}

.lj-meta-row:last-child {
	border-bottom: 0;
}

.lj-meta-key,
.lj-meta-value {
	display: table-cell;
}

.lj-meta-key {
	width: 45%;
	color: var(--lj-muted);
}

.lj-meta-value {
	text-align: right;
	font-weight: 700;
}

.lj-items {
	width: 100%;
	border-collapse: separate;
	border-spacing: 0;
	overflow: hidden;
	border: 1px solid var(--lj-border);
	border-radius: 18px;
	background: #ffffff;
}

.lj-items thead th {
	padding: 12px 14px;
	background: #f6f7fa;
	color: var(--lj-faint);
	font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
	font-size: 9px;
	font-weight: 800;
	letter-spacing: 0.14em;
	text-transform: uppercase;
	border-bottom: 1px solid var(--lj-border);
}

.lj-items td {
	padding: 14px;
	border-bottom: 1px solid rgba(20, 22, 28, 0.07);
	vertical-align: top;
}

.lj-items tbody tr:last-child td {
	border-bottom: 0;
}

.lj-num {
	width: 36px;
	color: var(--lj-faint);
}

.lj-right {
	text-align: right;
	white-space: nowrap;
}

.lj-item-title {
	font-weight: 800;
}

.lj-item-description {
	margin-top: 4px;
	color: var(--lj-muted);
	font-size: 11.5px;
}

.lj-totals-wrap {
	display: table;
	width: 100%;
	margin-top: 22px;
}

.lj-words,
.lj-totals {
	display: table-cell;
	vertical-align: bottom;
}

.lj-words {
	width: 55%;
	padding-right: 22px;
}

.lj-words-box,
.lj-notes {
	padding: 16px;
	border: 1px solid var(--lj-border);
	border-radius: 18px;
	background: rgba(236, 246, 251, 0.68);
}

.lj-totals {
	width: 45%;
}

.lj-total-panel {
	overflow: hidden;
	border: 1px solid var(--lj-border);
	border-radius: 18px;
	background: #ffffff;
}

.lj-total-row {
	display: table;
	width: 100%;
	padding: 10px 14px;
	border-bottom: 1px solid rgba(20, 22, 28, 0.07);
}

.lj-total-row:last-child {
	border-bottom: 0;
}

.lj-total-key,
.lj-total-value {
	display: table-cell;
}

.lj-total-key {
	color: var(--lj-muted);
}

.lj-total-value {
	text-align: right;
	font-weight: 800;
}

.lj-grand {
	background: linear-gradient(110deg, rgba(34, 211, 238, 0.14), rgba(139, 92, 246, 0.14));
}

.lj-grand .lj-total-key,
.lj-grand .lj-total-value {
	color: var(--lj-text);
	font-family: "Space Grotesk", Inter, "Helvetica Neue", Arial, sans-serif;
	font-size: 17px;
	font-weight: 800;
	letter-spacing: -0.02em;
}

.lj-notes {
	margin-top: 18px;
	background: #ffffff;
}

.lj-footer {
	display: table;
	width: 100%;
	margin-top: 24px;
	padding-top: 16px;
	border-top: 1px solid var(--lj-border);
	color: var(--lj-muted);
	font-size: 11px;
}

.lj-footer-left,
.lj-footer-right {
	display: table-cell;
}

.lj-footer-right {
	text-align: right;
}

@media print {
	.print-format {
		background: #ffffff !important;
	}

	.lj-doc {
		border-radius: 0;
		padding: 0;
		background: #ffffff;
	}

	.lj-sheet {
		box-shadow: none;
	}
}
"""


PRINT_HTML = (
	"""
{% set is_offer = doc.doctype == "Quotation" %}
{% set document_label = "Offer" if is_offer else "Invoice" %}
{% set document_number = doc.open_business_document_number or doc.name %}
{% set customer_label = doc.customer_name or doc.customer or doc.party_name or doc.name %}
{% set company_email = frappe.db.get_value("Company", doc.company, "email") or "info@loopjet.io" %}
{% set company_website = frappe.db.get_value("Company", doc.company, "website") or "https://loopjet.io" %}
{% set company_name = doc.company or "Loopjet LLC" %}
{% set issue_date = doc.get_formatted("transaction_date") if is_offer else doc.get_formatted("posting_date") %}
{% set due_label = "Valid until" if is_offer else "Due date" %}
{% set due_date = doc.get_formatted("valid_till") if is_offer else doc.get_formatted("due_date") %}
{% set status = doc.status or ("Draft" if doc.docstatus == 0 else "Submitted") %}
<div class="lj-doc">
	<div class="lj-sheet">
		<div class="lj-hero">
			<div class="lj-topline">
				<div class="lj-brand">
					<div class="lj-brand-lockup">
						"""
	+ LOOPJET_MARK
	+ """
						<span class="lj-wordmark">Loopjet</span>
					</div>
					<div class="lj-company-sub">We build software millions depend on.</div>
				</div>
				<div class="lj-doc-title">
					<span class="lj-eyebrow">{{ document_label }}</span>
					<div class="lj-number">{{ document_number }}</div>
					<span class="lj-status">{{ status }}</span>
				</div>
			</div>
		</div>

		<div class="lj-content">
			<div class="lj-grid">
				<div class="lj-card">
					<div class="lj-label">{{ "Offer for" if is_offer else "Bill to" }}</div>
					<div class="lj-name">{{ customer_label }}</div>
					<div class="lj-muted">
						{% if doc.address_display %}
							{{ doc.address_display }}
						{% elif doc.customer_address %}
							{{ doc.customer_address }}
						{% elif doc.party_name %}
							{{ doc.party_name }}
						{% endif %}
					</div>
				</div>
				<div class="lj-card">
					<div class="lj-label">Document details</div>
					<div class="lj-meta-row">
						<div class="lj-meta-key">{{ document_label }} no.</div>
						<div class="lj-meta-value">{{ document_number }}</div>
					</div>
					<div class="lj-meta-row">
						<div class="lj-meta-key">Date</div>
						<div class="lj-meta-value">{{ issue_date }}</div>
					</div>
					{% if due_date %}
						<div class="lj-meta-row">
							<div class="lj-meta-key">{{ due_label }}</div>
							<div class="lj-meta-value">{{ due_date }}</div>
						</div>
					{% endif %}
					<div class="lj-meta-row">
						<div class="lj-meta-key">Currency</div>
						<div class="lj-meta-value">{{ doc.currency }}</div>
					</div>
					{% if doc.po_no %}
						<div class="lj-meta-row">
							<div class="lj-meta-key">PO no.</div>
							<div class="lj-meta-value">{{ doc.po_no }}</div>
						</div>
					{% endif %}
				</div>
			</div>

			<table class="lj-items">
				<thead>
					<tr>
						<th class="lj-num">#</th>
						<th>Item</th>
						<th class="lj-right">Qty</th>
						<th class="lj-right">Rate</th>
						<th class="lj-right">Amount</th>
					</tr>
				</thead>
				<tbody>
					{% for row in doc.items %}
						<tr>
							<td class="lj-num">{{ row.idx }}</td>
							<td>
								<div class="lj-item-title">{{ row.item_name or row.item_code }}</div>
								{% if row.description and row.description|striptags != row.item_name %}
									<div class="lj-item-description">{{ row.description }}</div>
								{% endif %}
							</td>
							<td class="lj-right">{{ row.get_formatted("qty", doc) }} {{ row.uom or row.stock_uom }}</td>
							<td class="lj-right">{{ row.get_formatted("rate", doc) }}</td>
							<td class="lj-right">{{ row.get_formatted("amount", doc) }}</td>
						</tr>
					{% endfor %}
				</tbody>
			</table>

			<div class="lj-totals-wrap">
				<div class="lj-words">
					{% if doc.in_words %}
						<div class="lj-words-box">
							<div class="lj-label">In words</div>
							{{ doc.in_words }}
						</div>
					{% endif %}
				</div>
				<div class="lj-totals">
					<div class="lj-total-panel">
						<div class="lj-total-row">
							<div class="lj-total-key">Subtotal</div>
							<div class="lj-total-value">{{ doc.get_formatted("net_total") or doc.get_formatted("total") }}</div>
						</div>
						{% if doc.discount_amount %}
							<div class="lj-total-row">
								<div class="lj-total-key">Discount</div>
								<div class="lj-total-value">- {{ doc.get_formatted("discount_amount") }}</div>
							</div>
						{% endif %}
						{% if doc.total_taxes_and_charges %}
							<div class="lj-total-row">
								<div class="lj-total-key">Taxes</div>
								<div class="lj-total-value">{{ doc.get_formatted("total_taxes_and_charges") }}</div>
							</div>
						{% endif %}
						<div class="lj-total-row lj-grand">
							<div class="lj-total-key">Total</div>
							<div class="lj-total-value">{{ doc.get_formatted("grand_total") }}</div>
						</div>
						{% if not is_offer and doc.outstanding_amount %}
							<div class="lj-total-row">
								<div class="lj-total-key">Outstanding</div>
								<div class="lj-total-value">{{ doc.get_formatted("outstanding_amount") }}</div>
							</div>
						{% endif %}
					</div>
				</div>
			</div>

			{% if doc.terms or doc.remarks %}
				<div class="lj-notes">
					<div class="lj-label">{{ "Terms" if doc.terms else "Notes" }}</div>
					{{ doc.terms or doc.remarks }}
				</div>
			{% endif %}

			<div class="lj-footer">
				<div class="lj-footer-left">
					<strong>{{ company_name }}</strong><br>
					{{ company_website }}
				</div>
				<div class="lj-footer-right">
					{{ company_email }}<br>
					Generated by Loopjet ERP
				</div>
			</div>
		</div>
	</div>
</div>
"""
)


LETTER_HEAD_CONTENT = (
	"""
<div style="font-family: Inter, 'Helvetica Neue', Arial, sans-serif; color:#14161c; padding: 8px 0 12px;">
	<div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(20,22,28,.10); padding-bottom:12px;">
		<div style="display:flex; align-items:center; gap:10px;">
			"""
	+ LOOPJET_MARK.replace('class="lj-logo-mark"', 'style="width:40px;height:24px;color:#14161c;"')
	+ """
			<span style="font-size:22px; font-weight:700; letter-spacing:-.04em;">Loopjet</span>
		</div>
		<div style="font-size:11px; color:#5d6470; text-align:right;">https://loopjet.io<br>info@loopjet.io</div>
	</div>
</div>
"""
)


LETTER_HEAD_FOOTER = """
<div style="font-family: Inter, 'Helvetica Neue', Arial, sans-serif; color:#5d6470; font-size:10px; border-top:1px solid rgba(20,22,28,.10); padding-top:10px;">
	Loopjet LLC · https://loopjet.io · info@loopjet.io
</div>
"""


INVOICE_EMAIL_HTML = """
<div style="font-family:Inter,Arial,sans-serif;color:#14161c;line-height:1.55">
	<p>Hi {{ customer_name or customer }},</p>
	<p>Please find attached invoice <strong>{{ open_business_document_number or name }}</strong>.</p>
	<p>The total is <strong>{{ currency }} {{ grand_total }}</strong>{% if due_date %}, due on <strong>{{ due_date }}</strong>{% endif %}.</p>
	<p>If anything looks off, just reply to this email and we will help right away.</p>
	<p style="margin-top:24px;color:#5d6470">Best,<br>Loopjet</p>
</div>
"""


OFFER_EMAIL_HTML = """
<div style="font-family:Inter,Arial,sans-serif;color:#14161c;line-height:1.55">
	<p>Hi {{ customer_name or party_name }},</p>
	<p>Here is our offer <strong>{{ name }}</strong> for your review.</p>
	<p>The proposed total is <strong>{{ currency }} {{ grand_total }}</strong>{% if valid_till %}, valid until <strong>{{ valid_till }}</strong>{% endif %}.</p>
	<p>Reply with any questions or changes — happy to refine it with you.</p>
	<p style="margin-top:24px;color:#5d6470">Best,<br>Loopjet</p>
</div>
"""


HELPDESK_EMAIL_HTML = """
<div style="font-family:Inter,Arial,sans-serif;color:#14161c;line-height:1.55">
	<p>Hi {{ raised_by or customer or "there" }},</p>
	<p>Thanks for reaching out to Loopjet Support. We have received your request{% if name %} <strong>{{ name }}</strong>{% endif %} and will keep you updated here.</p>
	<p style="margin-top:24px;color:#5d6470">Best,<br>Loopjet Support</p>
</div>
"""


def install_branding() -> None:
	"""Install/update Loopjet branded print and email templates."""
	install_letter_head()
	install_print_formats()
	install_email_templates()
	_set_print_settings()
	frappe.clear_cache()


def install_letter_head() -> None:
	doc = _get_or_new("Letter Head", LETTER_HEAD_NAME)
	doc.letter_head_name = LETTER_HEAD_NAME
	doc.source = "HTML"
	doc.footer_source = "HTML"
	doc.content = LETTER_HEAD_CONTENT
	doc.footer = LETTER_HEAD_FOOTER
	doc.disabled = 0
	doc.is_default = 1
	_save(doc)

	for other in frappe.get_all("Letter Head", filters={"name": ["!=", LETTER_HEAD_NAME], "is_default": 1}, pluck="name"):
		frappe.db.set_value("Letter Head", other, "is_default", 0, update_modified=False)


def install_print_formats() -> None:
	for doctype, name in PRINT_FORMAT_NAME_BY_DOCTYPE.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		doc = _get_or_new("Print Format", name)
		doc.print_format_for = "DocType"
		doc.doc_type = doctype
		doc.module = "Loopjet Custom"
		doc.standard = "No"
		doc.custom_format = 1
		doc.disabled = 0
		doc.pdf_generator = "chrome"
		doc.print_format_type = "Jinja"
		doc.html = PRINT_HTML
		doc.css = PRINT_CSS
		doc.margin_top = 0
		doc.margin_bottom = 0
		doc.margin_left = 0
		doc.margin_right = 0
		doc.font = "Inter"
		doc.font_size = 12
		_save(doc)
		_set_default_print_format(doctype, name)
	_disable_legacy_print_formats()


def install_email_templates() -> None:
	_templates = [
		{
			"name": "Loopjet Invoice Email",
			"reference_doctype": "Sales Invoice",
			"subject": "Invoice {{ open_business_document_number or name }} from Loopjet",
			"response_html": INVOICE_EMAIL_HTML,
		},
		{
			"name": "Loopjet Offer Email",
			"reference_doctype": "Quotation",
			"subject": "Offer {{ name }} from Loopjet",
			"response_html": OFFER_EMAIL_HTML,
		},
	]
	if frappe.db.exists("DocType", "HD Ticket"):
		_templates.append(
			{
				"name": "Loopjet Helpdesk Reply",
				"reference_doctype": "HD Ticket",
				"subject": "We received your request{% if name %}: {{ name }}{% endif %}",
				"response_html": HELPDESK_EMAIL_HTML,
			}
		)

	for template in _templates:
		if not frappe.db.exists("DocType", template["reference_doctype"]):
			continue
		doc = _get_or_new("Email Template", template["name"])
		doc.enabled = 1
		doc.reference_doctype = template["reference_doctype"]
		doc.subject = template["subject"]
		doc.use_html = 1
		doc.response_html = template["response_html"]
		doc.response = ""
		_save(doc)


def _disable_legacy_print_formats() -> None:
	for print_format in LEGACY_PRINT_FORMATS_TO_DISABLE:
		if frappe.db.exists("Print Format", print_format):
			frappe.db.set_value("Print Format", print_format, "disabled", 1, update_modified=False)


def _set_print_settings() -> None:
	if not frappe.db.exists("DocType", "Print Settings"):
		return
	settings = frappe.get_single("Print Settings")
	settings.pdf_page_size = "A4"
	settings.font = "Inter"
	settings.font_size = 12
	settings.with_letterhead = 0
	settings.send_print_as_pdf = 1
	settings.save(ignore_permissions=True)


def _set_default_print_format(doctype: str, print_format: str) -> None:
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		doctype,
		None,
		"default_print_format",
		print_format,
		"Data",
		validate_fields_for_doctype=False,
	)


def _get_or_new(doctype: str, name: str) -> frappe.model.document.Document:
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.new_doc(doctype)
	doc.name = name
	return doc


def _save(doc: frappe.model.document.Document) -> None:
	if doc.get("__islocal"):
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
