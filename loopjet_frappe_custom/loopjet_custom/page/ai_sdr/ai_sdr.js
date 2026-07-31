frappe.pages["ai-sdr"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "AI SDR",
		single_column: true,
	});
	new LoopjetAISDR(page);
};

class LoopjetAISDR {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.renderShell();
		this.bindPageActions();
		this.refresh();
	}

	escape(value) {
		return frappe.utils.escape_html(String(value || ""));
	}

	renderShell() {
		this.$body.html(`
			<div class="lj-sdr">
				<style>
					.lj-sdr { max-width: 1240px; padding-bottom: 36px; }
					.lj-sdr-hero {
						display: flex; justify-content: space-between; gap: 18px; align-items: flex-start;
						padding: 24px; border: 1px solid var(--border-color); border-radius: 16px;
						background: linear-gradient(135deg, rgba(59, 130, 246, .11), rgba(139, 92, 246, .09));
						margin-bottom: 18px;
					}
					.lj-sdr-hero h2 { margin: 0 0 8px; font-size: 24px; font-weight: 700; }
					.lj-sdr-hero p { margin: 0; max-width: 760px; color: var(--text-muted); }
					.lj-sdr-links { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
					.lj-sdr-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }
					.lj-sdr-metric, .lj-sdr-card {
						border: 1px solid var(--border-color); border-radius: 14px; background: var(--card-bg);
					}
					.lj-sdr-metric { padding: 16px; }
					.lj-sdr-metric strong { display: block; font-size: 26px; line-height: 1.1; }
					.lj-sdr-metric span, .lj-sdr-muted { color: var(--text-muted); }
					.lj-sdr-card { margin-bottom: 16px; overflow: hidden; }
					.lj-sdr-card-head {
						display: flex; justify-content: space-between; align-items: center; gap: 12px;
						padding: 16px 18px; border-bottom: 1px solid var(--border-color);
					}
					.lj-sdr-card-head h3 { margin: 0; font-size: 17px; }
					.lj-sdr-item { padding: 16px 18px; border-bottom: 1px solid var(--border-color); }
					.lj-sdr-item:last-child { border-bottom: 0; }
					.lj-sdr-item-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
					.lj-sdr-item h4 { margin: 0 0 4px; font-size: 15px; }
					.lj-sdr-body {
						white-space: pre-wrap; margin: 12px 0; padding: 12px; border-radius: 10px;
						background: var(--bg-light-gray); max-height: 180px; overflow: auto;
					}
					.lj-sdr-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
					.lj-sdr-config { margin-bottom: 18px; padding: 12px 16px; border-radius: 12px; border: 1px solid var(--border-color); }
					.lj-sdr-config.warning { background: var(--yellow-50, #fff8db); }
					.lj-sdr-config.success { background: var(--green-50, #eafbea); }
					@media (max-width: 680px) {
						.lj-sdr-hero, .lj-sdr-item-top { flex-direction: column; }
						.lj-sdr-links { justify-content: flex-start; }
					}
				</style>
				<div class="lj-sdr-hero">
					<div>
						<h2>${__("Supervised outbound workspace inside Loopjet CRM")}</h2>
						<p>${__("Connect a verified AI model for research, personalized drafting, and reply classification. Lead records come from CRM or an explicit data source; no message is sent without recorded human approval.")}</p>
					</div>
					<div class="lj-sdr-links">
						<a class="btn btn-default btn-sm" href="/crm">${__("Open CRM")}</a>
						<a class="btn btn-default btn-sm" href="/app/ai-sdr-research">${__("Research")}</a>
						<a class="btn btn-default btn-sm" href="/app/ai-sdr-sequence">${__("Sequences")}</a>
						<a class="btn btn-default btn-sm" href="/app/ai-sdr-enrollment">${__("Enrollments")}</a>
						<a class="btn btn-default btn-sm" href="/app/ai-sdr-activity">${__("All Activities")}</a>
					</div>
				</div>
				<div class="lj-sdr-config-wrap"></div>
				<div class="lj-sdr-metrics"></div>
				<div class="lj-sdr-content"></div>
			</div>
		`);
	}

	bindPageActions() {
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh-cw");
		this.page.add_action_item(__("New Research"), () => frappe.new_doc("AI SDR Research"));
		this.page.add_action_item(__("New Sequence"), () => frappe.new_doc("AI SDR Sequence"));
		this.page.add_action_item(__("Suppression List"), () => frappe.set_route("List", "AI SDR Suppression"));
		this.page.add_action_item(__("AI SDR Settings"), () => frappe.set_route("Form", "AI SDR Settings"));
	}

	async refresh() {
		const response = await frappe.call({
			method: "loopjet_frappe_custom.ai_sdr.api.get_dashboard_context",
			freeze: true,
			freeze_message: __("Loading AI SDR..."),
		});
		this.context = response.message || {};
		this.render();
	}

	render() {
		this.renderConfiguration();
		this.renderMetrics();
		this.$body.find(".lj-sdr-content").html(`
			${this.renderApprovalQueue(this.context.activities || [])}
			${this.renderReplies(this.context.replies || [])}
		`);
		this.bindRowActions();
	}

	renderConfiguration() {
		const config = this.context.configuration || {};
		const active = config.ai_configured && config.ai_enabled && config.ai_connected;
		const className = active ? "success" : "warning";
		let aiText;
		if (active) {
			aiText = __("AI SDR active: {0} / {1} is verified and generation is enabled.", [
				config.ai_provider,
				config.ai_model,
			]);
		} else if (config.ai_connected) {
			aiText = __("{0} / {1} is connected, but AI generation is disabled.", [
				config.ai_provider,
				config.ai_model,
			]);
		} else if (config.ai_credentials_present) {
			aiText = __("AI is configured but not verified. Test the provider connection before calling this an active AI SDR.");
		} else {
			aiText = __("AI is not connected. Loopjet is currently operating with manual or fallback-template drafting.");
		}
		const sendText = config.sending_enabled
			? __("Approved email sending is enabled.")
			: __("Email sending is disabled; installation cannot contact prospects.");
		this.$body.find(".lj-sdr-config-wrap").html(`
			<div class="lj-sdr-config ${className}">
				<strong>${aiText}</strong> ${sendText}
				${this.context.can_manage ? `<a href="/app/ai-sdr-settings">${__("Review settings")}</a>` : ""}
			</div>
		`);
	}

	renderMetrics() {
		const metrics = this.context.metrics || {};
		const items = [
			[metrics.research_ready, __("Research ready")],
			[metrics.active_enrollments, __("Active sequences")],
			[metrics.awaiting_approval, __("Awaiting approval")],
			[metrics.approved_to_send, __("Approved to send")],
			[metrics.due_follow_ups, __("Follow-ups due")],
			[metrics.replies_today, __("Replies today")],
		];
		this.$body.find(".lj-sdr-metrics").html(
			items.map(([value, label]) => `
				<div class="lj-sdr-metric"><strong>${Number(value || 0)}</strong><span>${this.escape(label)}</span></div>
			`).join("")
		);
	}

	renderApprovalQueue(activities) {
		const rows = activities.length
			? activities.map((activity) => this.renderActivity(activity)).join("")
			: `<div class="lj-sdr-item lj-sdr-muted">${__("Nothing is waiting in the outreach queue.")}</div>`;
		return `
			<div class="lj-sdr-card">
				<div class="lj-sdr-card-head">
					<h3>${__("Outreach approval queue")}</h3>
					<span class="lj-sdr-muted">${activities.length} ${__("items")}</span>
				</div>
				${rows}
			</div>
		`;
	}

	renderActivity(activity) {
		const canManage = Boolean(this.context.can_manage);
		const canApprove = canManage && ["Draft", "Needs Approval", "Failed"].includes(activity.status);
		const canSend = canManage && activity.status === "Approved" && activity.channel === "Email";
		const canMark = activity.status === "Approved" && ["LinkedIn", "Call"].includes(activity.channel);
		return `
			<div class="lj-sdr-item" data-activity="${this.escape(activity.name)}">
				<div class="lj-sdr-item-top">
					<div>
						<h4>${this.escape(activity.recipient_name || activity.lead || activity.name)}</h4>
						<div class="lj-sdr-muted">${this.escape(activity.channel)} · ${this.escape(activity.activity_type)} · ${this.escape(activity.recipient_email)}</div>
					</div>
					<span class="indicator-pill ${this.statusColor(activity.status)}">${this.escape(activity.status)}</span>
				</div>
				${activity.subject ? `<strong>${this.escape(activity.subject)}</strong>` : ""}
				${activity.body ? `<div class="lj-sdr-body">${this.escape(activity.body)}</div>` : `<div class="lj-sdr-body lj-sdr-muted">${__("No message body yet. Open the record to draft or regenerate it.")}</div>`}
				${activity.last_error ? `<div class="text-danger">${this.escape(activity.last_error)}</div>` : ""}
				<div class="lj-sdr-actions">
					<a class="btn btn-default btn-xs" href="/app/ai-sdr-activity/${encodeURIComponent(activity.name)}">${__("Review / edit")}</a>
					<button class="btn btn-default btn-xs" data-action="regenerate">${__("Generate draft")}</button>
					${canApprove ? `<button class="btn btn-primary btn-xs" data-action="approve">${__("Approve")}</button>` : ""}
					${canManage && !["Rejected", "Sent"].includes(activity.status) ? `<button class="btn btn-default btn-xs" data-action="reject">${__("Reject")}</button>` : ""}
					${canSend ? `<button class="btn btn-primary btn-xs" data-action="send">${__("Send approved email")}</button>` : ""}
					${canMark ? `<button class="btn btn-primary btn-xs" data-action="mark-sent">${activity.channel === "Call" ? __("Mark call completed") : __("Mark LinkedIn sent")}</button>` : ""}
				</div>
			</div>
		`;
	}

	renderReplies(replies) {
		const rows = replies.length
			? replies.map((reply) => `
				<div class="lj-sdr-item">
					<div class="lj-sdr-item-top">
						<div>
							<h4>${this.escape(reply.recipient_name || reply.recipient_email || reply.lead)}</h4>
							<div>${this.escape(reply.subject)}</div>
						</div>
						<span class="indicator-pill blue">${this.escape(reply.reply_classification || __("Needs Review"))}</span>
					</div>
					<div class="lj-sdr-actions">
						<a class="btn btn-default btn-xs" href="/app/ai-sdr-activity/${encodeURIComponent(reply.name)}">${__("Open reply")}</a>
						${reply.lead ? `<a class="btn btn-default btn-xs" href="/crm/leads/${encodeURIComponent(reply.lead)}">${__("Open CRM Lead")}</a>` : ""}
					</div>
				</div>
			`).join("")
			: `<div class="lj-sdr-item lj-sdr-muted">${__("No classified replies yet.")}</div>`;
		return `
			<div class="lj-sdr-card">
				<div class="lj-sdr-card-head"><h3>${__("Recent replies")}</h3></div>
				${rows}
			</div>
		`;
	}

	statusColor(status) {
		if (status === "Approved" || status === "Sent") return "green";
		if (status === "Failed" || status === "Rejected") return "red";
		if (status === "Needs Approval") return "orange";
		return "gray";
	}

	bindRowActions() {
		this.$body.find("[data-action]").on("click", async (event) => {
			const $button = $(event.currentTarget);
			const action = $button.attr("data-action");
			const name = $button.closest("[data-activity]").attr("data-activity");
			if (!name) return;
			if (action === "reject") {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }],
					(values) => this.callAction("reject_activity", { name, reason: values.reason }),
					__("Reject outreach"),
					__("Reject")
				);
				return;
			}
			if (action === "send") {
				const confirmed = await this.confirm(__("Send this individually approved email now?"));
				if (!confirmed) return;
			}
			const methodMap = {
				regenerate: "regenerate_activity",
				approve: "approve_activity",
				send: "send_activity",
				"mark-sent": "mark_manual_sent",
			};
			await this.callAction(methodMap[action], { name });
		});
	}

	async callAction(method, args) {
		if (!method) return;
		await frappe.call({
			method: `loopjet_frappe_custom.ai_sdr.api.${method}`,
			args,
			freeze: true,
		});
		frappe.show_alert({ message: __("AI SDR item updated."), indicator: "green" });
		await this.refresh();
	}

	confirm(message) {
		return new Promise((resolve) => {
			frappe.confirm(message, () => resolve(true), () => resolve(false));
		});
	}
}
