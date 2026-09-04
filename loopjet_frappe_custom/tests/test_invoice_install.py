import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def test_reinstall_preserves_light_invoice_and_original_offer(monkeypatch):
	monkeypatch.setitem(sys.modules, "frappe", SimpleNamespace(db=SimpleNamespace(exists=lambda *args: True)))
	path = Path(__file__).resolve().parents[1] / "branding.py"
	spec = importlib.util.spec_from_file_location("invoice_branding_under_test", path)
	branding = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(branding)
	documents = {name: SimpleNamespace(html="old", css="old") for name in branding.PRINT_FORMAT_NAME_BY_DOCTYPE.values()}
	monkeypatch.setattr(branding, "_get_or_new", lambda doctype, name: documents[name])
	monkeypatch.setattr(branding, "_save", Mock())
	monkeypatch.setattr(branding, "_set_default_print_format", Mock())
	monkeypatch.setattr(branding, "_disable_legacy_print_formats", Mock())
	for _ in range(2):
		branding.install_print_formats()
		assert documents["Loopjet Invoice"].html == branding.INVOICE_HTML
		assert documents["Loopjet Invoice"].css == branding.INVOICE_CSS
		assert documents["Loopjet Offer"].html == branding.PRINT_HTML
		assert documents["Loopjet Offer"].css == branding.PRINT_CSS
