"""Hash-verified immutable cache, bounded public HTTP reads and crash-safe writes."""

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from football_recruitment.domain.models import Contract, NonEmpty, PositiveInt, ProviderSnapshot

SOURCE_PATH = re.compile(
    r"^data/(competitions\.json|matches/[0-9]+/[0-9]+\.json|"
    r"(?:events|lineups)/[0-9]+\.json)$"
)


class IngestionError(ValueError):
    """Explicit source/cache/mapping failure; never an empty observed dataset."""


class SourceArtifact(Contract):
    source_path: NonEmpty
    byte_count: PositiveInt
    snapshot: ProviderSnapshot


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes):
    """Reject invalid JSON, duplicate keys and non-finite numbers."""

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise IngestionError("Non-finite JSON number")
        return result

    def constant(value):
        raise IngestionError(f"Unsupported JSON constant: {value}")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise IngestionError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        data.decode("utf-8"),
        parse_float=finite_float,
        parse_constant=constant,
        object_pairs_hook=pairs,
    )


def json_bytes(value) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")


def within(root: Path, target: Path) -> Path:
    """Resolve symlinks/Windows junctions before any local artifact write."""

    def resolved(path):
        result = path.resolve()
        # Windows realpath can retain an extended prefix during concurrent directory creation.
        # Normalize only equivalent DOS/UNC representations after resolving junctions.
        text = str(result)
        if os.name == "nt":
            if text.startswith("\\\\?\\UNC\\"):
                result = Path("\\\\" + text[8:])
            elif re.match(r"^\\\\\?\\[A-Za-z]:\\", text):
                result = Path(text[4:])
        return result

    root = resolved(root)
    result = resolved(target)
    if not result.is_relative_to(root) or result == root:
        raise IngestionError("Artifact path escapes its configured storage root")
    return result


