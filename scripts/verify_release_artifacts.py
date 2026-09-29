"""Validate the checked v0.1 publication artifacts without network access."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from ecodeling import __version__
from ecodeling.config.schema import ModelConfig
from ecodeling.reporting import ReplayBundleV1

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "publication" / "v0.1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Fail when a release file, digest, version, or replay contract has drifted."""
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
    if manifest["release"] != __version__:
        raise SystemExit(
            f"release manifest {manifest['release']} does not match package {__version__}"
        )
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        if not path.is_file():
            raise SystemExit(f"missing release artifact: {path.relative_to(ROOT)}")
        if _sha256(path) != item["sha256"]:
            raise SystemExit(f"release artifact digest drifted: {path.relative_to(ROOT)}")

    fixture = ModelConfig.model_validate_json(
        (ROOT / "tests" / "fixtures" / "phase10_report_config.json").read_text()
    )
    published_config = ModelConfig.model_validate_json(
        (RELEASE / "canonical-config.json").read_text()
    )
    expected_config = ModelConfig.model_validate(
        fixture.model_dump(mode="python") | {"scenario_id": "canonical-replay-v1"}
    )
    if published_config != expected_config:
        raise SystemExit("versioned canonical configuration drifted from its analytical fixture")

    replay_path = ROOT / "web" / "replay" / "canonical-v1.json.gz"
    replay = ReplayBundleV1.model_validate_json(gzip.decompress(replay_path.read_bytes()))
    if replay.manifest.model_version != __version__:
        raise SystemExit("canonical replay model version does not match the release")
    if replay.manifest.scenario_id != "canonical-replay-v1":
        raise SystemExit("canonical replay scenario identity drifted")
    if not replay.scenario_pairing.shared_initialization:
        raise SystemExit("canonical pair no longer shares initialization")
    if not replay.scenario_pairing.shared_shock_path:
        raise SystemExit("canonical pair no longer shares its shock path")

    print(f"v{__version__} release artifacts verified ({len(manifest['artifacts'])} files)")


if __name__ == "__main__":
    main()
