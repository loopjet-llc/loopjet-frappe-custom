frappe.ui.form.on("AI SDR Settings", {
	refresh(frm) {
		if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("AI SDR Manager")) {
			return;
		}
		const provider = frm.doc.ai_provider || __("AI provider");
		frm.add_custom_button(__("Test {0} Connection", [provider]), async () => {
			await frm.save();
			const response = await frappe.call({
				method: "loopjet_frappe_custom.ai_sdr.api.test_ai_connection",
				freeze: true,
				freeze_message: __("Calling the configured model..."),
			});
			const result = response.message || {};
			if (result.connected) {
				frappe.show_alert({
					message: __("AI connection verified with a real model response."),
					indicator: "green",
				});
			} else {
				frappe.msgprint({
					title: __("AI connection failed"),
					message: frappe.utils.escape_html(result.error || __("The provider did not return a valid response.")),
					indicator: "red",
				});
			}
			await frm.reload_doc();
		});
	},
});
