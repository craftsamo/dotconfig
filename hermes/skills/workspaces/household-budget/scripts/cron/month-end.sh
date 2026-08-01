#!/bin/sh
# HouseholdBudget — month-end digest (cron --no-agent, runs on the 1st for the
# previous month). Compares spending with the month before and reports category,
# scope, largest-expense, project, and current reimbursement context. Telegram rich
# Markdown renders native tables and collapsible details through sendRichMessage.
HB="$HOME/.config/hermes/skills/workspaces/household-budget/scripts/hb"
exec python3 "$HB" digest month-end --format markdown
