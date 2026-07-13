frappe.pages["mcp-setup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "MCP Setup",
		single_column: true,
	});

	new LoopjetMCPSetup(page);
};

class LoopjetMCPSetup {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.render_shell();
		this.bind_page_actions();
		this.refresh();
	}

	render_shell() {
		this.$body.html(`
			<div class="loopjet-mcp-setup">
				<style>
					.loopjet-mcp-setup { max-width: 1120px; }
					.lj-mcp-hero {
						padding: 24px;
						border: 1px solid var(--border-color);
						border-radius: 16px;
						background: linear-gradient(135deg, rgba(34, 211, 238, 0.12), rgba(139, 92, 246, 0.10));
						margin-bottom: 18px;
					}
					.lj-mcp-hero h2 { margin: 0 0 8px; font-size: 24px; font-weight: 700; }
					.lj-mcp-hero p { margin: 0; color: var(--text-muted); max-width: 760px; }
					.lj-mcp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
					.lj-mcp-card {
						border: 1px solid var(--border-color);
						border-radius: 14px;
						background: var(--card-bg);
						padding: 18px;
						margin-bottom: 16px;
					}
					.lj-mcp-card h3 { margin: 0 0 8px; font-size: 17px; font-weight: 650; }
					.lj-mcp-muted { color: var(--text-muted); }
					.lj-mcp-row { display: flex; justify-content: space-between; gap: 12px; margin: 8px 0; }
					.lj-mcp-value { font-family: var(--font-stack-monospace); word-break: break-all; }
					.lj-mcp-secret {
						border: 1px solid var(--yellow-border-color, #f0d98c);
						background: var(--yellow-50, #fff8db);
						border-radius: 12px;
						padding: 12px;
						margin-top: 12px;
					}
					.lj-mcp-code-wrap { margin-top: 12px; }
					.lj-mcp-code-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
					.lj-mcp-code-title { font-weight: 650; }
					.lj-mcp-code {
						white-space: pre-wrap;
						word-break: break-word;
						font-family: var(--font-stack-monospace);
						font-size: 12px;
						line-height: 1.45;
						background: var(--bg-light-gray);
						border: 1px solid var(--border-color);
						border-radius: 10px;
						padding: 12px;
						max-height: 360px;
						overflow: auto;
					}
					.lj-mcp-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
					.lj-mcp-warning { margin: 8px 0 0; padding-left: 18px; color: var(--text-muted); }
				</style>
				<div class="lj-mcp-hero">
					<h2>Connect Claude, ChatGPT, Codex, or another MCP client to Loopjet Frappe.</h2>
					<p>Generate your own Frappe API credentials, copy the ready-made MCP connection config, and let your AI agent work only with the permissions your Frappe user already has.</p>
				</div>
				<div class="lj-mcp-status"></div>
				<div class="lj-mcp-content"></div>
			</div>
		`);
	}

	bind_page_actions() {
		this.page.set_primary_action(__("Generate / Rotate Key"), () => this.generate_key(), "key");
		this.page.add_action_item(__("Refresh"), () => this.refresh());
		this.page.add_action_item(__("Revoke MCP Key"), () => this.revoke_key());
	}

	async refresh() {
		const response = await frappe.call({
			method: "loopjet_frappe_custom.mcp_setup.get_mcp_setup_context",
		});
		this.context = response.message;
		this.render();
	}

	async generate_key() {
		const proceed = await this.confirm(
			__("Generate a new MCP API secret? Any previous secret for your Frappe user will stop working.")
		);
		if (!proceed) return;

		const response = await frappe.call({
			method: "loopjet_frappe_custom.mcp_setup.generate_mcp_api_key",
			freeze: true,
			freeze_message: __("Generating MCP credentials..."),
		});
		this.context = response.message;
		this.render();
		frappe.show_alert({ message: __("MCP key generated. Copy the secret now."), indicator: "green" });
	}

	async revoke_key() {
		const proceed = await this.confirm(
			__("Revoke your MCP API key? Any Claude, ChatGPT, or agent connection using it will stop working.")
		);
		if (!proceed) return;

		const response = await frappe.call({
			method: "loopjet_frappe_custom.mcp_setup.revoke_mcp_api_key",
			freeze: true,
			freeze_message: __("Revoking MCP credentials..."),
		});
		this.context = response.message;
		this.render();
		frappe.show_alert({ message: __("MCP key revoked."), indicator: "orange" });
	}

	confirm(message) {
		return new Promise((resolve) => {
			frappe.confirm(message, () => resolve(true), () => resolve(false));
		});
	}

	render() {
		const c = this.context;
		const conn = c.connections || {};
		this.copy_values = [];
		const status = c.has_api_key
			? `<span class="indicator-pill green">${__("API key active")}</span>`
			: `<span class="indicator-pill gray">${__("No MCP key yet")}</span>`;

		this.$body.find(".lj-mcp-status").html(`
			<div class="lj-mcp-card">
				<div class="lj-mcp-row"><div>${__("Signed in user")}</div><div class="lj-mcp-value">${frappe.utils.escape_html(c.user || "")}</div></div>
				<div class="lj-mcp-row"><div>${__("MCP endpoint")}</div><div class="lj-mcp-value">${frappe.utils.escape_html(c.server_url || "")}</div></div>
				<div class="lj-mcp-row"><div>${__("Credential status")}</div><div>${status}</div></div>
				${c.api_key ? `<div class="lj-mcp-row"><div>${__("API key")}</div><div class="lj-mcp-value">${frappe.utils.escape_html(c.api_key)}</div></div>` : ""}
				${
					c.secret_visible
						? `<div class="lj-mcp-secret">
								<strong>${__("Copy now:")}</strong> ${__("This API secret is shown only once. Store it in your password manager or agent secret store.")}
								<div class="lj-mcp-row"><div>${__("API secret")}</div><div class="lj-mcp-value">${frappe.utils.escape_html(c.api_secret || "")}</div></div>
							</div>`
						: ""
				}
				<div class="lj-mcp-actions">
					<button class="btn btn-primary btn-sm" data-action="generate">${__("Generate / Rotate Key")}</button>
					<button class="btn btn-secondary btn-sm" data-action="refresh">${__("Refresh")}</button>
					<button class="btn btn-danger btn-sm" data-action="revoke" ${c.has_api_key ? "" : "disabled"}>${__("Revoke")}</button>
				</div>
				<ul class="lj-mcp-warning">${(c.warnings || []).map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("")}</ul>
			</div>
		`);

		this.$body.find("[data-action='generate']").on("click", () => this.generate_key());
		this.$body.find("[data-action='refresh']").on("click", () => this.refresh());
		this.$body.find("[data-action='revoke']").on("click", () => this.revoke_key());

		this.$body.find(".lj-mcp-content").html(`
			<div class="lj-mcp-grid">
				${this.render_provider_card("ChatGPT API / Responses API", "Use this in OpenAI API calls with the MCP built-in tool.", conn.chatgpt_api_tool_json)}
				${this.render_provider_card("Claude API", "Use this with Anthropic Messages API mcp_servers and mcp_toolset.", conn.claude_api_json)}
				${this.render_provider_card("Claude Code", "Run this locally to add the remote HTTP MCP server.", conn.claude_code_command)}
				${this.render_provider_card("Codex / MCP clients", "Use this config shape for clients that accept remote MCP HTTP servers with headers.", conn.codex_config_json)}
				${this.render_provider_card("Authorization header", "Useful for MCP Inspector or clients with a custom header field.", conn.bearer_header)}
				${this.render_chatgpt_developer_card(conn.chatgpt_developer_mode || {})}
			</div>
		`);

		this.$body.find("[data-copy-index]").on("click", (event) => {
			const index = Number($(event.currentTarget).attr("data-copy-index"));
			const value = this.copy_values[index] || "";
			this.copy_to_clipboard(value);
		});
	}

	render_provider_card(title, description, code) {
		const copy_index = this.copy_values.push(code || "") - 1;
		const escaped_code = frappe.utils.escape_html(code || "");
		return `
			<div class="lj-mcp-card">
				<h3>${frappe.utils.escape_html(title)}</h3>
				<p class="lj-mcp-muted">${frappe.utils.escape_html(description)}</p>
				<div class="lj-mcp-code-wrap">
					<div class="lj-mcp-code-head">
						<div class="lj-mcp-code-title">${__("Copy configuration")}</div>
						<button class="btn btn-xs btn-default" data-copy-index="${copy_index}">${__("Copy")}</button>
					</div>
					<div class="lj-mcp-code">${escaped_code}</div>
				</div>
			</div>
		`;
	}

	render_chatgpt_developer_card(config) {
		const body = [
			`Name: ${config.name || "Loopjet Frappe"}`,
			`Description: ${config.description || ""}`,
			`MCP server URL: ${config.mcp_server_url || ""}`,
			"",
			config.note || "",
		].join("\n");
		return this.render_provider_card(
			"ChatGPT developer-mode app",
			"Use this in ChatGPT Settings → Plugins after enabling Developer mode.",
			body
		);
	}

	copy_to_clipboard(value) {
		if (navigator.clipboard && navigator.clipboard.writeText) {
			navigator.clipboard.writeText(value);
		} else {
			const $temp = $("<textarea>");
			$("body").append($temp);
			$temp.val(value).select();
			document.execCommand("copy");
			$temp.remove();
		}
		frappe.show_alert({ message: __("Copied."), indicator: "green" });
	}
}
