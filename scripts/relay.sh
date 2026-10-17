#!/usr/bin/env bash
# Keeps the collection running every 20 minutes during racing hours.
# GitHub delays or drops scheduled runs at busy times (on 2026-10-17 none of the
# runs due between 09:07 and 10:47 UTC started), whereas a dispatched run starts
# at once. So each collection waits for the next slot and dispatches the next
# one; the cron schedule of collect.yml only starts or restarts the chain.
#
#   scripts/relay.sh             # needs gh, GH_TOKEN, GH_REPO, REF_NAME, RUN_ID
#   DRY_RUN=1 NOW=<epoch> scripts/relay.sh   # print the decision only
set -euo pipefail

SLOT_MINUTES=(7 27 47)   # same minutes as the cron of collect.yml
FIRST_HOUR=9             # UTC, same window as the cron
LAST_HOUR=22

now=${NOW:-$(date -u +%s)}
hour_start=$(( now / 3600 * 3600 ))
target=""
for offset in 0 3600; do
  for minute in "${SLOT_MINUTES[@]}"; do
    slot=$(( hour_start + offset + minute * 60 ))
    if (( slot > now )); then target=$slot; break 2; fi
  done
done

hour=$(( target / 3600 % 24 ))
label=$(printf "%02d:%02d UTC" "$hour" $(( target / 60 % 60 )))
if (( hour < FIRST_HOUR || hour > LAST_HOUR )); then
  echo "Prochain créneau $label hors de la plage des courses : fin du relais."
  exit 0
fi
wait=$(( target - now ))
echo "Prochaine collecte à $label (dans ${wait} s)."
if [ -n "${DRY_RUN:-}" ]; then exit 0; fi
sleep "$wait"

# Another collection already queued or running (cron, manual run, republish)
# carries the chain on: dispatching one more would only duplicate it.
others=$(gh run list --workflow collect.yml --limit 20 --json databaseId,status \
  --jq "[.[] | select(.databaseId != $RUN_ID and .status != \"completed\")] | length")
if (( others > 0 )); then
  echo "Une autre collecte est déjà en file ou en cours : pas de relance."
  exit 0
fi
gh workflow run collect.yml --ref "$REF_NAME" -f relay=true
echo "Collecte suivante lancée."
