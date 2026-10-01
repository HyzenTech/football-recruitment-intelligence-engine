"""Synthetic source payloads exercise real storage, mapping and CLI-stage behavior."""

import copy
import json
import urllib.error
from pathlib import Path

import pytest

from football_recruitment.config import DatasetSettings, load_settings
from football_recruitment.ingestion.pipeline import ingest_cohort
from football_recruitment.ingestion.storage import (
    IngestionError,
    SnapshotStore,
    cohort_lock,
    digest,
    immutable_write,
    json_bytes,
)
from football_recruitment.ingestion.verification import verify_manifest
from football_recruitment.providers.statsbomb import (
    StatsBombOpenDataProvider,
    lineup_point,
    map_card,
    map_event,
    map_position,
    timestamp_seconds,
)

ROOT = Path(__file__).resolve().parents[1]


def source_payloads():
    """Fabricated match; never a sample copied from provider data."""
    catalog = [
        {
            "competition_id": 37,
            "season_id": 281,
            "competition_name": "FA Women's Super League",
            "season_name": "2023/2024",
            "country_name": "England",
            "competition_gender": "female",
            "competition_youth": False,
            "competition_international": False,
        }
    ]
    matches = [
        {
            "match_id": 101,
            "competition": {"competition_id": 37},
            "season": {"season_id": 281},
            "match_date": "2024-01-01",
            "home_score": 1,
            "away_score": 0,
            "home_team": {"home_team_id": 1, "home_team_name": "Synthetic A"},
            "away_team": {"away_team_id": 2, "away_team_name": "Synthetic B"},
            "competition_stage": {"name": "Regular Season"},
            "metadata": {"data_version": "1.1.0"},
        }
    ]
    events = [
        {
            "id": "synthetic-event-1",
            "index": 1,
            "period": 1,
            "timestamp": "00:00:00.000",
            "minute": 0,
            "second": 0,
            "type": {"id": 35, "name": "Starting XI"},
            "team": {"id": 1, "name": "Synthetic A"},
            "tactics": {
                "formation": 343,
                "lineup": [
                    {
                        "player": {"id": 100, "name": "Synthetic A1"},
                        "position": {"id": 1, "name": "Goalkeeper"},
                        "jersey_number": 1,
                    }
                ],
            },
        },
        {
            "id": "synthetic-event-2",
            "index": 2,
            "period": 2,
            "timestamp": "00:01:00.250",
            "minute": 46,
            "second": 0,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 1, "name": "Synthetic A"},
            "player": {"id": 100, "name": "Synthetic A1"},
            "location": [60.0, 40.0],
            "pass": {
                "end_location": [102.0, 40.0],
                "length": 42.0,
                "assisted_shot_id": "synthetic-event-3",
                "shot_assist": True,
                "switch": True,
            },
            "future_attribute": {"keep": "untouched"},
        },
        {
            "id": "synthetic-event-3",
            "index": 3,
            "period": 2,
            "timestamp": "00:01:01.000",
            "minute": 46,
            "second": 1,
            "type": {"id": 16, "name": "Shot"},
            "team": {"id": 1, "name": "Synthetic A"},
            "player": {"id": 100, "name": "Synthetic A1"},
            "location": [102.0, 40.0],
            "shot": {
                "outcome": {"id": 97, "name": "Goal"},
                "statsbomb_xg": 0.2,
                "end_location": [120.0, 40.5, 0.8],
            },
        },
    ]
    lineups = [
        {
            "team_id": t,
            "team_name": f"Synthetic {t}",
            "lineup": [
                {
                    "player_id": 100 if t == 1 else 200,
                    "player_name": f"Synthetic {t}1",
                    "jersey_number": 1,
                    "country": {"id": 1, "name": "Synthetic Country"},
                    "positions": [
                        {
                            "position_id": 1,
                            "position": "Goalkeeper",
                            "from": "45:00",
                            "to": "45:00",
                            "from_period": 2,
                            "to_period": 2,
                            "start_reason": "Tactical Shift",
                            "end_reason": "Tactical Shift",
                        }
                    ],
                    "cards": [
                        {
                            "time": "70:15",
                            "period": 2,
                            "card_type": "Yellow Card",
                            "reason": "Foul Committed",
                        }
                    ],
                }
            ],
        }
        for t in [1, 2]
    ]
    return {
        "data/competitions.json": json_bytes(catalog),
        "data/matches/37/281.json": json_bytes(matches),
        "data/events/101.json": json_bytes(events),
        "data/lineups/101.json": json_bytes(lineups),
    }


