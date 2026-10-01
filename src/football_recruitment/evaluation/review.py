"""Read-only checks of self-reported film review records, never expert certification."""

import hashlib
import math
import re
from datetime import date


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _duration(intervals):
    """Union intervals so repeated/overlapping viewing is not extra exposure."""
    end = total = 0
    for start, stop in sorted(intervals):
        total += max(0, stop - max(start, end))
        end = max(end, stop)
    return total


def _sample_points(source):
    """Check replay point references without deriving viewing time or match clocks."""
    points = source.get("timestamped_observations")
    if source.get("timestamp_basis") != "youtube_replay" or not isinstance(points, list):
        return False
    if not points:
        return False
    for point in points:
        if not isinstance(point, dict) or not _text(point.get("observation")):
            return False
        timestamp = point.get("timestamp")
        if not isinstance(timestamp, str) or not re.fullmatch(r"\d+:\d{2}(?::\d{2})?", timestamp):
            return False
        parts = [int(part) for part in timestamp.split(":")]
        if any(part >= 60 for part in parts[1:]):
            return False
        seconds = sum(part * 60**power for power, part in enumerate(reversed(parts)))
        if not _seconds(point.get("replay_seconds")) or point["replay_seconds"] != seconds:
            return False
        if point.get("match_clock") is not None:
            return False
    return True


