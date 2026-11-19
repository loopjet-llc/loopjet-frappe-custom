frappe.ui.form.on("Loopjet Activity Report", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("PDF herunterladen"), () => {
			const params = new URLSearchParams({
				doctype: "Loopjet Activity Report",
				name: frm.doc.name,
				format: "Loopjet Tätigkeitsbericht",
				no_letterhead: "0",
			});
			window.open(`/api/method/frappe.utils.print_format.download_pdf?${params}`, "_blank", "noopener");
		});

		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Rechnung öffnen"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			});
		}
	},
});