def configured(payloads):
    original = load_settings(ROOT / "config")
    dataset = DatasetSettings.model_validate(
        original.dataset.model_dump()
        | {
            "catalog_sha256": digest(payloads["data/competitions.json"]),
            "matches_sha256": digest(payloads["data/matches/37/281.json"]),
            "expected_match_count": 1,
            "expected_team_count": 2,
        }
    )
    return original.model_copy(update={"dataset": dataset})


def fake_fetcher(payloads, calls):
    def fetch(url, timeout, max_bytes):
        path = "data/" + url.split("/data/", 1)[1]
        calls.append(path)
        return payloads[path]

    return fetch


def store_at(tmp_path, **options):
    data = load_settings(ROOT / "config").dataset
    return SnapshotStore(
        tmp_path, data.revision, str(data.data_license_url), request_interval=0, **options
    )


def test_full_synthetic_ingestion_and_offline_rerun_are_identical(tmp_path):
    payloads = source_payloads()
    calls = []
    settings = configured(payloads)
    first = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, calls))
    assert first["status"] == "COMPLETE" and first["event_count"] == 3
    assert first["downloads"] == 4 and len(calls) == 4
    assert first["quality_flags"]["ZERO_DURATION_POSITION_OBSERVATION"] == 2
    assert first["quality_flags"]["UNREVIEWED_SOURCE_FIELDS"] == 1
    second = ingest_cohort(settings, tmp_path, offline=True)
    assert second["manifest_sha256"] == first["manifest_sha256"]
    assert second["downloads"] == 0 and second["cache_hits"] == 4
    assert second["canonical_quality"] == "UNVALIDATED"
    manifest = json.loads((tmp_path / first["manifest_path"]).read_text())
    canonical = (tmp_path / first["manifest_path"]).parent.parent
    for artifact in manifest["canonical_artifacts"]:
        assert digest((canonical / artifact["path"]).read_bytes()) == artifact["sha256"]
    verified = verify_manifest(settings, tmp_path, tmp_path / first["manifest_path"])
    assert verified["artifact_integrity"] == "VERIFIED" and verified["event_count"] == 3
    assert verified["source_files"] == verified["canonical_partitions"] == 4


def test_corrupt_verified_raw_cache_fails_and_never_claims_complete(tmp_path):
    payloads = source_payloads()
    settings = configured(payloads)
    first = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    assert first["status"] == "COMPLETE"
    raw = tmp_path / settings.dataset.paths.raw / "statsbomb" / settings.dataset.revision
    (raw / "data/events/101.json").write_bytes(b"[]")
    failed = ingest_cohort(settings, tmp_path, offline=True)
    assert failed["status"] == "FAILED"
    assert "manifest_path" not in failed and failed["downloads"] == 0
    assert "integrity mismatch" in failed["errors"][0]["error"]
    with pytest.raises(IngestionError, match="Raw source integrity"):
        verify_manifest(settings, tmp_path, tmp_path / first["manifest_path"])


def test_independent_verifier_rejects_modified_canonical_artifact(tmp_path):
    payloads = source_payloads()
    settings = configured(payloads)
    report = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    manifest_path = tmp_path / report["manifest_path"]
    manifest = json.loads(manifest_path.read_bytes())
    event = next(a for a in manifest["canonical_artifacts"] if a["kind"] == "events")
    (manifest_path.parent.parent / event["path"]).write_bytes(b"{}\n")
    with pytest.raises(IngestionError, match="Canonical artifact checksum"):
        verify_manifest(settings, tmp_path, manifest_path)


def test_independent_verifier_rejects_modified_manifest(tmp_path):
    payloads = source_payloads()
    settings = configured(payloads)
    report = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    manifest_path = tmp_path / report["manifest_path"]
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    with pytest.raises(IngestionError, match="Manifest filename"):
        verify_manifest(settings, tmp_path, manifest_path)


def test_failed_download_can_resume_without_refetching_good_files(tmp_path):
    payloads = source_payloads()
    settings = configured(payloads)
    calls = []
    broken = payloads | {"data/events/101.json": b"not json"}
    first = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(broken, calls))
    assert first["status"] == "FAILED"
    assert "manifest_path" not in first
    calls.clear()
    resumed = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, calls))
    assert resumed["status"] == "COMPLETE" and resumed["cache_hits"] == 2
    assert "data/competitions.json" not in calls and "data/matches/37/281.json" not in calls


