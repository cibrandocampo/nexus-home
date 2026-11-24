#!/bin/sh
# Updates the controller over the network, from a computer on the same LAN.
#
#   tools/update.sh <controller-ip> [version]
#
# Builds the firmware (tests included), turns it into an .ota file, serves it for a moment from this
# computer and asks the controller to download and install it. The access token is read from
# $GARAGE_TOKEN, or asked for. Refused by the controller while the door is moving.
set -e
cd "$(dirname "$0")/.."
board=${1:?usage: tools/update.sh <controller-ip> [version]}
port=${OTA_PORT:-8070}

tools/build.sh ${2:+"$2"}
version=${2:-$(sed -n 's/^#define FW_VERSION "\(.*\)"/\1/p' firmware/config.h)}
python3 -I tools/make_ota.py "dist/garage-$version.bin" "dist/garage-$version.ota"

# Address of this computer as seen from the controller's network.
me=$(ip route get "$board" | sed -n 's/.* src \([0-9.]*\).*/\1/p')
[ -n "$me" ] || { echo "cannot find this computer's address towards $board" >&2; exit 1; }

if [ -z "$GARAGE_TOKEN" ]; then
  printf "Access token: "
  stty -echo; read -r GARAGE_TOKEN; stty echo; echo
fi

from=$(curl -fsS -m 5 "http://$board/api/v1/info" | sed -n 's/.*"sw_version":"\([^"]*\)".*/\1/p')
echo "controller at $board runs $from, installing $version"

python3 -m http.server "$port" --bind "$me" --directory dist >/dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT INT TERM
sleep 1

# The board can install the update even when this script loses track of it (the request timed out, the
# board took longer to come back): before reporting a failure, ask which version it runs.
fail() {
  echo "$1" >&2
  now=$(curl -s -m 5 "http://$board/api/v1/info" | sed -n 's/.*"sw_version":"\([^"]*\)".*/\1/p')
  [ "$now" = "$version" ] && [ "$from" != "$version" ] && { echo "but the controller now runs $version: done"; exit 0; }
  echo "the controller runs '${now:-not answering}'" >&2
  exit 1
}

url="http://$me:$port/garage-$version.ota"
# The controller also checks the URL before downloading (a URL that does not answer would hang its WiFi
# module), but a firewall on this computer would make every attempt fail: check from here first.
curl -fsS -I -m 5 -o /dev/null "$url" || { echo "the local server does not answer at $url" >&2; exit 1; }
echo "asking it to download $url"
echo "(if it says server_unreachable, allow incoming TCP port $port on this computer's firewall)"
answer=$(curl -sS -m 150 -X POST -H "Authorization: Bearer $GARAGE_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"url\":\"$url\"}" -w '\n%{http_code}' "http://$board/api/v1/firmware") || true
code=$(echo "$answer" | tail -n 1)
echo "$answer" | sed '$d'
if [ "$code" = 000 ]; then  # no answer: the board may still have downloaded it and be flashing
  sleep 90
  fail "no answer to the update request"
fi
[ "$code" = 200 ] || { echo "update not started (HTTP $code)" >&2; exit 1; }

echo "downloaded and verified; flashing and restarting (about a minute)..."
# Done when the controller answers again after a restart (uptime back near zero) with the new version.
i=0
while [ $i -lt 90 ]; do
  sleep 2
  up=$(curl -s -m 2 "http://$board/api/v1/state" | sed -n 's/.*"uptime_s":\([0-9]*\).*/\1/p')
  if [ -n "$up" ] && [ "$up" -lt $((i * 2 + 5)) ]; then
    now=$(curl -s -m 2 "http://$board/api/v1/info" | sed -n 's/.*"sw_version":"\([^"]*\)".*/\1/p')
    if [ "$now" = "$version" ]; then echo "done: $from -> $version"; exit 0; fi
    fail "restarted but runs '$now', not $version"
  fi
  i=$((i + 1))
done
fail "the controller is not back with $version after 3 minutes; check it (a USB upload recovers it)"
