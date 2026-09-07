frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(
			__("Bericht hochladen"),
			() => frappe.new_doc("Loopjet Customer Report", {customer: frm.doc.name}),
			__("Kundenberichte"),
		);
		frm.add_custom_button(
			__("Kundenberichte öffnen"),
			() => frappe.set_route("List", "Loopjet Customer Report", {customer: frm.doc.name}),
			__("Kundenberichte"),
		);
	},
});
