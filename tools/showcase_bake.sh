#!/usr/bin/env bash
# The Cycle 5 showcase bake: a full-length book end to end, plates on Runpod.
#
# Same shape as headline_bake.sh, with two changes that only a long book forces.
#
# 1. THE PRE-WARM MOVED. headline_bake.sh pre-warms before the bake starts, which
#    is fine for Sleepy Hollow: its text steps take 161 s, so four warm workers
#    idle for under three minutes. Treasure Island's text steps take twenty-odd
#    minutes, and pre-warming in front of them would either bill four warm
#    workers through the whole text phase or -- worse -- let them fall past the
#    60 s idle timeout and go cold again, so the bake would pay a second ~490 s
#    cold start exactly when it started rendering. Every render in a bake happens
#    after the prompt gate, so the pre-warm now runs *at* that gate, via
#    run_baseline.py --at-prompt-gate. The billed window is the render block.
#
# 2. TITLE AND AUTHOR ARE PASSED. run_baseline.py defaults them to Usher/Poe, and
#    headline_bake.sh never overrode them -- which is why the published pg-41
#    bundle says "The Fall of the House of Usher" over Sleepy Hollow's text to
#    this day. A showcase artifact cannot carry the wrong book on its cover.
#
#   ./showcase_bake.sh <endpoint-id>
#
# Assumes the endpoint is provisioned and pinned (provision_client_endpoint.py).

set -euo pipefail
ENDPOINT="${1:?usage: showcase_bake.sh <endpoint-id>}"
BOOK_ID="${BOOK_ID:-pg-120}"
GUTENBERG_ID="${GUTENBERG_ID:-120}"
TITLE="${TITLE:-Treasure Island}"
AUTHOR="${AUTHOR:-Stevenson, Robert Louis}"
ERA="${ERA:-1750s Bristol and the Spanish Main}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/runs/$BOOK_ID-runpod"
DROPIN=/home/kb/.config/systemd/user/scriptorium-bakery.service.d
mkdir -p "$OUT"

say() { printf '\n\033[1m=== %s ===\033[0m  %s\n' "$1" "$(date -u +%H:%M:%SZ)"; }

# --- 1. point the bakery at Runpod (free) -----------------------------------
say "1. bakery -> runpod backend"
mkdir -p "$DROPIN"
cat > "$DROPIN/runpod.conf" <<EOF
[Service]
Environment=RENDER_BACKEND=runpod
Environment=RUNPOD_ENDPOINT_ID=$ENDPOINT
Environment=RENDER_CONCURRENCY=4
# Quoted. systemd splits Environment= on whitespace, and the unquoted form set
# RENDER_CARD=NVIDIA, which substring-matches every NVIDIA card and so weakened
# the placement check to useless rather than making it wrong.
Environment="RENDER_CARD=NVIDIA GeForce RTX 4090"
EOF
systemctl --user daemon-reload
systemctl --user restart scriptorium-bakery
sleep 6
tr '\0' '\n' < "/proc/$(systemctl --user show scriptorium-bakery -p MainPID --value)/environ" \
  | grep -E '^RENDER_|^RUNPOD_' | sed 's/^/  /'

# --- 2. clear any earlier copy so this is a real end-to-end run (free) -------
say "2. clear $BOOK_ID"
curl -s -X DELETE "http://localhost:8720/api/admin/books/$BOOK_ID" -m 60 | head -c 200; echo

# --- 3. the bake: text steps free, then pre-warm, then the paid render block -
# Nothing before the prompt gate touches a GPU that bills. The hook is where the
# money starts, and if it fails run_baseline leaves the gate closed rather than
# rendering against a cold fleet -- a worker's first render after a model load
# does not match a warm one, so a cold fleet is a fidelity problem, not just a
# slow one.
say "3. bake $BOOK_ID  (text free; PAID from the prompt gate)"
BAKE_T0=$(date -u +%s)
"$REPO/tools/run_baseline.py" \
    --gutenberg-id "$GUTENBERG_ID" \
    --title "$TITLE" --author "$AUTHOR" --era "$ERA" \
    --style-id oil-painting --density-preset lavish --images-per-scene 1 \
    --at-prompt-gate "$REPO/tools/prewarm.py --endpoint $ENDPOINT --workers 4 --out $OUT/prewarm.json" \
    --out "$OUT/run.json"
BAKE_T1=$(date -u +%s)
echo "  bake wall clock: $((BAKE_T1 - BAKE_T0)) s"

# --- 4. the live-demo measurement -------------------------------------------
say "4. single warm request  [PAID]"
"$REPO/tools/prewarm.py" --endpoint "$ENDPOINT" --workers 1 --size 832 \
    --out "$OUT/warm-demo.json"

# --- 5. tear down by name, immediately --------------------------------------
say "5. teardown"
runpodctl serverless delete "$ENDPOINT" | tail -2
runpodctl serverless list | python3 -c "import json,sys; print(f'  endpoints live: {len(json.load(sys.stdin))}')"

# --- 6. revert the bakery to the committed configuration (free) -------------
say "6. bakery -> local backend"
rm -f "$DROPIN/runpod.conf"; rmdir "$DROPIN" 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user restart scriptorium-bakery
sleep 6

# --- 7. attribute the time, and find any cold-load plates (free) ------------
say "7. timing"
"$REPO/tools/bake_timing.py" --book-id "$BOOK_ID" --run-log "$OUT/run.json" \
    --out "$OUT/timing.json" --markdown || true

say "8. cold-load plates"
"$REPO/tools/cold_load_plates.py" --book-id "$BOOK_ID" || true

say "done -- balance still needs to settle before any cost is recorded"
echo "  next: ./tools/settle_balance.py --out $OUT/balance-settle.log"
