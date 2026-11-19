frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 2) {
			return;
		}

		frm.add_custom_button(__("Tätigkeitsbericht öffnen / anlegen"), async () => {
			const response = await frappe.call({
				method: "loopjet_frappe_custom.activity_reports.get_or_create_for_invoice",
				args: { invoice_name: frm.doc.name },
				freeze: true,
			});
			if (response.message?.name) {
				frappe.set_route("Form", "Loopjet Activity Report", response.message.name);
			}
		}, __("Erstellen"));
	},
});
