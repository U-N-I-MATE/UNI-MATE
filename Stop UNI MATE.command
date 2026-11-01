#!/bin/bash
# Double-click in Finder to stop UNI MATE.
cd "$(dirname "$0")" || exit 1
bash "bin/unimate-stop.sh"
echo ""
echo "You can close this window."
