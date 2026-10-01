"""Independent processed-file integrity, interval totals and exclusion checks."""

from collections import Counter, defaultdict

from football_recruitment.domain.models import (
    Appearance,
    MatchPeriod,
    PositionInterval,
    PresenceInterval,
    QualityStatus,
)
from football_recruitment.ingestion.storage import IngestionError, digest, strict_json, within
from football_recruitment.preprocessing.minutes import EPSILON, MINUTES_VERSION, NOMINAL_SECONDS
from football_recruitment.providers.statsbomb import MAPPING_VERSION


def verify_minutes(settings, project_root, manifest_path):
    """Verify output artifacts; does not replace event-state calculation tests or source checks."""
    project_root = project_root.resolve()
    dataset = settings.dataset
    root = (
        within(project_root, project_root / dataset.paths.processed)
        / dataset.provider
        / (dataset.revision)
        / f"{dataset.competition_id}-{dataset.season_id}"
        / MINUTES_VERSION
    )
    path = within(root, manifest_path)
    data = path.read_bytes()
    manifest = strict_json(data)
    if path.stem != digest(data) or manifest["validation_version"] != MINUTES_VERSION:
        raise IngestionError("Processed manifest checksum/version mismatch")
    if manifest["revision"] != dataset.revision:
        raise IngestionError("Processed manifest revision mismatch")
    report_path = within(project_root, project_root / manifest["validation_report_path"])
    report_bytes = report_path.read_bytes()
    if digest(report_bytes) != manifest["validation_report_sha256"]:
        raise IngestionError("Validation report checksum mismatch")
    report = strict_json(report_bytes)
    if report["source_manifest_sha256"] != manifest["source_manifest_sha256"]:
        raise IngestionError("Processed source lineage mismatch")
    source_path = (
        within(project_root, project_root / dataset.paths.interim)
        / dataset.provider
        / dataset.revision
        / f"{dataset.competition_id}-{dataset.season_id}"
        / MAPPING_VERSION
        / "manifests"
        / (manifest["source_manifest_sha256"] + ".json")
    )
    source_content = within(project_root, source_path).read_bytes()
    if digest(source_content) != manifest["source_manifest_sha256"]:
        raise IngestionError("Processed upstream manifest checksum mismatch")
    source_manifest = strict_json(source_content)
    partitions = set()
    records = defaultdict(list)
    models = {
        "appearances": Appearance,
        "presence": PresenceInterval,
        "positions": PositionInterval,
        "periods": MatchPeriod,
    }
    for artifact in manifest["artifacts"]:
        kind, key = artifact["kind"], artifact["key"]
        if kind not in models or (kind, key) in partitions:
            raise IngestionError("Invalid or duplicate processed partition")
        partitions.add((kind, key))
        path = within(root, root / artifact["path"])
        content = path.read_bytes()
        if digest(content) != artifact["sha256"] or len(content) != artifact["byte_count"]:
            raise IngestionError("Processed artifact checksum mismatch")
        rows = [
            models[kind].model_validate_json(line) for line in content.splitlines() if line.strip()
        ]
        if len(rows) != artifact["record_count"]:
            raise IngestionError("Processed partition count mismatch")
        if any(r.match_id.rsplit(":", 1)[1] != key for r in rows):
            raise IngestionError("Processed record belongs to a different match")
        records[kind].extend(rows)
    match_keys = {m["match_id"].rsplit(":", 1)[1] for m in report["matches"]}
    if len(match_keys) != report["matches_checked"] or partitions != {
        (kind, key) for kind in models for key in match_keys
    }:
        raise IngestionError("Processed partition coverage mismatch")
    if manifest["full_cohort"] and len(match_keys) != dataset.expected_match_count:
        raise IngestionError("Processed full-cohort claim mismatch")
    appearances = {(a.match_id, a.player_id): a for a in records["appearances"]}
    if len(appearances) != len(records["appearances"]):
        raise IngestionError("Duplicate processed appearance")
    durations = {(p.match_id, p.period): p.duration_seconds for p in records["periods"]}
    if len(durations) != len(records["periods"]):
        raise IngestionError("Duplicate processed period")
    totals = {"presence": defaultdict(float), "positions": defaultdict(float)}
    by_period = {"presence": defaultdict(list), "positions": defaultdict(list)}
    nominal = defaultdict(float)
    capacity = defaultdict(list)
    for kind in ("presence", "positions"):
        for interval in records[kind]:
            key = interval.match_id, interval.player_id
            appearance = appearances.get(key)
            if (
                appearance is None
                or appearance.quality_status != QualityStatus.VALIDATED
                or interval.quality_status != QualityStatus.VALIDATED
                or appearance.team_id != interval.team_id
            ):
                raise IngestionError("Usable interval belongs to an unvalidated appearance")
            period = interval.start.period
            a, b = interval.start.elapsed_seconds, interval.end.elapsed_seconds
            if (
                period != interval.end.period
                or (interval.match_id, period) not in durations
                or b > durations[interval.match_id, period]
            ):
                raise IngestionError("Processed interval outside resolved period")
            totals[kind][key] += b - a
            by_period[kind][(*key, period)].append((a, b))
            if kind == "presence":
                nominal[key] += (
                    max(0.0, min(b, NOMINAL_SECONDS[period]) - min(a, NOMINAL_SECONDS[period])) / 60
                )
                capacity[interval.match_id, interval.team_id, period].extend([(a, 1), (b, -1)])
    for kind in by_period:
        for spans in by_period[kind].values():
            spans.sort()
            if any(
                a < prev_b - EPSILON for (_, prev_b), (a, _) in zip(spans, spans[1:], strict=False)
            ):
                raise IngestionError("Overlapping usable processed intervals")
    for timeline in capacity.values():
        on_pitch = 0
        for _, change in sorted(timeline):
            on_pitch += change
            if on_pitch < 0 or on_pitch > 11:
                raise IngestionError("Processed team exceeds eleven-player capacity")
    for key, appearance in appearances.items():
        if appearance.quality_status == QualityStatus.VALIDATED:
            if (
                abs(totals["presence"][key] - appearance.playing_seconds) > EPSILON
                or abs(totals["positions"][key] - appearance.playing_seconds) > EPSILON
                or abs(nominal[key] - appearance.nominal_minutes) > EPSILON
            ):
                raise IngestionError("Processed interval totals differ from appearance minutes")
            # Equal sums alone are insufficient: role intervals must cover the same timeline.
            for period in NOMINAL_SECONDS:
                present = by_period["presence"][(*key, period)]
                positioned = by_period["positions"][(*key, period)]
                cuts = sorted({t for a, b in present + positioned for t in (a, b)})
                for a, b in zip(cuts, cuts[1:], strict=False):
                    t = (a + b) / 2
                    if any(x <= t < y for x, y in present) != any(
                        x <= t < y for x, y in positioned
                    ):
                        raise IngestionError("Processed position/presence timeline mismatch")
        elif appearance.playing_seconds is not None or appearance.nominal_minutes is not None:
            raise IngestionError("Quarantined appearance exposes usable minutes")
    quality = Counter({"VALIDATED": 0, "NEEDS_REVIEW": 0, "EXCLUDED": 0})
    quality.update(a.quality_status.value for a in appearances.values())
    quality["unused_roster"] = sum(len(m["unused_roster"]) for m in report["matches"])
    if (
        dict(quality) != manifest["appearance_quality"]
        or dict(quality) != report["appearance_quality"]
    ):
        raise IngestionError("Processed quality counts mismatch")
    if sum(quality.values()) != source_manifest["roster_entries"]:
        raise IngestionError("Processed roster census differs from upstream cohort")
    return {
        "phase": 3,
        "processed_integrity": "VERIFIED",
        "network_access": False,
        "full_cohort": manifest["full_cohort"],
        "matches_checked": len(match_keys),
        "validation_manifest_sha256": digest(data),
        "appearance_quality": dict(quality),
        "presence_intervals": len(records["presence"]),
        "position_intervals": len(records["positions"]),
        "validated_periods": len(records["periods"]),
    }
