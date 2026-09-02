frappe.pages["founder-cockpit"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Founder Cockpit"),
		single_column: true,
	});
	new LoopjetFounderCockpit(page);
};

class LoopjetFounderCockpit {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.activeSurface = "needs_decision";
		this.renderShell();
		this.bindPageActions();
		this.refresh();
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	renderShell() {
		this.$body.html(`
			<div class="lj-cockpit" aria-live="polite">
				<style>
					.lj-cockpit { box-sizing: border-box; width: 100%; max-width: 1180px; margin: 0 auto; padding: 0 24px 32px; color: var(--text-color); }
					.lj-cockpit-hero {
						display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;
						padding: 20px 22px; margin-bottom: 12px; border: 1px solid var(--border-color);
						border-radius: 16px; background: linear-gradient(135deg, rgba(19, 107, 89, .13), rgba(33, 150, 243, .08));
					}
					.lj-cockpit-hero h2 { margin: 0 0 5px; font-size: 23px; line-height: 1.25; }
					.lj-cockpit-hero p { max-width: 720px; margin: 0; color: var(--text-muted); line-height: 1.45; }
					.lj-cockpit-generated { flex: 0 0 auto; color: var(--text-muted); font-size: 12px; }
					.lj-cockpit-surfaces { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
					.lj-cockpit-surface {
						appearance: none; width: 100%; padding: 13px 15px; text-align: left; cursor: pointer;
						border: 1px solid var(--border-color); border-radius: 14px; background: var(--card-bg);
						color: inherit; transition: border-color .15s ease, box-shadow .15s ease;
					}
					.lj-cockpit-surface:hover, .lj-cockpit-surface:focus-visible { border-color: var(--primary); outline: none; }
					.lj-cockpit-surface.active { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(19, 107, 89, .12); }
					.lj-cockpit-surface strong { display: block; margin-top: 2px; font-size: 24px; line-height: 1.05; }
					.lj-cockpit-surface span { color: var(--text-muted); font-size: 12px; }
					.lj-cockpit-panel { overflow: hidden; border: 1px solid var(--border-color); border-radius: 14px; background: var(--card-bg); }
					.lj-cockpit-panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border-color); }
					.lj-cockpit-panel-head h3 { margin: 0; font-size: 17px; }
					.lj-cockpit-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0; }
					.lj-cockpit-list.is-single, .lj-cockpit-list:has(.lj-cockpit-card:only-child) { grid-template-columns: minmax(0, 1fr); }
					.lj-cockpit-card { min-width: 0; padding: 16px; border-bottom: 1px solid var(--border-color); }
					.lj-cockpit-card:nth-child(odd) { border-right: 1px solid var(--border-color); }
					.lj-cockpit-list.is-single .lj-cockpit-card, .lj-cockpit-card:only-child { border-right: 0; }
					.lj-cockpit-card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
					.lj-cockpit-card h4 { margin: 5px 0 5px; font-size: 16px; line-height: 1.35; overflow-wrap: anywhere; }
					.lj-cockpit-domain { color: var(--text-muted); font-size: 12px; font-weight: 600; letter-spacing: .03em; text-transform: uppercase; }
					.lj-cockpit-reason { max-width: 760px; margin: 8px 0; line-height: 1.5; }
					.lj-cockpit-next { max-width: 760px; margin: 8px 0 10px; padding: 9px 11px; border-radius: 9px; background: var(--bg-light-gray); line-height: 1.45; }
					.lj-cockpit-meta { display: flex; flex-wrap: wrap; gap: 7px 14px; color: var(--text-muted); font-size: 12px; }
					.lj-cockpit-actions { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
					.lj-cockpit-pill { flex: 0 0 auto; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
					.lj-cockpit-pill.critical { background: var(--red-100, #ffe3e3); color: var(--red-700, #c92a2a); }
					.lj-cockpit-pill.high { background: var(--orange-100, #ffec99); color: var(--orange-800, #a65f00); }
					.lj-cockpit-pill.medium { background: var(--blue-100, #dbeafe); color: var(--blue-700, #1d4ed8); }
					.lj-cockpit-pill.low { background: var(--gray-100, #f1f3f5); color: var(--gray-700, #495057); }
					.lj-cockpit-empty { grid-column: 1 / -1; padding: 38px 20px; text-align: center; color: var(--text-muted); }
					.lj-cockpit-coverage { margin-top: 12px; border: 1px solid var(--border-color); border-radius: 12px; background: var(--card-bg); }
					.lj-cockpit-coverage summary { padding: 12px 15px; cursor: pointer; font-weight: 600; }
					.lj-cockpit-coverage-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px; padding: 0 16px 16px; }
					.lj-cockpit-coverage-item { padding: 9px 10px; border-radius: 8px; background: var(--bg-light-gray); font-size: 12px; }
					.lj-cockpit-coverage-item strong { display: block; }
					@media (max-width: 760px) {
						.lj-cockpit { padding-inline: 12px; }
						.lj-cockpit-hero { flex-direction: column; gap: 8px; padding: 16px; }
						.lj-cockpit-surfaces { grid-template-columns: 1fr; }
						.lj-cockpit-list { grid-template-columns: 1fr; }
						.lj-cockpit-card:nth-child(odd) { border-right: 0; }
						.lj-cockpit-actions .btn { flex: 1 1 auto; min-height: 38px; }
					}
				</style>
				<section class="lj-cockpit-hero" aria-labelledby="lj-cockpit-heading">
					<div>
						<h2 id="lj-cockpit-heading">${__("Only what needs judgment today")}</h2>
						<p>${__("Actionable exceptions from Sales, clients, finance, operations, and team work. Healthy activity stays hidden by default.")}</p>
					</div>
					<div class="lj-cockpit-generated"></div>
				</section>
				<nav class="lj-cockpit-surfaces" aria-label="${__("Cockpit surfaces")}"></nav>
				<section class="lj-cockpit-panel" aria-labelledby="lj-cockpit-panel-title">
					<div class="lj-cockpit-panel-head"><h3 id="lj-cockpit-panel-title"></h3><span class="lj-cockpit-panel-count text-muted"></span></div>
					<div class="lj-cockpit-list"></div>
				</section>
				<details class="lj-cockpit-coverage"><summary>${__("Coverage and unconnected sources")}</summary><div class="lj-cockpit-coverage-list"></div></details>
			</div>
		`);
	}