def test_unverified_orphan_is_revalidated_by_download_without_overwrite(tmp_path):
    payloads = source_payloads()
    path = tmp_path / "data/events/101.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(payloads["data/events/101.json"])
    source = store_at(tmp_path, fetcher=fake_fetcher(payloads, []))
    source.read("data/events/101.json")
    assert path.with_suffix(".receipt.json").exists()
    # Missing receipt plus different source bytes cannot silently replace the orphan.
    path.with_suffix(".receipt.json").unlink()
    changed = payloads | {"data/events/101.json": b'[{"changed":true}]'}
    with pytest.raises(IngestionError, match="conflicts"):
        store_at(tmp_path, fetcher=fake_fetcher(changed, [])).read("data/events/101.json")


def test_audited_hash_mismatch_does_not_publish_payload(tmp_path):
    source = store_at(tmp_path, fetcher=lambda *args: b"[{}]")
    with pytest.raises(IngestionError, match="hash mismatch"):
        source.read("data/competitions.json", "a" * 64)
    assert not (tmp_path / "data/competitions.json").exists()


@pytest.mark.parametrize("payload", [b"[]", b"{}", b"[NaN]", b"[1e309]", b'[{"id":1,"id":2}]'])
def test_malformed_empty_or_nonfinite_payloads_are_never_cached(tmp_path, payload):
    with pytest.raises(ValueError):
        store_at(tmp_path, fetcher=lambda *args: payload).read("data/events/101.json")
    assert not (tmp_path / "data/events/101.json").exists()


def test_offline_missing_cache_never_attempts_network(tmp_path):
    calls = []
    with pytest.raises(IngestionError, match="offline"):
        store_at(tmp_path, offline=True, fetcher=fake_fetcher(source_payloads(), calls)).read(
            "data/events/101.json"
        )
    assert calls == []


@pytest.mark.parametrize(
    "path", ["../events/1.json", "data/events/../1.json", "data/events/a.json"]
)
def test_path_traversal_is_rejected_before_fetch(tmp_path, path):
    calls = []
    with pytest.raises(IngestionError, match="source path"):
        store_at(tmp_path, fetcher=fake_fetcher(source_payloads(), calls)).read(path)
    assert calls == []


def test_http_404_is_not_retried_or_written(tmp_path):
    calls = []

    def fetch(url, *args):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "missing", {}, None)

    with pytest.raises(IngestionError, match="HTTP 404"):
        store_at(tmp_path, fetcher=fetch).read("data/events/101.json")
    assert len(calls) == 1


def test_transient_retry_is_bounded_and_can_succeed(tmp_path, monkeypatch):
    monkeypatch.setattr("football_recruitment.ingestion.storage.time.sleep", lambda _: None)
    calls = []

    def fetch(*args):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("synthetic connection reset")
        return b"[{}]"

    source = store_at(tmp_path, fetcher=fetch)
    source.read("data/events/101.json")
    assert len(calls) == 3


def test_transport_failure_stops_after_attempt_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("football_recruitment.ingestion.storage.time.sleep", lambda _: None)
    calls = []

    def fetch(*args):
        calls.append(1)
        raise OSError("synthetic reset")

    with pytest.raises(IngestionError, match="bounded retries"):
        store_at(tmp_path, fetcher=fetch, attempts=2).read("data/events/101.json")
    assert len(calls) == 2


def test_cohort_lock_prevents_competing_runs_and_releases(tmp_path):
    lock = tmp_path / "snapshot.lock"
    with cohort_lock(lock, tmp_path):
        with pytest.raises(IngestionError, match="holds"):
            with cohort_lock(lock, tmp_path):
                pass
    with cohort_lock(lock, tmp_path):
        pass


def test_immutable_artifacts_refuse_different_bytes(tmp_path):
    path = tmp_path / "artifact.json"
    immutable_write(path, b"original", tmp_path)
    with pytest.raises(IngestionError, match="conflicts"):
        immutable_write(path, b"changed", tmp_path)
    assert path.read_bytes() == b"original"


