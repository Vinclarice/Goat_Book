"""A generic JSON Lines adapter — one object per line.

The escape hatch. Any format with no dedicated adapter can be converted to JSONL
by a few lines of throwaway script, which is a far better use of effort than a
bespoke adapter for a corpus imported once. It is also the adapter the tests use
to exercise the runner without touching a filesystem layout.

Field names are configurable because no two exports agree on them.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from .base import SourceRecord, TimeQuality


# Seconds between 1601-01-01 and 1970-01-01. Chromium's base::Time — which is
# what `date_added` in a Chrome or Edge Bookmarks file holds — counts
# microseconds from the earlier epoch, so it is off by this plus a factor of a
# million from a unix timestamp.
WEBKIT_EPOCH_OFFSET = 11_644_473_600

# A resolved epoch must land in here to be believed. Without this the unit
# heuristic below silently turns a Chromium timestamp into a date in the year
# 2394 — a wrong date that no error reports and no test would notice.
PLAUSIBLE_YEARS = range(1990, 2101)

# Human-readable stamps that real exports emit. Obsidian's Linter plugin writes
# `date created` in this shape by default, and Kindle clippings use variants of
# it. Locale-dependent (%A/%B), which is acceptable for a single-user tool on an
# English system but is the reason these come last.
HUMAN_FORMATS = (
    "%A, %B %d %Y, %I:%M:%S %p",  # Wednesday, January 1 2020, 12:00:00 am
    "%A, %B %d, %Y %I:%M:%S %p",  # Saturday, March 7, 2026 11:42:18 AM
    "%A, %d %B %Y %H:%M:%S",  # Friday, 7 June 2024 22:47:03
    "%A, %B %d %Y",
    "%B %d, %Y",  # March 20, 2014
    "%B %d %Y",  # March 20 2014 — the same date without the comma
)

NUMERIC_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",  # unambiguous: a four-digit year cannot be a month
)

# `NN/NN/YYYY` is deliberately NOT parsed. It is genuinely ambiguous — 03/01/2024
# is 3 January to most of the world and 1 March in the United States — and
# guessing is the worst available option: whenever the day is 12 or lower the
# wrong reading succeeds silently, so half a corpus lands months out and half is
# correct, with no error to distinguish them. This module's whole premise is that
# a wrong date is worse than a missing one, so it is refused.
AMBIGUOUS_SLASH_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")

ORDINAL = re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)


def _from_epoch(raw: float) -> datetime | None:
    """Try each unit and epoch that exports actually use, keeping the plausible one.

    Self-correcting rather than heuristic-on-magnitude: every interpretation is
    tried and only one that lands in a believable range is accepted. A Chromium
    microsecond-since-1601 value only looks sane under the last interpretation,
    and a unix second count only under the first, so the range check does the
    disambiguating instead of a digit count.
    """
    for divisor, offset in (
        (1, 0),  # seconds since 1970
        (1e3, 0),  # milliseconds since 1970
        (1e6, 0),  # microseconds since 1970 (Firefox JSON backups)
        (1e6, WEBKIT_EPOCH_OFFSET),  # microseconds since 1601 (Chromium)
    ):
        try:
            candidate = datetime.fromtimestamp(raw / divisor - offset, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            continue
        if candidate.year in PLAUSIBLE_YEARS:
            return candidate
    return None


def parse_timestamp(value: Any) -> datetime | None:
    """Read the timestamp shapes exports actually use.

    Returns None rather than raising, so one unparseable date costs one record
    and not the run. Naive results are intentional and stay naive — they are
    wall-clock readings, and interpreting them belongs to `resolve_captured_at`
    with the owner's zone.

    That last choice is a genuine fork: Hugo and Jekyll treat a naive front
    matter date as UTC, whereas a personal second mind is better served reading
    it in the person's own zone, since that is what they meant when they typed
    it. Worth a setting if this ever ingests someone else's published site.
    """
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _from_epoch(float(value))

    text = str(value).strip().strip("'\"")
    if not text:
        return None

    if AMBIGUOUS_SLASH_DATE.match(text):
        return None

    # ISO is tried before the epoch branch, and the order matters: "20240301" is
    # all digits *and* a valid ISO basic-format date. Reading it as an epoch
    # instead yields nothing plausible, so the date would be discarded and the
    # caller would fall through to filesystem metadata — a silent wrong date,
    # which is the exact failure this module exists to prevent. A genuine epoch
    # like "1709303400" is not valid ISO, so it falls through here correctly.
    iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        pass

    # A bare integer arriving as a string — common, since JSON exports quote it.
    if text.isdigit():
        return _from_epoch(float(text))

    for pattern in NUMERIC_FORMATS:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue

    without_ordinals = ORDINAL.sub(r"\1", text)
    for pattern in HUMAN_FORMATS:
        try:
            return datetime.strptime(without_ordinals, pattern)
        except ValueError:
            continue

    return None


@dataclass
class JsonlSource:
    """One JSON object per line, with a configurable field mapping.

    `skipped` accumulates every line passed over and why, so nothing vanishes
    between the file and the report. Without it, pointing this at an export whose
    timestamp field is named `date` rather than `created_at` produces a run that
    reports "0 created" and exits successfully — a silent no-op over a whole
    corpus, indistinguishable from an empty file.
    """

    path: Path
    name: str = "jsonl"
    content_field: str = "content"
    timestamp_field: str = "created_at"
    id_field: str | None = "id"
    title_field: str | None = "title"
    extra_fields: Sequence[str] = field(default_factory=tuple)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def records(self) -> Iterator[SourceRecord]:
        self.skipped = []
        with open(self.path, encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    # Skip rather than abort: the rest of the file is still good.
                    self.skipped.append((f"line-{line_number}", f"invalid json: {exc}"))
                    continue
                if not isinstance(payload, dict):
                    self.skipped.append((f"line-{line_number}", "not a json object"))
                    continue

                record = self._to_record(payload, line_number)
                if record is not None:
                    yield record

    def _to_record(self, payload: dict, line_number: int) -> SourceRecord | None:
        where = f"line-{line_number}"
        content = str(payload.get(self.content_field) or "")
        title = (
            str(payload[self.title_field])
            if self.title_field and payload.get(self.title_field)
            else None
        )

        raw_timestamp = payload.get(self.timestamp_field)
        captured_at = parse_timestamp(raw_timestamp)
        if captured_at is None:
            reason = (
                f"no {self.timestamp_field!r} field"
                if raw_timestamp is None
                else f"unparseable {self.timestamp_field}: {raw_timestamp!r}"
            )
            self.skipped.append((where, reason))
            return None

        return SourceRecord(
            external_id=self._external_id(payload, content, captured_at),
            content=content,
            captured_at=captured_at,
            quality=TimeQuality.LOCALISED,
            title=title,
            extra={k: payload.get(k) for k in self.extra_fields if k in payload},
        )

    def _external_id(self, payload: dict, content: str, captured_at) -> str:
        """A stable id, falling back to a content hash rather than a line number.

        Line number is a property of the *file*, not the record, and using it
        aliases catastrophically across re-exports: prepend one entry and every
        line shifts, so the whole corpus imports a second time; remove one and a
        line number names a different record whose key already exists, so that
        record is silently skipped as already-imported. The second failure is
        invisible — it reports as a normal resume.

        A content hash trades that for a milder, *visible* failure: editing an
        entry produces a second node rather than updating the first. A duplicate
        can be seen and merged; a silently dropped entry cannot.
        """
        if self.id_field:
            raw = payload.get(self.id_field)
            if raw is not None and str(raw).strip():
                return str(raw).strip()

        digest = hashlib.sha256(
            f"{captured_at.isoformat()}\x1f{content}".encode()
        ).hexdigest()
        return f"sha256-{digest[:32]}"