	bindPageActions() {
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh-cw");
	}

	async refresh() {
		const response = await frappe.call({
			method: "loopjet_frappe_custom.founder_cockpit.api.get_context",
			type: "GET",
			freeze: true,
			freeze_message: __("Loading actionable exceptions..."),
		});
		this.context = response.message || {};
		if (!(this.context.surfaces?.[this.activeSurface] || []).length) {
			this.activeSurface = this.context.counts?.today ? "today" : "needs_decision";
		}
		if (this.context.can_manage && !this.settingsActionAdded) {
			this.page.add_action_item(__("Cockpit Settings"), () => frappe.set_route("Form", "Founder Cockpit Settings"));
			this.settingsActionAdded = true;
		}
		this.render();
	}

	render() {
		this.$body.find(".lj-cockpit-generated").text(__("Updated {0}", [this.context.generated_at || ""]));
		this.renderSurfaces();
		this.renderActiveSurface();
		this.renderCoverage();
	}

	renderSurfaces() {
		const surfaces = [
			["today", __("Today"), __("Due or critical")],
			["needs_decision", __("Needs my decision"), __("Explicit founder judgment")],
			["watchlist", __("Watchlist"), __("Actionable, not due yet")],
		];
		this.$body.find(".lj-cockpit-surfaces").html(
			surfaces.map(([key, label, detail]) => `
				<button type="button" class="lj-cockpit-surface ${key === this.activeSurface ? "active" : ""}" data-surface="${key}" aria-pressed="${key === this.activeSurface}">
					${this.escape(label)}<strong>${Number(this.context.counts?.[key] || 0)}</strong><span>${this.escape(detail)}</span>
				</button>
			`).join("")
		);
		this.$body.find("[data-surface]").on("click", (event) => {
			this.activeSurface = $(event.currentTarget).attr("data-surface");
			this.renderSurfaces();
			this.renderActiveSurface();
		});
	}

