#!/bin/sh
# HouseholdBudget — weekly digest (cron --no-agent). Telegram HTML: bold headings,
# <pre> tables (by-counterparty), and an open-reimbursements list inside an
# expandable blockquote, plus needs-review counts. The cron delivery path
# (tools/send_message_tool._send_telegram) auto-selects parse_mode=HTML when HTML
# tags are present, so this renders natively. See `hb digest --help`.
HB="$HOME/.config/hermes/skills/workspaces/household-budget/scripts/hb"
exec python3 "$HB" digest weekly --format html
