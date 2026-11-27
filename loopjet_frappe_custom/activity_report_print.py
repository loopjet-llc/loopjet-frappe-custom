"""Loopjet print format for a structured activity report."""

ACTIVITY_REPORT_HTML = """
{% set is_german = doc.report_language != "English" %}
{% set customer_name = frappe.db.get_value("Customer", doc.customer, "customer_name") or doc.customer %}
{% set company_email = frappe.db.get_value("Company", doc.company, "email") or "info@loopjet.io" %}
{% set company_website = frappe.db.get_value("Company", doc.company, "website") or "https://loopjet.io" %}
<div class="lj-activity-report">
  <div class="lj-report-hero">
    <div class="lj-report-brand">
      <svg class="lj-report-logo" viewBox="0 0 90 23" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="loopjet">
        <circle cx="8.5" cy="11.5" r="6" stroke="#00009D" stroke-width="2.6"/>
        <circle cx="17.5" cy="11.5" r="6" stroke="#00009D" stroke-width="2.6"/>
        <text x="30" y="17.2" font-family="system-ui, -apple-system, 'Segoe UI', Arial, sans-serif" font-size="16.5" font-weight="650" letter-spacing="-0.4" fill="#00009D">loopjet</text>
      </svg>
      <div class="lj-report-claim">{{ "SOFTWARE. KI. CLOUD. PRODUKTE." if is_german else "SOFTWARE. AI. CLOUD. PRODUCTS." }}</div>
    </div>
    <div class="lj-report-heading">
      <div class="lj-report-kicker">{{ "LEISTUNGSNACHWEIS" if is_german else "SERVICE RECORD" }}</div>
      <h1>{{ "Tätigkeitsbericht" if is_german else "Activity report" }}</h1>
      <div class="lj-report-number">{{ doc.name | e }}</div>
    </div>
  </div>

  {% if doc.docstatus == 0 %}<div class="lj-report-draft">{{ "ENTWURF" if is_german else "DRAFT" }}</div>{% endif %}

  <div class="lj-report-info">
    <div class="lj-report-card">
      <div class="lj-report-label">{{ "Bericht für" if is_german else "Report for" }}</div>
      <div class="lj-report-customer">{{ customer_name | e }}</div>
      {% if doc.customer_address %}<div class="lj-report-address">{{ doc.customer_address | e }}</div>{% endif %}
    </div>
    <div class="lj-report-card">
      <div class="lj-report-label">{{ "Berichtsdetails" if is_german else "Report details" }}</div>
      <div class="lj-report-meta"><span>{{ "Berichtsdatum" if is_german else "Report date" }}</span><strong>{{ doc.get_formatted("report_date") }}</strong></div>
      <div class="lj-report-meta"><span>{{ "Leistungszeitraum" if is_german else "Service period" }}</span><strong>{{ doc.get_formatted("period_start") }} &ndash; {{ doc.get_formatted("period_end") }}</strong></div>
      {% if doc.sales_invoice %}<div class="lj-report-meta"><span>{{ "Zugehörige Rechnung" if is_german else "Related invoice" }}</span><strong>{{ doc.sales_invoice | e }}</strong></div>{% endif %}
    </div>
  </div>

  {% if doc.report_title %}<h2 class="lj-report-title">{{ doc.report_title | e }}</h2>{% endif %}
  {% if doc.summary %}
    <div class="lj-report-summary">
      <div class="lj-report-label">{{ "Zusammenfassung" if is_german else "Summary" }}</div>
      <p>{{ doc.summary | e }}</p>
    </div>
  {% endif %}

  <div class="lj-report-label lj-report-section-label">{{ "Erbrachte Leistungen" if is_german else "Services performed" }}</div>
  <table class="lj-report-table">
    <thead><tr>
      <th>{{ "Datum" if is_german else "Date" }}</th>
      <th>{{ "Tätigkeit und Inhalt" if is_german else "Activity and details" }}</th>
      <th class="lj-report-hours">{{ "Stunden" if is_german else "Hours" }}</th>
    </tr></thead>
    <tbody>
      {% for row in doc.activities %}
      <tr>
        <td class="lj-report-date">{{ row.get_formatted("service_date", doc) }}</td>
        <td><div class="lj-report-activity-title">{{ row.activity_title | e }}</div>{% if row.details %}<div class="lj-report-details">{{ row.details | e }}</div>{% endif %}</td>
        <td class="lj-report-hours">{{ row.get_formatted("hours", doc) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="lj-report-total"><span>{{ "Gesamtaufwand" if is_german else "Total time" }}</span><strong>{{ doc.get_formatted("total_hours") }} {{ "Stunden" if is_german else "hours" }}</strong></div>

  <div class="lj-report-footer">
    <div><strong>{{ doc.company | e }}</strong><br>{{ company_email | e }}<br>{{ company_website | e }}</div>
    <div>{{ "Dieser Tätigkeitsbericht dokumentiert die erbrachten Leistungen im genannten Zeitraum." if is_german else "This report records the services performed during the stated period." }}</div>
  </div>
</div>
"""


