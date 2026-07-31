frappe.ui.form.on("AI SDR Research", {
	refresh(frm) {
		const roles = new Set(frappe.user_roles || []);
		const canManage =
			roles.has("System Manager") ||
			roles.has("AI SDR Manager") ||
			frappe.session.user === "Administrator";
		const canAnalyze = ["Draft", "Ready for Analysis", "Stale", "Failed"].includes(
			frm.doc.status
		);
		if (frm.is_new() || !canManage || !canAnalyze) return;

		frm.add_custom_button(__("Analyze with AI"), async () => {
			await frappe.call({
				method: "loopjet_frappe_custom.ai_sdr.api.analyze_research",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Queueing account analysis..."),
			});
			frappe.show_alert({
				message: __("Account analysis queued."),
				indicator: "green",
			});
			await frm.reload_doc();
		});
	},
});