def immutable_write(path: Path, data: bytes, root: Path) -> None:
    """Publish atomically; refuse to replace different bytes at an immutable location."""
    path = within(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = within(root, path)
    if path.exists():
        if path.read_bytes() != data:
            raise IngestionError(f"Immutable artifact conflicts with existing bytes: {path.name}")
        return
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        # The cohort lock prevents concurrent runs from overwriting each other's cache receipts.
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def cohort_lock(path: Path, root: Path):
    """OS releases this advisory lock even after a hard process interruption."""
    path = within(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise IngestionError("Another ingestion process holds this snapshot lock") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def public_download(url: str, timeout: float, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "FootballRecruitmentResearch/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if urlparse(response.geturl()).hostname != "raw.githubusercontent.com":
            raise IngestionError("Unexpected source redirect host")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise IngestionError("Source exceeds the configured maximum payload size")
    return data


class SnapshotStore:
    """One pinned source revision, receipt per byte-preserved JSON payload."""

    def __init__(
        self,
        root: Path,
        revision: str,
        license_url: str,
        *,
        offline=False,
        fetcher: Callable = public_download,
        timeout=30.0,
        attempts=3,
        request_interval=0.15,
        max_bytes=32 * 1024 * 1024,
    ):
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise IngestionError("A full pinned Git revision is required")
        if attempts < 1 or timeout <= 0 or request_interval < 0 or max_bytes < 1:
            raise IngestionError("Invalid download limits")
        self.root = root.resolve()
        self.revision = revision
        self.license_url = license_url
        self.offline = offline
        self.fetcher = fetcher
        self.timeout = timeout
        self.attempts = attempts
        self.request_interval = request_interval
        self.max_bytes = max_bytes
        self._guard = threading.Lock()
        self._last_request = 0.0
        self._artifacts: dict[str, SourceArtifact] = {}
        self._hits = 0
        self._downloads = 0

    @property
    def artifacts(self) -> tuple[SourceArtifact, ...]:
        with self._guard:
            return tuple(self._artifacts[key] for key in sorted(self._artifacts))

    @property
    def stats(self):
        with self._guard:
            return {"cache_hits": self._hits, "downloads": self._downloads}

    def _network_read(self, url):
        for attempt in range(self.attempts):
            with self._guard:
                wait = max(0.0, self.request_interval - (time.monotonic() - self._last_request))
                if wait:
                    time.sleep(wait)
                self._last_request = time.monotonic()
            try:
                return self.fetcher(url, self.timeout, self.max_bytes)
            except urllib.error.HTTPError as error:
                if error.code not in {408, 429, 500, 502, 503, 504}:
                    raise IngestionError(f"Source returned HTTP {error.code}: {url}") from error
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if retry_after and retry_after.isdigit() and int(retry_after) > 30:
                    raise IngestionError(
                        "Provider asks for a long retry delay; resume later"
                    ) from error
                delay = max(
                    2**attempt, int(retry_after or 0) if (retry_after or "").isdigit() else 0
                )
            except (OSError, urllib.error.URLError) as error:
                delay = 2**attempt
                if attempt + 1 == self.attempts:
                    raise IngestionError(
                        f"Source read failed after bounded retries: {url}"
                    ) from error
            if attempt + 1 == self.attempts:
                raise IngestionError(f"Source unavailable after bounded retries: {url}")
            time.sleep(min(delay, 30))
        raise IngestionError("No download attempt completed")

    def read(self, source_path: str, expected_sha256: str | None = None):
        if not SOURCE_PATH.fullmatch(source_path):
            raise IngestionError("Unsupported source path")
        url = f"https://raw.githubusercontent.com/hudl/open-data/{self.revision}/{source_path}"
        path = within(self.root, self.root / source_path)
        receipt = within(self.root, path.with_suffix(".receipt.json"))
        cached = path.exists() and receipt.exists()
        if cached:
            artifact = SourceArtifact.model_validate(strict_json(receipt.read_bytes()))
            data = path.read_bytes()
            if (
                artifact.source_path != source_path
                or str(artifact.snapshot.source_url) != url
                or artifact.snapshot.revision != self.revision
                or artifact.snapshot.sha256 != digest(data)
                or artifact.byte_count != len(data)
                or str(artifact.snapshot.license_url) != self.license_url
                or artifact.snapshot.provider != "statsbomb"
                or len(data) > self.max_bytes
                or artifact.snapshot.snapshot_id
                != (f"statsbomb:{self.revision}:{source_path}:{digest(data)}")
            ):
                raise IngestionError(f"Cached source/receipt integrity mismatch: {source_path}")
        else:
            if self.offline:
                raise IngestionError(f"Verified cache unavailable in offline mode: {source_path}")
            data = self._network_read(url)
            if not isinstance(data, bytes) or not data or len(data) > self.max_bytes:
                raise IngestionError("Invalid/oversized downloaded payload")
            artifact = SourceArtifact(
                source_path=source_path,
                byte_count=len(data),
                snapshot=ProviderSnapshot(
                    snapshot_id=f"statsbomb:{self.revision}:{source_path}:{digest(data)}",
                    provider="statsbomb",
                    revision=self.revision,
                    retrieved_at=datetime.now(UTC),
                    source_url=url,
                    sha256=digest(data),
                    license_url=self.license_url,
                    schema_version="statsbomb-open-data",
                ),
            )
        if expected_sha256 and digest(data) != expected_sha256:
            raise IngestionError(f"Audited source hash mismatch: {source_path}")
        payload = strict_json(data)
        if not isinstance(payload, list) or not payload:
            raise IngestionError(f"Expected nonempty source record list: {source_path}")
        if not cached:
            # If interrupted between these writes, re-fetch and compare orphan bytes on resume.
            immutable_write(path, data, self.root)
            immutable_write(receipt, json_bytes(artifact.model_dump(mode="json")), self.root)
        with self._guard:
            self._artifacts[source_path] = artifact
            if cached:
                self._hits += 1
            else:
                self._downloads += 1
        return payload, artifact
