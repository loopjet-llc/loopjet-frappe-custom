from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
	import frappe as _frappe
except ModuleNotFoundError:  # Allows the pure helper functions to be tested without Frappe installed.
	_frappe = None

CUSTOMER_REPORT_DOCTYPE = "Loopjet Customer Report"


def _whitelist(function):
	if _frappe is None:
		return function
	return _frappe.whitelist()(function)


def is_customer_report_pdf(file_url: str | None) -> bool:
	"""Return whether a report attachment has a PDF filename."""
	return urlparse(file_url or "").path.lower().endswith(".pdf")


def make_customer_report_file_private(doc: Any) -> Any:
	"""Keep report uploads private even if a user changes the upload default."""
	if getattr(doc, "attached_to_doctype", None) == CUSTOMER_REPORT_DOCTYPE:
		doc.is_private = 1
	return doc


@_whitelist
def download_customer_report(name: str) -> None:
	"""Download the report attachment as raw bytes after checking report access."""
	if _frappe is None:
		raise RuntimeError("Frappe must be installed to download a customer report.")

	report = _frappe.get_doc(CUSTOMER_REPORT_DOCTYPE, name)
	report.check_permission("read")
	if not report.report_file:
		_frappe.throw("Für diesen Bericht ist keine PDF-Datei hinterlegt.")

	file = _frappe.get_doc("File", {"file_url": report.report_file})
	if not file.is_private:
		_frappe.throw("Der Bericht muss als private Datei hinterlegt sein.")

	file_path = Path(file.get_full_path())
	if not file_path.is_file():
		_frappe.throw("Die hinterlegte Berichtsdatei wurde nicht gefunden.")

	_frappe.local.response.filename = file.file_name
	_frappe.local.response.filecontent = file_path.read_bytes()
	_frappe.local.response.type = "download"
