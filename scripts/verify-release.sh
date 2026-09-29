#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/ecodeling-uv-release-cache}"

uv sync --locked --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run ecodeling --version
replay_before="$(sha256sum \
  web/replay/canonical-v1.json.gz \
  web/replay/canonical-v1.metadata.json \
  web/replay/replay-v1.schema.json)"
uv run python scripts/generate_replay_v1.py
replay_after="$(sha256sum \
  web/replay/canonical-v1.json.gz \
  web/replay/canonical-v1.metadata.json \
  web/replay/replay-v1.schema.json)"
if [[ "$replay_before" != "$replay_after" ]]; then
  echo "canonical replay regeneration changed checked release artifacts" >&2
  exit 1
fi
uv run python scripts/verify_release_artifacts.py
npm ci
npm run typecheck:web
npm run lint:web
npm run format:check
npm test
npm run build:web
npm run test:browser
