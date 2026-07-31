from __future__ import annotations

import frappe
from frappe.installer import update_site_config
from frappe.utils.caching import redis_cache

from loopjet_frappe_custom.ai_sdr.install import install_ai_sdr
from loopjet_frappe_custom.branding import install_branding
from loopjet_frappe_custom.inbound_email import required_file_size_limit
from loopjet_frappe_custom.portal import install_ticket_portal
from loopjet_frappe_custom.workspace import install_raven_home_shortcut

SUPPORTED_FRAPPE_MAJOR = 16


def _validate_framework_version() -> None:
	major = int(frappe.__version__.split(".", 1)[0])
	if major != SUPPORTED_FRAPPE_MAJOR:
		frappe.throw(f"Loopjet Custom supports Frappe v{SUPPORTED_FRAPPE_MAJOR}; found {frappe.__version__}.")


def after_install() -> None:
	_validate_framework_version()
	ensure_inbound_attachment_capacity()
	install_branding()
	install_ticket_portal()
	install_raven_home_shortcut()
	install_ai_sdr()
	frappe.clear_cache()


def after_migrate() -> None:
	_validate_framework_version()
	ensure_inbound_attachment_capacity()
	install_branding()
	install_ticket_portal()
	install_raven_home_shortcut()
	install_ai_sdr()
	frappe.clear_cache()


def ensure_inbound_attachment_capacity() -> None:
	configured_limit = frappe.conf.get("max_file_size")
	try:
		configured_limit = int(configured_limit or 0)
	except (TypeError, ValueError):
		configured_limit = 0
	required_limit = required_file_size_limit(configured_limit)
	if configured_limit >= required_limit:
		return
	update_site_config("max_file_size", required_limit, validate=False)
	frappe.local.conf.max_file_size = required_limit


@redis_cache(ttl=300)
def get_installed_product_apps() -> tuple[str, ...]:
	products = {"erpnext", "hrms", "crm", "helpdesk"}
	return tuple(sorted(products.intersection(frappe.get_installed_apps())))
