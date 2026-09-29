#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/cv/web/static/ecodeling" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
destination="$1"

cd "$repo_root"
npm run build:web
mkdir -p "$destination"
cp web/public/dist/ecodeling-experience.js "$destination/ecodeling-experience.js"
cp web/public/dist/ecodeling-experience.css "$destination/ecodeling-experience.css"
cp web/replay/canonical-v1.json.gz "$destination/canonical-v1.json.gz"

cd "$destination"
sha256sum \
  ecodeling-experience.js \
  ecodeling-experience.css \
  canonical-v1.json.gz > SHA256SUMS

echo "Exported the static Ecodeling bundle to $destination"
