const DOWNLOAD_FILE_METHOD = "frappe.utils.file_manager.download_file";

function reportDownloadUrl(reportFile) {
	return `/api/method/${DOWNLOAD_FILE_METHOD}?file_url=${encodeURIComponent(reportFile)}`;
}

frappe.ui.form.on("Loopjet Customer Report", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.report_file) {
			return;
		}

		frm.add_custom_button(__("PDF herunterladen"), () => {
			window.open(reportDownloadUrl(frm.doc.report_file), "_blank", "noopener");
		});
	},
});
