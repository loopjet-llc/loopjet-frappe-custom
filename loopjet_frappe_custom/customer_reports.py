from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

CUSTOMER_REPORT_DOCTYPE = "Loopjet Customer Report"


def is_customer_report_pdf(file_url: str | None) -> bool:
	"""Return whether a report attachment has a PDF filename."""
	return urlparse(file_url or "").path.lower().endswith(".pdf")


def make_customer_report_file_private(doc: Any) -> Any:
	"""Keep report uploads private even if a user changes the upload default."""
	if getattr(doc, "attached_to_doctype", None) == CUSTOMER_REPORT_DOCTYPE:
		doc.is_private = 1
	return doc