def test_mapping_preserves_orientation_shot_height_and_unknown_fields():
    raw = json.loads(source_payloads()["data/events/101.json"])
    passed = map_event(raw[1], "statsbomb:match:101", "synthetic-snapshot")
    assert passed.start_location.x == 0.5 and passed.start_location.y == 0.5
    assert passed.detail.end_location.x == 0.85
    assert passed.elapsed_seconds == 60.25 and passed.display_minute == 46
    assert passed.detail.outcome == "complete" and passed.detail.switch is True
    assert passed.source_attributes["future_attribute"] == {"keep": "untouched"}
    shot = map_event(raw[2], "statsbomb:match:101", "synthetic-snapshot")
    assert shot.detail.end_location.z_provider_units == 0.8
    assert shot.detail.xg == 0.2


def test_unknown_outcome_is_not_assumed_completed():
    raw = json.loads(source_payloads()["data/events/101.json"])[1]
    raw["pass"]["outcome"] = {"id": 999, "name": "Synthetic Unknown"}
    value = map_event(raw, "statsbomb:match:101", "synthetic-snapshot")
    assert value.detail.outcome == "unknown"
    assert "UNMAPPED_PASS_OUTCOME" in value.quality_flags


def test_tactics_substitution_and_card_semantics_are_canonical():
    raw = json.loads(source_payloads()["data/events/101.json"])[0]
    value = map_event(raw, "statsbomb:match:101", "synthetic-snapshot")
    assert value.tactical_lineup[0].player_id == "statsbomb:player:100"
    assert value.formation == "343"
    sub = copy.deepcopy(raw)
    sub["type"] = {"id": 19, "name": "Substitution"}
    sub["substitution"] = {"replacement": {"id": 200, "name": "Synthetic"}}
    assert (
        map_event(sub, "statsbomb:match:101", "snapshot").replacement_player_id
        == "statsbomb:player:200"
    )
    sub["type"] = {"id": 24, "name": "Bad Behaviour"}
    sub["bad_behaviour"] = {"card": {"id": 67, "name": "Red Card"}}
    assert map_event(sub, "statsbomb:match:101", "snapshot").card.card_type == "Red Card"


def test_lineup_period_clock_does_not_include_halftime_or_resolve_null_ends():
    assert lineup_point("70:15", 2).elapsed_seconds == 1515.0
    raw = json.loads(source_payloads()["data/lineups/101.json"])[0]["lineup"][0]["positions"][0]
    value = map_position(raw)
    assert value.quality_flags == ("ZERO_DURATION_POSITION_OBSERVATION",)
    raw["to"] = None
    raw["to_period"] = None
    assert map_position(raw).end is None


def test_reversed_position_is_preserved_flagged_and_never_fixed():
    raw = {
        "position_id": 14,
        "position": "Synthetic midfield",
        "from": "99:00",
        "to": "65:00",
        "from_period": 2,
        "to_period": 2,
        "start_reason": "Player On",
        "end_reason": "Player Off",
    }
    observed = map_position(raw)
    assert observed.start.elapsed_seconds == 3240.0
    assert observed.end.elapsed_seconds == 1200.0
    assert observed.quality_flags == ("REVERSED_SOURCE_POSITION_INTERVAL",)
    assert observed.source_attributes == raw


def test_inconsistent_card_clock_retains_original_and_marks_unknown_time():
    raw = {"time": "12:00", "period": 2, "card_type": "Yellow Card", "reason": "Bad Behaviour"}
    observed = map_card(raw)
    assert observed.time is None
    assert observed.quality_flags == ("INVALID_SOURCE_CARD_CLOCK",)
    assert observed.source_attributes == raw


@pytest.mark.parametrize("value", ["00:60:00.000", "00:00:60.000", "bad"])
def test_malformed_timestamps_fail(value):
    with pytest.raises(IngestionError):
        timestamp_seconds(value)


def test_provider_rejects_noncohort_matches_before_fetch(tmp_path):
    payloads = source_payloads()
    settings = configured(payloads)
    source = store_at(tmp_path, fetcher=fake_fetcher(payloads, []))
    provider = StatsBombOpenDataProvider(source, settings.dataset)
    with pytest.raises(IngestionError, match="cohort"):
        provider.load_events("football-data:match:101")


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows extended path representation")
def test_windows_resolved_path_prefix_keeps_containment_checks(tmp_path, monkeypatch):
    from football_recruitment.ingestion.storage import within

    root = tmp_path / "root"
    root.mkdir()
    target = root / "child.json"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path != root:
            return Path("\\\\?\\" + str(result))
        return result

    monkeypatch.setattr(Path, "resolve", resolve)
    assert within(root, target) == target
    with pytest.raises(IngestionError, match="escapes"):
        within(root, tmp_path / "outside.json")
