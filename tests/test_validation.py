"""Offline end-to-end acceptance, from fabricated provider bytes to usable minutes."""

import json

import pytest
from test_ingestion import configured, fake_fetcher, source_payloads

from football_recruitment.ingestion.pipeline import ingest_cohort
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes
from football_recruitment.validation.pipeline import validate_cohort
from football_recruitment.validation.verification import verify_minutes


def complete_payloads():
    payloads = source_payloads()
    events, lineups = [], []
    for team in (1, 2):
        roster = [
            {
                "player_id": team * 100 + n,
                "player_name": f"Synthetic {team}-{n}",
                "positions": [
                    {
                        "position_id": 14,
                        "position": "Center Midfield",
                        "from": "00:00",
                        "from_period": 1,
                        "to": None,
                        "to_period": None,
                        "start_reason": "Starting XI",
                        "end_reason": "Final Whistle",
                    }
                ],
                "cards": [],
            }
            for n in range(1, 12)
        ]
        lineups.append({"team_id": team, "team_name": f"Synthetic {team}", "lineup": roster})
        events.append(
            {
                "id": f"xi-{team}",
                "index": 1,
                "period": 1,
                "timestamp": "00:00:00.000",
                "minute": 0,
                "second": 0,
                "team": {"id": team, "name": f"Synthetic {team}"},
                "type": {"id": 35, "name": "Starting XI"},
                "tactics": {
                    "formation": 433,
                    "lineup": [
                        {
                            "player": {"id": p["player_id"], "name": p["player_name"]},
                            "position": {"id": 14, "name": "Center Midfield"},
                        }
                        for p in roster
                    ],
                },
            }
        )
        for period in (1, 2):
            for kind, source_id, timestamp in (
                ("Half Start", 18, "00:00:00.000"),
                ("Half End", 34, "00:50:00.000"),
            ):
                events.append(
                    {
                        "id": f"{kind}-{period}-{team}",
                        "index": 1,
                        "period": period,
                        "timestamp": timestamp,
                        "minute": 0,
                        "second": 0,
                        "type": {"id": source_id, "name": kind},
                        "team": {"id": team, "name": f"Synthetic {team}"},
                    }
                )
    events.sort(key=lambda e: (e["period"], e["timestamp"], e["type"]["name"] != "Starting XI"))
    for i, e in enumerate(events, 1):
        e["index"] = i
    payloads["data/events/101.json"] = json_bytes(events)
    payloads["data/lineups/101.json"] = json_bytes(lineups)
    return payloads


def ingested(tmp_path):
    payloads = complete_payloads()
    settings = configured(payloads)
    ing = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    assert ing["status"] == "COMPLETE"
    return settings, tmp_path / ing["manifest_path"]


def test_complete_validation_and_repeat_are_identical(tmp_path):
    settings, path = ingested(tmp_path)
    first = validate_cohort(settings, tmp_path, path)
    second = validate_cohort(settings, tmp_path, path)
    assert first == second
    assert first["appearance_quality"] == {
        "EXCLUDED": 0,
        "NEEDS_REVIEW": 0,
        "VALIDATED": 22,
        "unused_roster": 0,
    }
    assert first["validated_playing_seconds"] == 22 * 6000
    assert first["validated_nominal_minutes"] == 22 * 90
    assert first["issue_counts"] == {}
    manifest_path = tmp_path / first["validation_manifest_path"]
    assert digest(manifest_path.read_bytes()) == first["validation_manifest_sha256"]
    manifest = json.loads(manifest_path.read_bytes())
    for artifact in manifest["artifacts"]:
        content = (manifest_path.parent.parent / artifact["path"]).read_bytes()
        assert digest(content) == artifact["sha256"]
    assert first["network_access"] is False
    verified = verify_minutes(settings, tmp_path, manifest_path)
    assert verified["processed_integrity"] == "VERIFIED"
    assert verified["presence_intervals"] == verified["position_intervals"] == 44


def test_corrupt_input_cannot_publish_processed_output(tmp_path):
    settings, path = ingested(tmp_path)
    manifest = json.loads(path.read_bytes())
    artifact = next(a for a in manifest["canonical_artifacts"] if a["kind"] == "events")
    (path.parent.parent / artifact["path"]).write_bytes(b"{}\n")
    with pytest.raises(IngestionError, match="checksum"):
        validate_cohort(settings, tmp_path, path)
    assert not (tmp_path / "data/processed").exists()


def test_unreliable_boundaries_report_exclusions_instead_of_defaults(tmp_path):
    payloads = complete_payloads()
    events = json.loads(payloads["data/events/101.json"])
    for event in events:
        if event["type"]["name"] == "Half End":
            event["half_end"] = {"early_video_end": True}
    payloads["data/events/101.json"] = json_bytes(events)
    settings = configured(payloads)
    ing = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    result = validate_cohort(settings, tmp_path, tmp_path / ing["manifest_path"])
    assert result["status"] == "COMPLETE_WITH_EXCLUSIONS"
    assert result["appearance_quality"]["NEEDS_REVIEW"] == 22
    assert result["validated_playing_seconds"] == 0


def test_processed_verifier_detects_corruption(tmp_path):
    settings, path = ingested(tmp_path)
    result = validate_cohort(settings, tmp_path, path)
    processed = tmp_path / result["validation_manifest_path"]
    manifest = json.loads(processed.read_bytes())
    artifact = next(a for a in manifest["artifacts"] if a["kind"] == "presence")
    (processed.parent.parent / artifact["path"]).write_bytes(b"{}\n")
    with pytest.raises(IngestionError, match="artifact checksum"):
        verify_minutes(settings, tmp_path, processed)


def test_processed_verifier_rejects_inconsistent_minutes_even_with_new_hashes(tmp_path):
    settings, path = ingested(tmp_path)
    result = validate_cohort(settings, tmp_path, path)
    processed = tmp_path / result["validation_manifest_path"]
    manifest = json.loads(processed.read_bytes())
    artifact = next(a for a in manifest["artifacts"] if a["kind"] == "appearances")
    target = processed.parent.parent / artifact["path"]
    rows = [json.loads(line) for line in target.read_bytes().splitlines()]
    rows[0]["playing_seconds"] += 1
    data = b"".join(json_bytes(row) for row in rows)
    target.write_bytes(data)
    artifact.update(sha256=digest(data), byte_count=len(data))
    content = json_bytes(manifest)
    new_path = processed.with_name(digest(content) + ".json")
    new_path.write_bytes(content)
    with pytest.raises(IngestionError, match="interval totals"):
        verify_minutes(settings, tmp_path, new_path)
