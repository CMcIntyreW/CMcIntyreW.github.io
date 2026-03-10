#!/usr/bin/env bash
# Run RSVP backend checks. Pass optional BASE_URL as first argument.
# Usage: ./check_rsvp.sh [https://your-app.up.railway.app]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/rsvp_flask"
exec bash check_railway.sh "$@"
