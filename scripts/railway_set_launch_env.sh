#!/usr/bin/env bash
# The launch settings on Railway's web service, read from the private files and never printed (docs/ship/live-prices.md):
#   GITAWAY_PUBLIC_URL (the card form returns there), the Resend SMTP settings for booking emails (F-285), and the Google Maps browser key (F-284).
# It skips the automatic deploy; deploy with `railway up --service web --detach`.
set -euo pipefail
RW="${RAILWAY:-railway}"
"$RW" status | grep -q "Project: *gitaway" || { echo "railway is not linked to the gitaway project; run 'railway status'"; exit 1; }
set_plain() { printf '%s' "$2" | "$RW" variables --service web --set-from-stdin "$1" --skip-deploys >/dev/null; echo "set $1"; }
from_file() {      # name, file, variable in the file
  local v; v="$(sed -n "s/^$3=//p" "$2" | tr -d '\r\n')"
  [ -n "$v" ] || { echo "no $3 in $2"; exit 1; }
  printf '%s' "$v" | "$RW" variables --service web --set-from-stdin "$1" --skip-deploys >/dev/null; unset v; echo "set $1 (from $2, not shown)"
}
set_plain GITAWAY_PUBLIC_URL "https://gitaway.me"
RESEND="${HOME}/.config/gitaway/resend.env"; GMAPS="${HOME}/.config/gitaway/google-maps.env"
[ -r "$RESEND" ] || { echo "no $RESEND"; exit 1; }
[ -r "$GMAPS" ] || { echo "no $GMAPS"; exit 1; }
set_plain SMTP_HOST "smtp.resend.com"
set_plain SMTP_PORT "465"
set_plain SMTP_SSL "true"
set_plain SMTP_USER "resend"
set_plain SMTP_MAIL_FROM "GitAway <trips@gitaway.me>"
from_file SMTP_PASSWORD "$RESEND" RESEND_API_KEY
from_file GOOGLE_MAPS_API_KEY "$GMAPS" GOOGLE_MAPS_API_KEY
echo "done; names on Railway now:"; "$RW" variables --service web --kv | cut -d= -f1 | grep -E '^(GITAWAY_PUBLIC_URL|SMTP_|GOOGLE_MAPS_API_KEY|LITEAPI_KEY)$' | sort
