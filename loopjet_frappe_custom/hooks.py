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
