"""Regenerate the canonical compressed production replay-v1 fixture."""

import json
from pathlib import Path

from ecodeling.config.schema import ModelConfig
from ecodeling.economy import run_endogenous_indexation_comparison
from ecodeling.reporting import ReplayBundleV1, export_replay_v1, load_config, serialize_replay_v1

RELEASE_MANIFEST = Path("publication/v0.1/manifest.json")
CONFIG = Path("tests/fixtures/phase10_report_config.json")
OUTPUT = Path("web/replay/canonical-v1.json.gz")
METADATA = Path("web/replay/canonical-v1.metadata.json")
SCHEMA = Path("web/replay/replay-v1.schema.json")


def main() -> None:
    """Run the declared paired model and write deterministic publication artifacts."""
    source = load_config(CONFIG)
    config = ModelConfig.model_validate(
        source.model_dump(mode="python") | {"scenario_id": "canonical-replay-v1"}
    )
    bundle = export_replay_v1(
        run_endogenous_indexation_comparison(config),
        git_commit=json.loads(RELEASE_MANIFEST.read_text())["model_source_commit"],
    )
    artifact = serialize_replay_v1(bundle)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(artifact.gzip_bytes)
    SCHEMA.write_text(
        json.dumps(ReplayBundleV1.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    METADATA.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sha256_uncompressed": artifact.sha256,
                "uncompressed_bytes": len(artifact.canonical_bytes),
                "compressed_bytes": len(artifact.gzip_bytes),
                "content_encoding": "gzip",
                "content_type": "application/json",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
