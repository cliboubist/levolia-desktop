#!/usr/bin/env bash
# Print the one-click pairing link for a client.
#
#   bash scripts/levolia/pairing-link.sh https://client.levolia.ai "$HERMES_DASHBOARD_SESSION_TOKEN"
#
# The client installs Levolia Desktop, clicks the link, confirms the server
# name in the dialog, and is connected. Send the link by a private channel:
# it carries the access token.
set -euo pipefail

url="${1:?server url, e.g. https://client.levolia.ai}"
token="${2:?access token (HERMES_DASHBOARD_SESSION_TOKEN on the server)}"

enc() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

echo "levolia://connect?url=$(enc "$url")&token=$(enc "$token")"
