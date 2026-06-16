#!/bin/sh
# HouseholdBudget — month-end digest (cron --no-agent, runs on the 1st for the
# previous month). Telegram HTML: bold headings + <pre> category/scope tables with
# an expandable-blockquote full-category breakdown. The cron delivery path selects
# parse_mode=HTML automatically when HTML tags are present. See `hb digest --help`.
HB="$HOME/.config/hermes/skills/workspaces/household-budget/scripts/hb"
exec python3 "$HB" digest month-end --format html