def check_reviews(evidence, results):
    """Return errors and advisory coverage; inputs are not modified."""
    if not isinstance(evidence, dict) or evidence.get("protocol_version") != "cb-review-0.1":
        raise ValueError("Expected cb-review-0.1 model evidence")
    if not isinstance(results, dict):
        raise ValueError("Review results must be a case-keyed object")
    cases = [(c["case_id"], [c["query"], c["peer"]], "pair") for c in evidence["pairs"]]
    cases += [(c["case_id"], [c["player"]], "candidate") for c in evidence["candidates"]]
    if len({c[0] for c in cases}) != len(cases):
        raise ValueError("Duplicate evidence case IDs")
    cases.sort(key=lambda c: hashlib.sha256(("cb-review-0.1:" + c[0]).encode()).hexdigest())
    expected = {f"CASE-{i:02d}" for i in range(1, len(cases) + 1)}
    errors = [f"Unexpected case: {key}" for key in sorted(set(results) - expected)]
    locators = {
        (f["player"]["player_id"], f["player"]["team_id"], f["match_id"])
        for f in evidence["footage_locators"]
    }
    reports = []
    for index, (case_id, players, kind) in enumerate(cases, 1):
        alias = f"CASE-{index:02d}"
        issues, warnings, exposure = [], [], {}
        row = results.get(alias)
        if not isinstance(row, dict):
            reports.append({"case": alias, "errors": ["Missing or invalid case record"]})
            continue
        status = row.get("review_status")
        if status not in {"NOT_PERFORMED", "NOT_ASSESSABLE", "LIMITED", "COMPLETED"}:
            issues.append("Unknown review_status")
        rating_fields = (
            "blind_pair_similarity_1_to_5",
            "blind_requirement_fit_1_to_5",
            "revealed_model_agreement_1_to_5",
        )
        rated = any(row.get(field) is not None for field in rating_fields)
        for field in rating_fields:
            value = row.get(field)
            if value is not None and (type(value) is not int or not 1 <= value <= 5):
                issues.append(f"{field}: expected integer 1-5 or null")
        irrelevant = rating_fields[1] if kind == "pair" else rating_fields[0]
        if row.get(irrelevant) is not None:
            issues.append(f"{irrelevant}: incompatible with case type")
        if rated and status in {"NOT_PERFORMED", "NOT_ASSESSABLE"}:
            issues.append("Unperformed/unassessable cases cannot carry ratings")
        active = status in {"LIMITED", "COMPLETED"} or rated
        limited_unrated = status == "LIMITED" and not rated
        if status != "NOT_PERFORMED":
            for field in (
                "reviewer",
                "reviewer_experience",
                "context_and_uncertainty",
                "observation_summary",
                "supported_next_action",
            ):
                if not _text(row.get(field)):
                    issues.append(f"{field}: nonempty text required")
            try:
                raw_date = row.get("review_date", "")
                if date.fromisoformat(raw_date).isoformat() != raw_date:
                    raise ValueError("Noncanonical date")
            except (TypeError, ValueError):
                issues.append("review_date: expected ISO date YYYY-MM-DD")
            exposure_disclosure = row.get("model_seen_before_review")
            if limited_unrated and exposure_disclosure == "unknown":
                warnings.append("Prior model exposure unknown; consult verbatim disclosure")
                if not _text(row.get("model_exposure_disclosure")):
                    issues.append("model_exposure_disclosure: verbatim explanation required")
            elif type(exposure_disclosure) is not bool:
                issues.append("model_seen_before_review: boolean disclosure required")
        confidence = row.get("confidence_low_medium_high")
        if (
            active
            and confidence not in {"low", "medium", "high"}
            and not (limited_unrated and confidence in {"unknown", "not assessed"})
        ):
            issues.append("confidence_low_medium_high: low/medium/high required")
        elif active and confidence in {"unknown", "not assessed"}:
            warnings.append("Reviewer confidence not assessed; no rating inferred")
        if row.get("revealed_model_agreement_1_to_5") is not None:
            if not _text(row.get("disagreement_reason")):
                issues.append("disagreement_reason: explanation required after reveal")
        sources = row.get("footage_sources_and_timestamps")
        if not isinstance(sources, list):
            issues.append("footage_sources_and_timestamps: expected list")
            sources = []
        ids = set()
        sampled_identities = set()
        unknown_duration_identities = set()
        identities = {(p["player_id"], p["team_id"]) for p in players}
        for number, source in enumerate(sources, 1):
            prefix = f"Source {number}"
            if not isinstance(source, dict):
                issues.append(f"{prefix}: expected structured source record")
                continue
            sid = source.get("source_id")
            if not _text(sid) or sid in ids:
                issues.append(f"{prefix}: unique nonempty source_id required")
            else:
                ids.add(sid)
            identity = (source.get("player_id"), source.get("team_id"))
            match = source.get("match_id")
            if identity not in identities:
                issues.append(f"{prefix}: player/team does not belong to this case")
            if (*identity, match) not in locators:
                issues.append(f"{prefix}: fixture is not in the frozen pack locators")
            for field in ("reference", "authorization_basis", "observed_role"):
                if not _text(source.get(field)):
                    issues.append(f"{prefix}: {field} required")
                elif source[field].strip().lower() in {"unknown", "not assessed"}:
                    warnings.append(f"{prefix}: {field} is unknown/not assessed")
            if source.get("content_kind") not in {"full_match", "highlights"}:
                issues.append(f"{prefix}: content_kind must be full_match or highlights")
            if source.get("content_kind") == "highlights":
                warnings.append(f"{prefix}: highlights provide limited coverage")
            if active and (
                not _text(row.get("observation_summary"))
                or f"[{sid}]" not in row["observation_summary"]
            ):
                issues.append(f"{prefix}: observation_summary must cite [{sid}]")
            intervals = source.get("observed_intervals_seconds")
            sampled = source.get("viewing_mode") == "sampled_with_skips"
            if sampled:
                if not limited_unrated:
                    issues.append(
                        f"{prefix}: skipped sample requires LIMITED status and no ratings"
                    )
                if not _sample_points(source):
                    issues.append(
                        f"{prefix}: valid YouTube point observations required; "
                        "match clocks must remain unknown"
                    )
                elif identity in identities and (*identity, match) in locators:
                    sampled_identities.add(identity)
                if intervals == [] and source.get("watched_minutes") == "unknown":
                    unknown_duration_identities.add(identity)
                    warnings.append(f"{prefix}: skipped viewing; continuous duration unknown")
                    continue
            if not isinstance(intervals, list) or not intervals:
                issues.append(f"{prefix}: actual observed intervals required")
                continue
            valid = []
            for interval in intervals:
                if (
                    not isinstance(interval, list)
                    or len(interval) != 2
                    or not all(_seconds(v) for v in interval)
                    or interval[1] <= interval[0]
                ):
                    issues.append(f"{prefix}: intervals need finite start < end video seconds")
                else:
                    valid.append(interval)
            if identity in identities and (*identity, match) in locators:
                # Different video editions may have different clocks. Conservatively take
                # the largest source exposure for a fixture, never sum editions.
                key = (*identity, match)
                seconds = _duration(valid) if source.get("content_kind") == "full_match" else 0
                exposure[key] = max(exposure.get(key, 0), seconds)
        coverage = []
        for player in players:
            identity = (player["player_id"], player["team_id"])
            matches = {key[2]: value / 60 for key, value in exposure.items() if key[:2] == identity}
            substantial = sum(value >= 60 for value in matches.values())
            coverage.append(
                {
                    "player_id": identity[0],
                    "team_id": identity[1],
                    "self_reported_full_match_minutes": matches,
                    "continuous_duration_status": (
                        "unknown"
                        if identity in unknown_duration_identities
                        else "INTERVALS_REPORTED"
                        if matches
                        else "NO_INTERVALS_REPORTED"
                    ),
                    "timestamped_sample_present": identity in sampled_identities,
                }
            )
            if (
                active
                and not (limited_unrated and identity in sampled_identities)
                and not any(
                    isinstance(s, dict)
                    and (s.get("player_id"), s.get("team_id")) == identity
                    and isinstance(s.get("observed_intervals_seconds"), list)
                    and any(
                        isinstance(i, list)
                        and len(i) == 2
                        and all(_seconds(v) for v in i)
                        and i[1] > i[0]
                        for i in s["observed_intervals_seconds"]
                    )
                    for s in sources
                )
            ):
                issues.append(f"{identity[0]}: no reported viewing supports this review")
            if active and substantial < 2:
                warnings.append(f"{identity[0]}: below recommended two matches of 60 minutes")
        reports.append(
            {
                "case": alias,
                "case_id": case_id,
                "declared_status": status,
                "errors": issues,
                "warnings": warnings,
                "coverage": coverage,
            }
        )
    return {
        "check": "REVIEW_RECORD_STRUCTURE_ONLY",
        "expert_validation": "NOT_CERTIFIED",
        "predictive_validation": "NOT_PERFORMED",
        "errors": errors,
        "cases": reports,
        "valid_structure": not errors and all(not r["errors"] for r in reports),
        "pending_cases": sum(r.get("declared_status") == "NOT_PERFORMED" for r in reports),
        "note": "Viewing, rights, expertise and judgments are human declarations. "
        "Coverage recommendations are advisory, not a validation pass threshold.",
    }
