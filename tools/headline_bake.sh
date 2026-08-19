#!/usr/bin/env bash
# The Cycle 4 headline bake: pg-41 end to end, text steps at home, plates on Runpod.
#
# Scripted rather than typed because every second between the first pre-warm render
# and the teardown is billed at $1.10/hr per warm worker. The expensive window is
# steps 3-6; everything before and after is free.
#
#   ./headline_bake.sh                    # endpoint id resolved by endpoint_id.py
#   OUT=runs/pg-41-rehearsal KEEP_ENDPOINT=1 ./headline_bake.sh
#
# Assumes: the endpoint is already provisioned and pinned (provision_client_endpoint.py),
# the bakery is running on master with ADR-0038, and the pg-41 baseline is backed up.
#
# TWO ENV GUARDS, both added in Cycle 6 when this script was re-run for a stage
# rehearsal and neither default was survivable:
#
#   OUT             Where the artifacts land. The default is the directory holding
#                   the committed evidence for the 325.24 s headline -- run.json,
#                   timing.json, prewarm.json, warm-demo.json. A second run with
#                   the default overwrites all four and the provenance behind the
#                   repo's headline number is simply gone. Override it for
#                   anything that is not the original measurement.
#
#   KEEP_ENDPOINT   Set to 1 to skip step 6, the teardown. The default is to tear
#                   down, because an endpoint left up by accident is the failure
#                   mode that costs money. Set it deliberately when the endpoint
#                   is wanted afterwards -- a rehearsal, or a live demo.

set -euo pipefail
# The id is optional: with no argument, endpoint_id.py resolves the one
# serverless endpoint on the account. Pass one to override.
ENDPOINT="${1:-$(python3 "$(dirname "$0")/endpoint_id.py")}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$REPO/runs/pg-41-runpod}"
case "$OUT" in /*) ;; *) OUT="$REPO/$OUT" ;; esac   # accept a repo-relative OUT
KEEP_ENDPOINT="${KEEP_ENDPOINT:-0}"
DROPIN=/home/kb/.config/systemd/user/scriptorium-bakery.service.d
mkdir -p "$OUT"

say() { printf '\n\033[1m=== %s ===\033[0m  %s\n' "$1" "$(date -u +%H:%M:%SZ)"; }

# --- 1. point the bakery at Runpod (free) -----------------------------------
# A drop-in, not an edit to the tracked env file: the committed deployment stays
# on RENDER_BACKEND=local so nothing production-facing references a torn-down
# endpoint. Reverted in step 7.
say "1. bakery -> runpod backend"
mkdir -p "$DROPIN"
cat > "$DROPIN/runpod.conf" <<EOF
[Service]
Environment=RENDER_BACKEND=runpod
Environment=RUNPOD_ENDPOINT_ID=$ENDPOINT
Environment=RENDER_CONCURRENCY=4
# Quoted, because systemd splits Environment= on whitespace: the unquoted form
# set RENDER_CARD=NVIDIA and silently dropped "GeForce RTX 4090". Harmless in the
# first headline run -- the value only drives a warning, and "NVIDIA" substring-
# matches every NVIDIA card, so the check was weakened to useless rather than
# made wrong -- but it would never have fired if placement had been substituted.
Environment="RENDER_CARD=NVIDIA GeForce RTX 4090"
EOF
systemctl --user daemon-reload
systemctl --user restart scriptorium-bakery
sleep 6
systemctl --user show scriptorium-bakery -p SubState | sed 's/^/  /'
tr '\0' '\n' < "/proc/$(systemctl --user show scriptorium-bakery -p MainPID --value)/environ" \
  | grep -E '^RENDER_|^RUNPOD_' | sed 's/^/  /'

# --- 2. clear the old pg-41 so the bake is a real end-to-end run (free) ------
say "2. clear pg-41 (baseline is backed up at ~/scriptorium-baseline-pg41-20260818)"
curl -s -X DELETE "http://localhost:8720/api/admin/books/pg-41" -m 60 | head -c 200; echo

# --- 3. PAID FROM HERE: pre-warm every worker -------------------------------
say "3. pre-warm 4 workers  [PAID]"
# --straggler-grace: this is a warm-up before a TIMED bake, so warmth is the goal
# and the fleet-depth reading is not. Without it, one 300 s render stall in the
# preamble adds five minutes to a live demo; the abandoned jobs keep running and
# still warm their worker. The step-5 measurement below deliberately has no grace.
"$REPO/tools/prewarm.py" --endpoint "$ENDPOINT" --workers 4 --straggler-grace 60 \
    --out "$OUT/prewarm.json"

# --- 4. the bake ------------------------------------------------------------
say "4. bake pg-41 end to end  [PAID]"
BAKE_T0=$(date -u +%s)
"$REPO/tools/run_baseline.py" --gutenberg-id 41 --out "$OUT/run.json"
BAKE_T1=$(date -u +%s)
echo "  bake wall clock: $((BAKE_T1 - BAKE_T0)) s   (home baseline: 388.63 s)"

# --- 5. the live-demo measurement -------------------------------------------
# One request against a worker that is already warm, which is the configuration a
# stage demo actually runs in.
say "5. single warm request  [PAID]"
"$REPO/tools/prewarm.py" --endpoint "$ENDPOINT" --workers 1 --size 832 \
    --out "$OUT/warm-demo.json"

# --- 6. tear down by name, immediately --------------------------------------
if [ "$KEEP_ENDPOINT" = "1" ]; then
  say "6. teardown SKIPPED (KEEP_ENDPOINT=1)"
  echo "  endpoint $ENDPOINT is still up and still billable while workers are warm."
  echo "  Tear it down with:  runpodctl serverless delete $ENDPOINT"
  runpodctl serverless list | python3 -c "import json,sys; print(f'  endpoints live: {len(json.load(sys.stdin))}')"
else
  say "6. teardown"
  runpodctl serverless delete "$ENDPOINT" | tail -2
  runpodctl serverless list | python3 -c "import json,sys; print(f'  endpoints live: {len(json.load(sys.stdin))}')"
fi

# --- 7. revert the bakery to the committed configuration (free) -------------
say "7. bakery -> local backend"
rm -f "$DROPIN/runpod.conf"; rmdir "$DROPIN" 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user restart scriptorium-bakery
sleep 6
systemctl --user show scriptorium-bakery -p SubState | sed 's/^/  /'

# --- 8. attribute the time (free) -------------------------------------------
say "8. timing"
"$REPO/tools/bake_timing.py" --book-id pg-41 --run-log "$OUT/run.json" \
    --out "$OUT/timing.json" --markdown || true

say "done -- balance still needs to settle before any cost is recorded"
