"""Drives a source into the database: resumable, batched, and honest about loss.

Three properties matter more than throughput here.

**Resumable.** A 50,000-item import that dies at item 30,000 must skip those
30,000 on the next run. `import_key` uniqueness already makes `capture()`
idempotent, so correctness is free; the pre-fetched key set below only makes it
fast.

**One bad record does not lose the rest.** A malformed item is skipped with its
reason recorded, not raised. This is the same commitment as "capture is durable
before it is clever", applied to bulk: a single unparseable entry in a decade of
journal must not cost the decade.

**Nothing is silently guessed.** Timestamp quality is counted and reported. An
import that inferred half its dates from filesystem mtime looks identical, in
the database, to one that read them all correctly — so the difference is
surfaced rather than left for a detector to trip over months later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from itertools import islice
from typing import Iterable, Iterator

from django.db import DatabaseError, transaction

from .. import services
from ..models import EventType, Node, NodeSource
from .base import ImportSource, SourceRecord, TimeQuality, import_key, resolve_captured_at

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 200
MAX_RECORDED_FAILURES = 500


@dataclass
class ImportReport:
    """What actually happened. Every field is something a person should see."""

    source: str
    created: int = 0
    skipped: int = 0
    failed: int = 0
    empty: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    quality: dict[str, int] = field(default_factory=dict)

    def record_failure(self, external_id: str, reason: str) -> None:
        """Keep the reason, but bounded.

        A systemic fault — an unreadable owner time zone, say — fails every
        record, and holding one tuple per record turns a 50,000-item import into
        50,000 accumulated strings to print twenty of. The count in `failed`
        stays exact regardless.
        """
        if len(self.failures) < MAX_RECORDED_FAILURES:
            self.failures.append((external_id, reason))

    @property
    def reached_runner(self) -> int:
        """Records the adapter actually handed over.

        Deliberately not named `considered`: it does not count what the source
        file held. An adapter drops malformed and undatable records before this
        point, and reports those separately through its own `skipped` list.
        """
        return self.created + self.skipped + self.failed + self.empty

    @property
    def guessed_timestamps(self) -> int:
        """How many dates were not stated plainly by the source.

        The number worth looking at before trusting any temporal detector over
        this material.
        """
        return (
            self.quality.get(TimeQuality.FALLBACK.value, 0)
            + self.quality.get(TimeQuality.AMBIGUOUS.value, 0)
            + self.quality.get(TimeQuality.NONEXISTENT.value, 0)
        )

    def summary(self) -> str:
        parts = [
            f"{self.source}: {self.created} created",
            f"{self.skipped} already present",
        ]
        if self.empty:
            parts.append(f"{self.empty} empty")
        if self.failed:
            parts.append(f"{self.failed} failed")
        if self.guessed_timestamps:
            parts.append(f"{self.guessed_timestamps} timestamps not stated by source")
        return ", ".join(parts)


def _batched(iterable: Iterable[SourceRecord], size: int) -> Iterator[list[SourceRecord]]:
    iterator = iter(iterable)
    while chunk := list(islice(iterator, size)):
        yield chunk


def existing_keys(owner, source_name: str) -> set[str]:
    """Keys already imported from this source.

    Fetched once rather than queried per record: on a large corpus the
    per-record lookup is the whole cost of a resumed run, and this reduces it to
    one indexed scan.
    """
    prefix = f"{source_name}:"
    return set(
        Node.objects.filter(owner=owner, import_key__startswith=prefix).values_list(
            "import_key", flat=True
        )
    )


def run_import(
    owner,
    source: ImportSource,
    *,
    now: datetime,
    actor: str = "importer",
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
    dry_run: bool = False,
) -> ImportReport:
    """Import everything `source` yields that is not already present.

    `limit` bounds how many records are *created*, so a repeated run with a limit
    makes progress each time rather than re-recognising what it already holds.

    `now` is only used for the import's own bookkeeping event. Every node's
    `captured_at` comes from the record, never from here — that separation is
    the entire point of the import path.

    `dry_run` reads, resolves, and counts without writing. It reports what would
    happen, including timestamp quality, which is the thing worth checking
    before committing a decade of material.
    """
    report = ImportReport(source=source.name)
    seen = existing_keys(owner, source.name)

    for batch in _batched(source.records(), batch_size):
        # One transaction per batch, so a crash keeps completed batches. Each
        # record then runs in its own savepoint, so a single failure rolls back
        # only itself and the batch continues.
        with transaction.atomic():
            for record in batch:
                _ingest_one(
                    owner,
                    source,
                    record,
                    report=report,
                    seen=seen,
                    actor=actor,
                    dry_run=dry_run,
                )
                # `limit` counts *new* records, not records consumed. Applying it
                # to the source stream instead would make a resumed run spend the
                # whole budget re-recognising material it already has, so a
                # nightly `--limit 1000` would stall permanently after the first
                # night while reporting success.
                if limit is not None and report.created >= limit:
                    break
        if limit is not None and report.created >= limit:
            break

    if not dry_run:
        services._record(
            owner,
            EventType.IMPORTED,
            occurred_at=now,
            actor=actor,
            payload={
                "source": source.name,
                "created": report.created,
                "skipped": report.skipped,
                "failed": report.failed,
                "quality": report.quality,
            },
        )

    logger.info("import finished — %s", report.summary())
    return report


def _ingest_one(
    owner,
    source: ImportSource,
    record: SourceRecord,
    *,
    report: ImportReport,
    seen: set[str],
    actor: str,
    dry_run: bool,
) -> None:
    key = import_key(source.name, record.external_id)

    if key in seen:
        report.skipped += 1
        return

    try:
        captured_at, quality = resolve_captured_at(
            record.captured_at, owner.time_zone
        )
    except Exception as exc:  # a bad zone or an unrepresentable date
        report.failed += 1
        report.record_failure(record.external_id, f"timestamp: {exc}")
        return

    # A record's own quality wins when it already knows its date was a guess —
    # an adapter falling back to filesystem mtime says so, and resolving that
    # naive value must not upgrade the claim to "localised".
    if record.quality is TimeQuality.FALLBACK:
        quality = TimeQuality.FALLBACK

    body = record.body()
    if not body.strip() and not record.attachments:
        report.empty += 1
        return

    if dry_run:
        report.created += 1
        report.quality[quality.value] = report.quality.get(quality.value, 0) + 1
        seen.add(key)
        return

    try:
        with transaction.atomic():  # savepoint: isolates this record's failure
            services.capture(
                owner,
                content=body,
                captured_at=captured_at,
                source=NodeSource.IMPORT,
                actor=actor,
                import_key=key,
                attachments=record.attachments,
            )
    except Exception as exc:
        # Deliberately broad. A named tuple of exception classes only honours
        # "one bad record does not lose the rest" for the classes someone
        # remembered: a TypeError from a malformed AttachmentSpec, a
        # ValidationError, an AttributeError on a custom user model would each
        # escape, unwind the enclosing per-batch transaction, and discard up to
        # batch_size already-processed records *along with the report itself*.
        # Losing the report is what makes it unacceptable — the failure would be
        # unattributable. The record's reason is recorded instead.
        report.failed += 1
        report.record_failure(record.external_id, f"{exc.__class__.__name__}: {exc}")
        logger.warning("import skipped %s: %s", key, exc)
        return

    report.created += 1
    report.quality[quality.value] = report.quality.get(quality.value, 0) + 1
    seen.add(key)
