"""Canonical production replay regression and shared-contract fixture."""

import gzip
import json
from pathlib import Path

from ecodeling.config.schema import ModelConfig
from ecodeling.economy import run_endogenous_indexation_comparison
from ecodeling.reporting import (
    ReplayBundleV1,
    export_replay_v1,
    load_config,
    serialize_replay_v1,
)


def test_canonical_replay_v1_fixture_matches_export() -> None:
    source = load_config(Path("tests/fixtures/phase10_report_config.json"))
    config = ModelConfig.model_validate(
        source.model_dump(mode="python") | {"scenario_id": "canonical-replay-v1"}
    )
    artifact = serialize_replay_v1(
        export_replay_v1(
            run_endogenous_indexation_comparison(config),
            git_commit=json.loads(Path("publication/v0.1/manifest.json").read_text())[
                "model_source_commit"
            ],
        )
    )
    fixture = Path("web/replay/canonical-v1.json.gz").read_bytes()
    metadata = json.loads(Path("web/replay/canonical-v1.metadata.json").read_text())
    schema = json.loads(Path("web/replay/replay-v1.schema.json").read_text())

    assert fixture == artifact.gzip_bytes
    assert gzip.decompress(fixture) == artifact.canonical_bytes
    assert metadata == {
        "schema_version": 1,
        "sha256_uncompressed": artifact.sha256,
        "uncompressed_bytes": len(artifact.canonical_bytes),
        "compressed_bytes": len(artifact.gzip_bytes),
        "content_encoding": "gzip",
        "content_type": "application/json",
    }
    assert schema == ReplayBundleV1.model_json_schema()
