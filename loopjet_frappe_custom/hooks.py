app_name = "loopjet_frappe_custom"
app_title = "Loopjet Custom"
app_publisher = "Loopjet LLC"
app_description = "Upgrade-safe extensions for the Loopjet Frappe platform"
app_email = "engineering@loopjet.com"
app_license = "GNU Affero General Public License (v3)"

# Product apps are intentionally optional. The same package can be installed on
# the ERP/HR, CRM, and Helpdesk sites without coupling their upgrade schedules.
required_apps = []

after_install = "loopjet_frappe_custom.install.after_install"
after_migrate = "loopjet_frappe_custom.install.after_migrate"

get_website_user_home_page = "loopjet_frappe_custom.portal.get_website_user_home_page"

website_redirects = [
	{"source": "/portal", "target": "/helpdesk/my-tickets", "redirect_http_status": 302},
	{"source": "/issues", "target": "/helpdesk/my-tickets", "redirect_http_status": 302},
	{"source": "/support", "target": "/helpdesk/my-tickets/new", "redirect_http_status": 302},
]

# Add reviewed exports here. Avoid broad, unfiltered fixtures that can capture
# site-specific or personal configuration.
fixtures = []

doc_events = {
	"Communication": {
		"after_insert": "loopjet_frappe_custom.ai_sdr.services.handle_received_communication",
	},
	"CRM Deal": {
		"after_insert": "loopjet_frappe_custom.ai_sdr.services.stop_enrollments_for_deal",
	},
}

scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"loopjet_frappe_custom.ai_sdr.services.process_due_enrollments",
		],
	},
}

permission_query_conditions = {
	"AI SDR Research": "loopjet_frappe_custom.ai_sdr.permissions.research_query_condition",
	"AI SDR Enrollment": "loopjet_frappe_custom.ai_sdr.permissions.enrollment_query_condition",
	"AI SDR Activity": "loopjet_frappe_custom.ai_sdr.permissions.activity_query_condition",
}

has_permission = {
	"AI SDR Research": "loopjet_frappe_custom.ai_sdr.permissions.has_owned_permission",
	"AI SDR Enrollment": "loopjet_frappe_custom.ai_sdr.permissions.has_owned_permission",
	"AI SDR Activity": "loopjet_frappe_custom.ai_sdr.permissions.has_owned_permission",
}
