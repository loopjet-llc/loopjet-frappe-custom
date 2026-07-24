from loopjet_frappe_custom.inbound_email import migrate_legacy_inbound_issues


def execute() -> None:
	migrate_legacy_inbound_issues()
