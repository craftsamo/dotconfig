#!/bin/sh
# HouseholdBudget — weekly digest (cron --no-agent). Compares the previous
# complete Monday-Sunday period with the week before, then adds current open
# reimbursements and review backlog. Telegram rich Markdown renders native
# tables and collapsible details through sendRichMessage. See `hb digest --help`.
HB="$HOME/.config/hermes/skills/workspaces/household-budget/scripts/hb"
exec python3 "$HB" digest weekly --format markdown