ACTIVITY_REPORT_CSS = """
@page { size: A4; margin: 12mm; }
.print-format { padding: 0 !important; background: #fff !important; }
.lj-activity-report { color: #14161c; font-family: Inter, Arial, sans-serif; font-size: 10px; line-height: 1.5; }
.lj-report-hero { display: flex; justify-content: space-between; align-items: flex-start; padding: 7mm 0 6mm; border-bottom: 2px solid #00009d; break-inside: avoid; }
.lj-report-logo { width: 110px; height: 29px; display: block; }
.lj-report-claim { margin-top: 8px; color: #646b79; font-size: 8px; letter-spacing: 1.1px; }
.lj-report-heading { text-align: right; }
.lj-report-kicker { color: #00009d; font-size: 8px; font-weight: 700; letter-spacing: 1.5px; }
.lj-report-heading h1 { margin: 3px 0 2px; color: #11123b; font-size: 26px; font-weight: 700; line-height: 1.1; }
.lj-report-number { color: #5d6470; font-size: 10px; }
.lj-report-draft { display: inline-block; margin-top: 13px; padding: 3px 8px; border: 1px solid #c8ccd5; color: #555b66; font-size: 8px; font-weight: 700; letter-spacing: 1px; }
.lj-report-info { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 20px; break-inside: avoid; }
.lj-report-card { min-height: 72px; padding: 14px 16px; border: 1px solid #e0e3e9; background: #f8f9fb !important; }
.lj-report-label { color: #00009d; font-size: 8px; font-weight: 700; letter-spacing: 1.1px; text-transform: uppercase; }
.lj-report-customer { margin-top: 7px; font-size: 15px; font-weight: 700; color: #11123b; }
.lj-report-address { margin-top: 5px; color: #4d5561; white-space: pre-line; }
.lj-report-meta { display: flex; justify-content: space-between; gap: 15px; margin-top: 8px; border-bottom: 1px solid #e6e8ed; padding-bottom: 5px; }
.lj-report-meta span { color: #5d6470; }
.lj-report-meta strong { text-align: right; font-weight: 600; }
.lj-report-title { margin: 16px 0 6px; color: #11123b; font-size: 16px; line-height: 1.35; }
.lj-report-summary { margin-top: 10px; padding: 11px 16px; border-left: 3px solid #6756d6; background: #f6f6fb !important; break-inside: avoid; }
.lj-report-summary p { margin: 6px 0 0; white-space: pre-line; }
.lj-report-section-label { margin: 16px 0 7px; }
.lj-report-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.lj-report-table thead { display: table-header-group; }
.lj-report-table th { padding: 8px 10px; background: #11123b !important; color: #fff; font-size: 8px; font-weight: 700; letter-spacing: .5px; text-align: left; }
.lj-report-table th:first-child, .lj-report-date { width: 19%; }
.lj-report-table th:last-child, .lj-report-hours { width: 14%; text-align: right; }
.lj-report-table td { padding: 6px 10px; border-bottom: 1px solid #e1e4ea; vertical-align: top; }
.lj-report-table tr { break-inside: avoid; page-break-inside: avoid; }
.lj-report-date { color: #4d5561; font-weight: 600; }
.lj-report-activity-title { font-weight: 700; color: #11123b; }
.lj-report-details { margin-top: 4px; color: #434a56; white-space: pre-line; overflow-wrap: anywhere; }
.lj-report-total { display: flex; justify-content: flex-end; gap: 30px; margin-top: 8px; padding: 9px 13px; border-top: 2px solid #00009d; color: #11123b; break-inside: avoid; }
.lj-report-total strong { font-size: 12px; }
.lj-report-footer { display: flex; justify-content: space-between; gap: 18px; margin-top: 16px; padding-top: 10px; border-top: 1px solid #dce0e7; color: #667080; font-size: 8px; break-inside: avoid; }
.lj-report-footer > div { width: 50%; }
.lj-report-footer > div:last-child { text-align: right; }
.lj-report-footer strong { color: #11123b; }
"""
