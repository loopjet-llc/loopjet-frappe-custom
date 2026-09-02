from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from html import escape


@dataclass(frozen=True)
class EmailBrandProfile:
	brand: str
	sender_name: str
	sender_email: str
	company_name: str
	accent_color: str

	@property
	def formatted_sender(self) -> str:
		return f"{self.sender_name} <{self.sender_email}>"


LOOPJET_SUPPORT_PROFILE = EmailBrandProfile(
	brand="loopjet",
	sender_name="Ahmad El-Ali | Loopjet LLC",
	sender_email="support@loopjet.io",
	company_name="Loopjet LLC",
	accent_color="#0891b2",
)


def resolve_email_brand(*, brand: str, sender: str) -> EmailBrandProfile:
	"""Resolve the exact configured profile and reject cross-brand sender leakage."""
	_, sender_email = parseaddr(str(sender or ""))
	profile = LOOPJET_SUPPORT_PROFILE if brand == "loopjet" else None
	if profile is None or sender_email.strip().lower() != profile.sender_email:
		raise ValueError("email_brand_sender_mismatch")
	return profile


def render_loopjet_signature(*, sender: str) -> str:
	profile = resolve_email_brand(brand="loopjet", sender=sender)
	return (
		f'<div data-email-brand="{profile.brand}" style="margin-top:28px;padding-top:18px;'
		f'border-top:1px solid #d6dde5;color:#334155;font-family:Arial,Helvetica,sans-serif;line-height:1.55">'
		f'<strong style="color:#0f172a">{escape("Ahmad El-Ali")}</strong><br>'
		f'{escape(profile.company_name)}<br>'
		f'<a href="mailto:{profile.sender_email}" style="color:{profile.accent_color};text-decoration:none">'
		f'{profile.sender_email}</a></div>'
	)
