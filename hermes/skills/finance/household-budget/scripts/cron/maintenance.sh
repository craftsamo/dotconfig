#!/bin/sh
# HouseholdBudget — daily maintenance (cron --no-agent watchdog).
# Silent on success (empty stdout); prints an alert to stdout only on failure,
# which the cron job then delivers. Apply migrations, refresh FX, back up,
# refresh the mirror, validate.
HB="$HOME/.config/hermes/skills/finance/household-budget/scripts/hb"
fail=""
python3 "$HB" migrate         >/dev/null 2>&1 || fail="$fail migrate"
python3 "$HB" fx-refresh      >/dev/null 2>&1 || fail="$fail fx-refresh"
python3 "$HB" backup --keep 14 >/dev/null 2>&1 || fail="$fail backup"
python3 "$HB" export          >/dev/null 2>&1 || fail="$fail export"
verr=$(python3 "$HB" validate 2>&1) || fail="$fail validate"
if [ -n "$fail" ]; then
  printf '⚠️ HouseholdBudget maintenance issue(s):%s\n\n%s\n' "$fail" "$verr"
fi
exit 0
