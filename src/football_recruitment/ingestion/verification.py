"""Independent offline checksum/count verification of an ingestion manifest."""

from pathlib import Path

from football_recruitment.config import ProjectSettings
from football_recruitment.ingestion.storage import (
    SOURCE_PATH,
    IngestionError,
    SourceArtifact,
    digest,
    strict_json,
    within,
)
from football_recruitment.providers.statsbomb import MAPPING_VERSION


def verify_manifest(settings: ProjectSettings, project_root: Path, manifest_path: Path):
    """Integrity is not football validity: no appearance minutes are certified here."""
    project_root = project_root.resolve()
    dataset = settings.dataset
    raw_root = within(project_root, project_root / dataset.paths.raw)
    raw = raw_root / "statsbomb" / dataset.revision
    canonical_root = within(project_root, project_root / dataset.paths.interim)
    canonical = (
        canonical_root
        / "statsbomb"
        / dataset.revision
        / (f"{dataset.competition_id}-{dataset.season_id}")
        / MAPPING_VERSION
    )
    manifest_path = within(canonical, manifest_path)
    content = manifest_path.read_bytes()
    manifest = strict_json(content)
    if digest(content) != manifest_path.stem:
        raise IngestionError("Manifest filename/content hash mismatch")
    if manifest["revision"] != dataset.revision or manifest["mapping_version"] != MAPPING_VERSION:
        raise IngestionError("Manifest revision/mapping differs from configured baseline")
    if (manifest["competition_id"], manifest["season_id"]) != (
        dataset.competition_id,
        dataset.season_id,
    ) or manifest["cohort_match_count"] != dataset.expected_match_count:
        raise IngestionError("Manifest describes a different cohort")
    sources = {}
    for row in manifest["source_artifacts"]:
        artifact = SourceArtifact.model_validate(row)
        if not SOURCE_PATH.fullmatch(artifact.source_path) or artifact.source_path in sources:
            raise IngestionError("Invalid or duplicate source manifest path")
        path = within(raw, raw / artifact.source_path)
        data = path.read_bytes()
        receipt = SourceArtifact.model_validate(
            strict_json(path.with_suffix(".receipt.json").read_bytes())
        )
        if (
            artifact != receipt
            or artifact.snapshot.sha256 != digest(data)
            or artifact.byte_count != len(data)
        ):
            raise IngestionError(f"Raw source integrity mismatch: {artifact.source_path}")
        expected_url = f"https://raw.githubusercontent.com/hudl/open-data/{dataset.revision}/{artifact.source_path}"
        if (
            str(artifact.snapshot.source_url) != expected_url
            or artifact.snapshot.revision != dataset.revision
        ):
            raise IngestionError("Source provenance differs from pinned source")
        # Independent source record counts detect accidentally omitted rows in canonical partitions.
        payload = strict_json(data)
        if not isinstance(payload, list) or not payload:
            raise IngestionError("Source payload is not a nonempty record list")
        sources[artifact.source_path] = (artifact, len(payload))
    for source, expected in (
        ("data/competitions.json", dataset.catalog_sha256),
        (f"data/matches/{dataset.competition_id}/{dataset.season_id}.json", dataset.matches_sha256),
    ):
        if source not in sources or sources[source][0].snapshot.sha256 != expected:
            raise IngestionError("Audited catalog/match hash does not match manifest")
    partitions = set()
    event_keys = set()
    lineup_keys = set()
    count_events = count_roster = count_cards = 0
    for artifact in manifest["canonical_artifacts"]:
        identifier = (artifact["kind"], artifact["key"])
        if identifier in partitions:
            raise IngestionError("Duplicate canonical partition")
        partitions.add(identifier)
        path = within(canonical, canonical / artifact["path"])
        data = path.read_bytes()
        if digest(data) != artifact["sha256"] or len(data) != artifact["byte_count"]:
            raise IngestionError("Canonical artifact checksum mismatch")
        rows = [strict_json(line) for line in data.splitlines() if line.strip()]
        if len(rows) != artifact["record_count"]:
            raise IngestionError("Canonical row count differs from manifest")
        kind, key = identifier
        if kind == "events":
            event_keys.add(key)
            if sources.get(f"data/events/{key}.json", (None, None))[1] != len(rows):
                raise IngestionError("Canonical event count differs from raw source")
            count_events += len(rows)
        elif kind == "lineups":
            lineup_keys.add(key)
            if sources.get(f"data/lineups/{key}.json", (None, None))[1] != len(rows):
                raise IngestionError("Canonical team-sheet count differs from raw source")
            count_roster += sum(len(r["entries"]) for r in rows)
            count_cards += sum(len(p["cards"]) for r in rows for p in r["entries"])
        elif kind == "matches":
            if key != "all" or len(rows) != dataset.expected_match_count:
                raise IngestionError("Canonical cohort match count differs from audited baseline")
        elif kind == "catalog":
            if key != "all" or len(rows) != sources["data/competitions.json"][1]:
                raise IngestionError("Canonical catalog count differs from raw source")
        else:
            raise IngestionError("Unknown canonical artifact kind")
    if event_keys != lineup_keys or len(event_keys) != manifest["ingested_match_count"]:
        raise IngestionError("Incomplete event/lineup partition coverage")
    if ("catalog", "all") not in partitions or ("matches", "all") not in partitions:
        raise IngestionError("Canonical catalog/matches partition missing")
    expected_sources = {
        "data/competitions.json",
        f"data/matches/{dataset.competition_id}/{dataset.season_id}.json",
    }
    expected_sources.update(
        f"data/{kind}/{key}.json" for key in event_keys for kind in ("events", "lineups")
    )
    if set(sources) != expected_sources:
        raise IngestionError("Raw manifest coverage differs from canonical partitions")
    if manifest["full_cohort"] != (len(event_keys) == dataset.expected_match_count):
        raise IngestionError("Manifest full-cohort claim is inconsistent")
    if (count_events, count_roster, count_cards) != (
        manifest["event_count"],
        manifest["roster_entries"],
        manifest["card_observations"],
    ):
        raise IngestionError("Canonical aggregate counts differ from manifest")
    return {
        "artifact_integrity": "VERIFIED",
        "full_cohort": manifest["full_cohort"],
        "manifest_sha256": digest(content),
        "source_files": len(sources),
        "canonical_partitions": len(partitions),
        "ingested_matches": len(event_keys),
        "event_count": count_events,
        "roster_entries": count_roster,
        "card_observations": count_cards,
        "canonical_quality": "UNVALIDATED",
        "minutes_validation": "not_run",
        "network_access": False,
    }
