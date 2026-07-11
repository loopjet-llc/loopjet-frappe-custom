from __future__ import annotations

import frappe
from frappe.utils.caching import redis_cache

from loopjet_frappe_custom.branding import install_branding

SUPPORTED_FRAPPE_MAJOR = 16


def _validate_framework_version() -> None:
	major = int(frappe.__version__.split(".", 1)[0])
	if major != SUPPORTED_FRAPPE_MAJOR:
		frappe.throw(
			f"Loopjet Custom supports Frappe v{SUPPORTED_FRAPPE_MAJOR}; found {frappe.__version__}."
		)


def after_install() -> None:
	_validate_framework_version()
	install_branding()
	frappe.clear_cache()


def after_migrate() -> None:
	_validate_framework_version()
	install_branding()
	frappe.clear_cache()


@redis_cache(ttl=300)
def get_installed_product_apps() -> tuple[str, ...]:
	products = {"erpnext", "hrms", "crm", "helpdesk"}
	return tuple(sorted(products.intersection(frappe.get_installed_apps())))
