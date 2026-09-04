"""Light-mode website CI for the Sales Invoice print format only."""

INVOICE_HTML = """
{% set is_offer = doc.doctype == "Quotation" %}
{% set selected_language = doc.get("loopjet_document_language") or doc.get("language") or "English" %}
{% set is_german = selected_language in ["Deutsch", "German", "de", "de-DE"] %}
{% set document_label = ("Angebot" if is_offer else "Rechnung") if is_german else ("Offer" if is_offer else "Invoice") %}
{% set document_number = doc.open_business_document_number or doc.name %}
{% set customer_label = doc.customer_name or doc.customer or doc.party_name or doc.name %}
{% set company_email = frappe.db.get_value("Company", doc.company, "email") or "info@loopjet.io" %}
{% set company_website = frappe.db.get_value("Company", doc.company, "website") or "https://loopjet.io" %}
{% set company_name = doc.company or "Loopjet LLC" %}
{% set issue_date = doc.get_formatted("transaction_date") if is_offer else doc.get_formatted("posting_date") %}
{% set due_label = ("Gültig bis" if is_offer else "Fällig am") if is_german else ("Valid until" if is_offer else "Due date") %}
{% set due_date = doc.get_formatted("valid_till") if is_offer else doc.get_formatted("due_date") %}
{% set service_period_start = doc.get_formatted("service_period_start") if doc.service_period_start else "" %}
{% set service_period_end = doc.get_formatted("service_period_end") if doc.service_period_end else "" %}
{% set service_period_value = service_period_start ~ " - " ~ service_period_end if service_period_start and service_period_end else "" %}
{% set tax_note = "Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge). Die Umsatzsteuer wird vom Leistungsempfänger geschuldet." if is_german else "Reverse charge applies. VAT is to be accounted for by the recipient." %}
<div class="lj-doc">
	<div class="lj-sheet">
		<div class="lj-hero">
			<div class="lj-topline">
				<div class="lj-brand">
					<div class="lj-brand-lockup">

<svg class="lj-brand-logo" viewBox="0 0 90 23" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="loopjet">
<circle cx="8.5" cy="11.5" r="6" stroke="#00009D" stroke-width="2.6"/>
<circle cx="17.5" cy="11.5" r="6" stroke="#00009D" stroke-width="2.6"/>
<text x="30" y="17.2" font-family="system-ui, -apple-system, 'Segoe UI', Arial, sans-serif" font-size="16.5" font-weight="650" letter-spacing="-0.4" fill="#00009D">loopjet</text>
</svg>
					</div>
					<div class="lj-company-sub">{{ "SOFTWARE. KI. CLOUD. PRODUKTE." if is_german else "SOFTWARE. AI. CLOUD. PRODUCTS." }}</div>
				</div>
				<div class="lj-doc-title">
					<div class="lj-heading">{{ document_label }}</div>
<div class="lj-number">{{ document_number }}</div>
				</div>
			</div>
		</div>

		<div class="lj-content">
			<div class="lj-grid">
				<div class="lj-card">
					<div class="lj-label">{{ ("Angebot für" if is_offer else "Rechnung an") if is_german else ("Offer for" if is_offer else "Bill to") }}</div>
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
					<div class="lj-label">{{ "Dokumentdetails" if is_german else "Document details" }}</div>
					<div class="lj-meta-row">
						<div class="lj-meta-key">{{ ("Angebotsnr." if is_offer else "Rechnungsnr.") if is_german else document_label ~ " no." }}</div>
						<div class="lj-meta-value">{{ document_number }}</div>
					</div>
					<div class="lj-meta-row">
						<div class="lj-meta-key">{{ "Datum" if is_german else "Date" }}</div>
						<div class="lj-meta-value">{{ issue_date }}</div>
					</div>
					{% if service_period_value %}
						<div class="lj-meta-row lj-period-row">
							<div class="lj-meta-key">{{ "Leistungszeitraum" if is_german else "Service period" }}</div>
							<div class="lj-meta-value">
								{{ service_period_value }}
							</div>
						</div>
					{% endif %}
					{% if due_date %}
						<div class="lj-meta-row">
							<div class="lj-meta-key">{{ due_label }}</div>
							<div class="lj-meta-value">{{ due_date }}</div>
						</div>
					{% endif %}
					<div class="lj-meta-row">
						<div class="lj-meta-key">{{ "Währung" if is_german else "Currency" }}</div>
						<div class="lj-meta-value">{{ doc.currency }}</div>
					</div>
					{% if doc.po_no %}
						<div class="lj-meta-row">
							<div class="lj-meta-key">{{ "Bestellnr." if is_german else "PO no." }}</div>
							<div class="lj-meta-value">{{ doc.po_no }}</div>
						</div>
					{% endif %}
				</div>
			</div>

			<table class="lj-items">
				<thead>
					<tr>
						<th class="lj-num">#</th>
						<th>{{ "Position" if is_german else "Item" }}</th>
						<th class="lj-right">{{ "Menge" if is_german else "Qty" }}</th>
						<th class="lj-right">{{ "Preis" if is_german else "Rate" }}</th>
						<th class="lj-right">{{ "Betrag" if is_german else "Amount" }}</th>
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
				<div class="lj-totals">
					<div class="lj-total-panel">
						<div class="lj-total-row">
							<div class="lj-total-key">{{ "Zwischensumme" if is_german else "Subtotal" }}</div>
							<div class="lj-total-value">{{ doc.get_formatted("net_total") or doc.get_formatted("total") }}</div>
						</div>
						{% if doc.discount_amount %}
							<div class="lj-total-row">
								<div class="lj-total-key">{{ "Rabatt" if is_german else "Discount" }}</div>
								<div class="lj-total-value">- {{ doc.get_formatted("discount_amount") }}</div>
							</div>
						{% endif %}
						{% if doc.total_taxes_and_charges %}
							<div class="lj-total-row">
								<div class="lj-total-key">{{ "Steuern" if is_german else "Taxes" }}</div>
								<div class="lj-total-value">{{ doc.get_formatted("total_taxes_and_charges") }}</div>
							</div>
						{% endif %}
						<div class="lj-total-row lj-grand">
							<div class="lj-total-key">{{ "Gesamtbetrag" if is_german else "Total" }}</div>
							<div class="lj-total-value">{{ doc.get_formatted("grand_total") }}</div>
						</div>
						{% if not is_offer and doc.outstanding_amount %}
							<div class="lj-total-row">
								<div class="lj-total-key">{{ "Offen" if is_german else "Outstanding" }}</div>
								<div class="lj-total-value">{{ doc.get_formatted("outstanding_amount") }}</div>
							</div>
						{% endif %}
					</div>
				</div>
			</div>

			{% if doc.get("reverse_charge_applies") %}
				<div class="lj-tax-note">
					<div class="lj-label">{{ "Steuerhinweis" if is_german else "Tax note" }}</div>
					{{ tax_note }}
				</div>
			{% endif %}

			{% if doc.terms or doc.remarks %}
				<div class="lj-notes">
					<div class="lj-label">{{ ("Bedingungen" if doc.terms else "Hinweise") if is_german else ("Terms" if doc.terms else "Notes") }}</div>
					{{ doc.terms or doc.remarks }}
				</div>
			{% endif %}

			<div class="lj-footer">
				<div class="lj-footer-left">
					<strong>{{ company_name }}</strong><br>
					{% if doc.company_address_display %}{{ doc.company_address_display }}{% endif %}
				</div>
				<div class="lj-footer-right">
					{{ company_email }}<br>
					{{ company_website }}
				</div>
			</div>
		</div>
	</div>
</div>

"""

