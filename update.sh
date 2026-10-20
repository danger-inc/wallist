#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
git pull --ff-only
./install.sh --update
echo "wallist aktualisiert – einmal schließen und neu öffnen."
