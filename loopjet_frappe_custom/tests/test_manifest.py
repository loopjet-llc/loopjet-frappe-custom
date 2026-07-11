from pathlib import Path

from loopjet_frappe_custom import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_version_is_semantic() -> None:
	parts = __version__.split(".")
	assert len(parts) == 3
	assert all(part.isdigit() for part in parts)


def test_frappe_metadata_exists() -> None:
	package = ROOT / "loopjet_frappe_custom"
	assert (package / "hooks.py").is_file()
	assert (package / "modules.txt").read_text().strip() == "Loopjet Custom"
	assert (package / "loopjet_custom" / "__init__.py").is_file()
	assert "[post_model_sync]" in (package / "patches.txt").read_text()
