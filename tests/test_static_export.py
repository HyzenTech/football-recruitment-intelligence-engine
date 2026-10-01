"""Publication boundaries for the separate presentation exporter."""

import runpy
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]


@pytest.fixture
def exporter():
    return runpy.run_path(str(REPOSITORY / "scripts/export_demo_data.py"))


def test_existing_export_is_never_overwritten(exporter, tmp_path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        exporter["export_snapshot"](tmp_path, tmp_path / "manifest.json", tmp_path)
    assert sentinel.read_text() == "keep"


def test_tracked_demo_destination_is_rejected(exporter, tmp_path):
    destination = REPOSITORY / "demo/data/should-not-be-created"
    with pytest.raises(ValueError, match="ignored outputs"):
        exporter["export_snapshot"](tmp_path, tmp_path / "manifest.json", destination)
    assert not destination.exists()


@pytest.mark.parametrize("full_cohort", [False, True])
def test_unverified_cohort_or_different_baseline_is_rejected(
    exporter, monkeypatch, tmp_path, full_cohort
):
    export = exporter["export_snapshot"]
    monkeypatch.setitem(export.__globals__, "load_settings", lambda _: object())
    monkeypatch.setitem(
        export.__globals__,
        "load_profiles",
        lambda *_: ([], None, {"full_cohort": full_cohort, "profile_manifest_sha256": "0" * 64}),
    )
    message = "frozen V1 baseline" if full_cohort else "full frozen cohort"
    with pytest.raises(ValueError, match=message):
        export(REPOSITORY / "config", tmp_path / "manifest.json", tmp_path / "new-export")
    assert not (tmp_path / "new-export").exists()


def test_changed_configuration_is_rejected(exporter, monkeypatch, tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "cohorts.toml").write_text("changed = true")
    export = exporter["export_snapshot"]
    monkeypatch.setitem(export.__globals__, "load_settings", lambda _: object())
    monkeypatch.setitem(
        export.__globals__, "load_profiles", lambda *_: ([], None, {"full_cohort": True})
    )
    with pytest.raises(ValueError, match="configuration differs"):
        export(config, tmp_path / "manifest.json", tmp_path / "new-export")
    assert not (tmp_path / "new-export").exists()


def test_nonfinite_statistics_cannot_be_serialized(exporter):
    with pytest.raises(ValueError):
        exporter["encode"]({"value": float("nan")})
