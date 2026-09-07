const CUSTOMER_REPORT_DOWNLOAD_METHOD = "loopjet_frappe_custom.customer_reports.download_customer_report";

function reportDownloadUrl(reportName) {
	return `/api/method/${CUSTOMER_REPORT_DOWNLOAD_METHOD}?name=${encodeURIComponent(reportName)}`;
}

frappe.ui.form.on("Loopjet Customer Report", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.report_file) {
			return;
		}

		frm.add_custom_button(__("PDF herunterladen"), () => {
			window.open(reportDownloadUrl(frm.doc.name), "_blank", "noopener");
		});
	},
});
