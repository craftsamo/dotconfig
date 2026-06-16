#!/bin/sh
# Cron entry (assistant profile) -> HouseholdBudget skill daily maintenance.
exec "$HOME/.config/hermes/skills/finance/household-budget/scripts/cron/maintenance.sh"
