from __future__ import annotations

import frappe

from loopjet_frappe_custom import __version__
from loopjet_frappe_custom.install import get_installed_product_apps


@frappe.whitelist(allow_guest=False)
def health() -> dict[str, object]:
	"""Return a non-sensitive application health payload for authenticated operators."""
	return {
		"status": "ok",
		"custom_app_version": __version__,
		"frappe_version": frappe.__version__,
		"product_apps": get_installed_product_apps(),
	}

