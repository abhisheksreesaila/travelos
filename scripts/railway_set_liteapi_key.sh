#!/usr/bin/env bash
# Put the live LiteAPI key on Railway's web service (F-267), read from the private file, never printed.
# Run ONLY after the founder says "deploy" (docs/ship/live-prices.md). It skips the automatic deploy; deploy with `railway up --service web --detach`.
set -euo pipefail
RW="${RAILWAY:-railway}"
FILE="${HOME}/.config/gitaway/liteapi-live.env"
[ -r "$FILE" ] || { echo "no $FILE"; exit 1; }
"$RW" status | grep -q "Project: *gitaway" || { echo "railway is not linked to the gitaway project; run 'railway status'"; exit 1; }
KEY="$(sed -n 's/^LITEAPI_KEY=//p' "$FILE" | tr -d '\r\n')"
case "$KEY" in sand_*|"") echo "the file does not hold a live key"; exit 1;; esac
printf '%s' "$KEY" | "$RW" variables --service web --set-from-stdin LITEAPI_KEY --skip-deploys >/dev/null
unset KEY
echo "LITEAPI_KEY on Railway is now: $("$RW" variables --service web --kv | sed -n 's/^LITEAPI_KEY=\(sand_\)\{0,1\}.*/\1/p' | sed 's/^$/live/;s/^sand_$/sandbox/')"