	renderActiveSurface() {
		const labels = {
			today: __("Today"),
			needs_decision: __("Needs my decision"),
			watchlist: __("Watchlist"),
		};
		const cards = this.context.surfaces?.[this.activeSurface] || [];
		this.$body.find(".lj-cockpit-panel-head h3").text(labels[this.activeSurface]);
		this.$body.find(".lj-cockpit-panel-count").text(__("{0} exceptions", [cards.length]));
		this.$body.find(".lj-cockpit-list").toggleClass("is-single", cards.length === 1).html(
			cards.length
				? cards.map((card) => this.renderCard(card)).join("")
				: `<div class="lj-cockpit-empty"><strong>${__("No actionable exceptions here.")}</strong><br>${__("Normal activity remains hidden.")}</div>`
		);
		this.bindCardActions();
	}

	renderCard(card) {
		const metadata = [];
		if (card.owner) metadata.push(__("Owner: {0}", [card.owner]));
		if (card.due_at) metadata.push(__("Due: {0}", [card.due_at]));
		if (Number.isFinite(card.age_days)) metadata.push(__("Age: {0} days", [card.age_days]));
		if (card.company) metadata.push(__("Scope: {0}", [card.company]));
		metadata.push(`${card.source_doctype} ${card.source_name}`);
		return `
			<article class="lj-cockpit-card" data-card-id="${this.escape(card.card_id)}" data-doctype="${this.escape(card.source_doctype)}" data-docname="${this.escape(card.source_name)}">
				<div class="lj-cockpit-card-head">
					<div><div class="lj-cockpit-domain">${this.escape(card.domain)} · ${this.escape(card.exception_type)}</div><h4>${this.escape(card.title)}</h4></div>
					<span class="lj-cockpit-pill ${this.escape(String(card.priority || "Low").toLowerCase())}">${this.escape(card.priority)} ${Number(card.priority_score || 0)}</span>
				</div>
				<p class="lj-cockpit-reason">${this.escape(card.reason)}</p>
				<div class="lj-cockpit-next"><strong>${__("Recommended next action")}</strong><br>${this.escape(card.recommended_action)}</div>
				<div class="lj-cockpit-meta">${metadata.map((item) => `<span>${this.escape(item)}</span>`).join("")}</div>
				<div class="lj-cockpit-actions">
					<a class="btn btn-primary btn-sm" href="${this.escape(card.source_url)}">${__("Open source")}</a>
					<button type="button" class="btn btn-default btn-sm" data-action="schedule">${__("Schedule follow-up")}</button>
					<button type="button" class="btn btn-default btn-sm" data-action="acknowledge">${__("Acknowledge")}</button>
				</div>
			</article>
		`;
	}

	bindCardActions() {
		this.$body.find("[data-action]").on("click", (event) => {
			const $button = $(event.currentTarget);
			const $card = $button.closest("[data-card-id]");
			const source = {
				card_id: $card.attr("data-card-id"),
				source_doctype: $card.attr("data-doctype"),
				source_name: $card.attr("data-docname"),
			};
			if ($button.attr("data-action") === "acknowledge") {
				this.acknowledge(source);
			} else {
				this.schedule(source);
			}
		});
	}

	async acknowledge(source) {
		await frappe.call({ method: "loopjet_frappe_custom.founder_cockpit.api.acknowledge", args: source, freeze: true });
		frappe.show_alert({ message: __("Exception acknowledged temporarily."), indicator: "green" });
		await this.refresh();
	}

	schedule(source) {
		frappe.prompt(
			[
				{ fieldname: "due_date", fieldtype: "Date", label: __("Follow-up date"), default: frappe.datetime.add_days(frappe.datetime.get_today(), 1), reqd: 1 },
				{ fieldname: "priority", fieldtype: "Select", label: __("Priority"), options: "High\nMedium\nLow", default: "High", reqd: 1 },
			],
			async (values) => {
				await frappe.call({
					method: "loopjet_frappe_custom.founder_cockpit.api.schedule_follow_up",
					args: { ...source, due_date: values.due_date, priority: values.priority },
					freeze: true,
				});
				frappe.show_alert({ message: __("Native follow-up scheduled."), indicator: "green" });
				await this.refresh();
			},
			__("Schedule a native follow-up"),
			__("Schedule")
		);
	}

	renderCoverage() {
		const coverage = this.context.coverage || [];
		this.$body.find(".lj-cockpit-coverage-list").html(
			coverage.map((item) => `
				<div class="lj-cockpit-coverage-item"><strong>${this.escape(item.source)} · ${this.escape(item.status)}</strong>${this.escape(item.reason)}</div>
			`).join("")
		);
	}
}
