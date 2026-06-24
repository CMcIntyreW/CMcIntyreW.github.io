#!/usr/bin/env bash
# Check that the RSVP Flask app is set up correctly on Railway.
#
# Usage:
#   ./check_railway.sh                          # use RSVP_BACKEND_URL or railway domain
#   ./check_railway.sh https://your-app.up.railway.app
#
# Optional env:
#   RSVP_BACKEND_URL  – base URL (no trailing slash); used if no argument given.

BASE="${1:-${RSVP_BACKEND_URL:-}}"

if [ -z "$BASE" ]; then
  if command -v railway >/dev/null 2>&1; then
    echo "No URL given. Trying: railway domain ..."
    BASE=$(railway domain 2>/dev/null || true)
  fi
fi

if [ -z "$BASE" ]; then
  echo "Usage: ./check_railway.sh <BASE_URL>"
  echo "   or: RSVP_BACKEND_URL=https://your-app.up.railway.app ./check_railway.sh"
  echo "   or: run from rsvp_flask with 'railway link' set, then run ./check_railway.sh"
  exit 1
fi

# Strip trailing slash
BASE="${BASE%/}"

PASS=0
FAIL=0

check() {
  local name="$1"
  local method="${2:-GET}"
  local path="$3"
  local expected_code="${4:-200}"
  local extra_args=("${@:5}")

  local url="$BASE$path"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "${extra_args[@]}" "$url" 2>/dev/null || echo "000")

  if [ "$code" = "$expected_code" ]; then
    echo "  OK   $name (HTTP $code)"
    ((PASS++)) || true
    return 0
  else
    echo "  FAIL $name (expected HTTP $expected_code, got $code)"
    ((FAIL++)) || true
    return 1
  fi
}

echo "Checking RSVP backend at: $BASE"
echo ""

# Run all checks (don't exit on first failure)
check "GET / (RSVP form)" GET "/" 200
check "GET /thank-you" GET "/thank-you" 200
check "GET /data (export page)" GET "/data" 200
check "GET /download-csv" GET "/download-csv" 200
check "POST /submit (redirect to thank-you)" POST "/submit" 302 "-d" "name=CheckTest&email=check@test&attending=yes"

echo ""
echo "--- Summary ---"
echo "Passed: $PASS  Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo "All checks passed. Setup looks correct."