INVOICE_CSS = """
@page { size: A4; margin: 14mm; }
.print-format {
  padding: 0 !important; background: #ffffff !important;
  color: #09090b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.print-format * { box-sizing: border-box; }
.lj-doc { color: #09090b; background: #fff; font-size: 12px; line-height: 1.55; }
.lj-sheet { background: #fff; overflow: visible; }
.lj-hero { padding: 0 0 27px; border-bottom: 1px solid #dedee3; }
.lj-topline, .lj-grid, .lj-meta-row, .lj-total-row, .lj-footer { display: table; width: 100%; table-layout: fixed; }
.lj-brand, .lj-doc-title, .lj-card, .lj-meta-key, .lj-meta-value, .lj-total-key, .lj-total-value, .lj-footer-left, .lj-footer-right { display: table-cell; vertical-align: top; }
.lj-brand { width: 44%; }
.lj-brand-logo { width: 148px; height: 38px; display: block; }
.lj-company-sub { color: #626268; font-size: 9px; letter-spacing: 1.25px; margin-top: 12px; }
.lj-doc-title { text-align: right; }
.lj-heading { color: #0f0f71; font-size: 34px; line-height: 1.1; font-weight: 600; letter-spacing: -1.1px; }
.lj-number { color: #626268; font-size: 12px; margin-top: 10px; overflow-wrap: anywhere; }
.lj-content { padding: 0; }
.lj-grid { margin: 28px 0 30px; }
.lj-card:first-child { width: 49%; padding-right: 30px; }
.lj-card:last-child { width: 51%; padding-left: 12px; }
.lj-label { color: #66666e; font-size: 9px; font-weight: 600; letter-spacing: 1.25px; text-transform: uppercase; margin-bottom: 10px; }
.lj-name { font-weight: 600; font-size: 15px; margin-bottom: 5px; }
.lj-muted { color: #52525b; }
.lj-meta-row { margin: 0 0 6px; font-size: 11px; }
.lj-meta-key { width: 42%; color: #66666e; padding-right: 8px; }
.lj-meta-value { text-align: right; font-weight: 500; overflow-wrap: anywhere; }
.lj-period-row .lj-meta-key, .lj-period-row .lj-meta-value { display: block; width: 100%; text-align: left; }
.lj-period-row .lj-meta-value { margin-top: 2px; }
.lj-period-row { padding: 3px 0; }
.print-format .lj-items { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0; font-size: 11px; }
.print-format .lj-items thead { display: table-header-group; }
.print-format .lj-items th { background: #fafafa !important; color: #66666e; font-size: 9px; font-weight: 600; letter-spacing: .8px; text-transform: uppercase; padding: 10px 8px !important; border-top: 1px solid #dedee3 !important; border-bottom: 1px solid #dedee3 !important; }
.print-format .lj-items td { padding: 15px 8px !important; border-bottom: 1px solid #e8e8ed !important; vertical-align: top; }
.print-format .lj-items th:first-child, .print-format .lj-items td:first-child { padding-left: 0 !important; width: 5%; }
.print-format .lj-items th:nth-child(2) { width: 45%; text-align: left; }
.print-format .lj-items th:nth-child(3) { width: 14%; }
.print-format .lj-items th:nth-child(4), .print-format .lj-items th:nth-child(5) { width: 18%; }
.print-format .lj-items th:last-child, .print-format .lj-items td:last-child { padding-right: 0 !important; }
.lj-right { text-align: right; font-variant-numeric: tabular-nums; }
.lj-num { color: #71717a; text-align: left; }
.lj-item-title { font-weight: 600; overflow-wrap: anywhere; }
.lj-item-description { margin-top: 5px; color: #626268; font-size: 10px; line-height: 1.55; overflow-wrap: anywhere; }
.lj-item-description p { margin: 0 0 5px; }
.lj-totals-wrap { margin: 19px 0 25px; }
.lj-totals { width: 53%; margin-left: auto; }
.lj-total-row { font-size: 11px; }
.lj-total-key, .lj-total-value { padding: 7px 0; }
.lj-total-key { width: 51%; color: #626268; }
.lj-total-value { text-align: right; font-variant-numeric: tabular-nums; }
.lj-grand { border-top: 1px solid #0f0f71; border-bottom: 1px solid #dedee3; }
.lj-grand .lj-total-key, .lj-grand .lj-total-value { padding: 12px 0; color: #0f0f71; font-weight: 650; font-size: 17px; }
.lj-grand .lj-total-key { font-size: 12px; vertical-align: middle; }
.lj-tax-note, .lj-notes { color: #52525b; font-size: 10px; line-height: 1.6; margin-top: 22px; }
.lj-tax-note .lj-label, .lj-notes .lj-label { margin-bottom: 6px; }
.lj-notes p { margin: 0 0 6px; }
.lj-footer { margin-top: 35px; padding-top: 16px; border-top: 1px solid #dedee3; font-size: 9px; line-height: 1.65; color: #71717a; }
.lj-footer strong { color: #09090b; font-weight: 600; }
.lj-footer-left { width: 55%; padding-right: 20px; }
.lj-footer-right { text-align: right; }
.lj-hero, .lj-grid, .lj-items tr, .lj-totals, .lj-tax-note, .lj-footer { break-inside: avoid; page-break-inside: avoid; }
.lj-notes h1, .lj-notes h2, .lj-notes h3, .lj-label { break-after: avoid; page-break-after: avoid; }

"""
