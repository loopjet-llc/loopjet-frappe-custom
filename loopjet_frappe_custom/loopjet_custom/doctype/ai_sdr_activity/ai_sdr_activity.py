import frappe
from frappe import _
from frappe.model.document import Document


class AISDRActivity(Document):
	def validate(self) -> None:
		self.validate_protected_transitions()
		self.validate_approved_content()
		self.validate_approval_state()
		self.validate_delivery_state()

	def validate_protected_transitions(self) -> None:
		previous = self.get_doc_before_save()
		previous_status = previous.status if previous else None
		if self.status == "Approved" and previous_status != "Approved":
			if not self.flags.get("ai_sdr_approval_action"):
				frappe.throw(_("Use the AI SDR approval action to approve outreach."))
		if self.status == "Rejected" and previous_status != "Rejected":
			if not self.flags.get("ai_sdr_rejection_action"):
				frappe.throw(_("Use the AI SDR rejection action to reject outreach."))
		if self.status == "Sent" and previous_status != "Sent":
			if not self.flags.get("ai_sdr_delivery_action"):
				frappe.throw(_("Use the AI SDR delivery action to record delivery."))

	def validate_approved_content(self) -> None:
		previous = self.get_doc_before_save()
		if not previous or previous.status != "Approved" or self.status != "Approved":
			return
		protected_fields = ("channel", "recipient_email", "subject", "body")
		if any(previous.get(fieldname) != self.get(fieldname) for fieldname in protected_fields):
			frappe.throw(_("Approved recipient and message content cannot be changed. Reject and redraft it first."))

	def validate_approval_state(self) -> None:
		if self.status in {"Approved", "Sent"}:
			if not self.approved_by or not self.approved_at:
				frappe.throw(_("Approved By and Approved At are required before delivery."))
			if self.channel != "Call" and not (self.body or "").strip():
				frappe.throw(_("An approved outreach activity must contain a message body."))

	def validate_delivery_state(self) -> None:
		if self.status != "Sent":
			return
		if not self.sent_at:
			frappe.throw(_("Sent At is required for a sent activity."))
		if self.channel == "Email" and not self.recipient_email:
			frappe.throw(_("Recipient Email is required for an email activity."))
