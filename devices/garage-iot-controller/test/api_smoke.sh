#!/bin/sh
# Read-only API check against a running controller. Usage: ./api_smoke.sh <ip-or-host> [token]
# Pass LIGHT=1 to also switch the light on for 5 s. It never moves the door.
set -e
base="http://${1:?usage: $0 <ip-or-host> [token]}/api/v1"
auth="Authorization: Bearer ${2:-}"

echo "== info";  curl -fsS "$base/info";  echo
echo "== state"; curl -fsS "$base/state"; echo
echo "== unknown command (expects 404; 401 if the device has a token and none was given)"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST -H "$auth" "$base/door/nope"
echo "== cross-origin POST (expects 403)"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST -H "Origin: http://evil.example" "$base/light/off"
if [ -n "$LIGHT" ]; then
  echo "== light on for 5 s"
  curl -fsS -X POST -H "$auth" "$base/light/on?duration=5"; echo
fi
