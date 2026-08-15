"""Markdown or plain-text files on disk — the most likely real corpus.

Timestamp recovery is the whole difficulty, and it is attempted in descending
order of trust:

1. **YAML front matter** — an explicit date the person or their tool wrote down.
2. **The filename** — daily-note conventions like `2024-03-01.md` state a date
   plainly, and a date embedded in a name is far more durable than file metadata.
3. **Filesystem mtime** — marked `FALLBACK`, because it is not a creation time
   and is destroyed by copying, syncing, zip extraction, and git checkout. A
   corpus resting mostly on this cannot support a temporal detector, which is
   why the count is reported rather than buried.

Front matter is scanned for scalar keys only, not parsed as full YAML. That
avoids a dependency for the sake of reading a date, and the failure mode is
benign: an exotic value simply is not recognised and the next strategy is tried.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from .base import SourceRecord, TimeQuality
from .jsonl import parse_timestamp

# Tried in this order, stopping at the first parseable value.
#
# Obsidian has no core creation-date property, so the keys that appear in real
# vaults come from plugins and differ between them: `created`/`updated` from
# Update Time on Edit, `date created`/`date modified` from the Linter — whose
# default value format is a human string like "Wednesday, January 1st 2020,
# 12:00:00 am", handled in parse_timestamp.
#
# `created` before `date` deliberately: where a file has both, `date` is often a
# publication date, and it is Hugo's and Jekyll's key rather than a creation
# marker. Modification keys are omitted entirely — `updated` and `lastmod` are
# not creation times and using them would misdate exactly the notes that were
# revisited most, which are the ones a detector cares about.
FRONT_MATTER_DATE_KEYS = (
    "created",
    "created_at",
    "date created",
    "date-created",
    "datecreated",
    "creation_date",
    "created-date",
    "date",
    "publishdate",
    "publish_date",
    "pubdate",
    "published",
)

FRONT_MATTER_TITLE_KEYS = ("title",)

# A date anywhere in the filename: 2024-03-01, 2024_03_01, 20240301.
FILENAME_DATE = re.compile(r"(?<!\d)(\d{4})[-_]?(\d{2})[-_]?(\d{2})(?!\d)")

# A time, but only immediately adjacent to the date and separated from it.
#
# Anchored deliberately. An unanchored search over the rest of the filename reads
# any digits at all as a clock: "2024-03-01 to 2024-03-02" became 20:24:03 by
# consuming the second date, and "2024-03-01 Q3 2019 review" became 20:19 by
# consuming a bare year. Both pass an hour<24/minute<60 guard, because those are
# valid clock numbers — the fix has to be positional, not a range check.
FILENAME_TIME = re.compile(r"^[ _T-]+(\d{2})[-_:]?(\d{2})(?:[-_:]?(\d{2}))?(?!\d)")

# A filename date outside this range is a false positive, not a very old note —
# the same guard _from_epoch applies to epochs.
PLAUSIBLE_YEARS = range(1900, 2101)

SCALAR_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*)\s*:\s*(.*)$")


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Return (scalar front-matter keys, remaining body).

    Recognises the conventional `---` fenced block at the very start of a file.
    Nested structures and lists are skipped rather than misread; only top-level
    scalars are collected, which is all a date or title ever is.
    """
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            block, body = lines[1:index], "\n".join(lines[index + 1 :])
            break
    else:
        return {}, text  # unterminated fence: treat the whole file as body

    found: dict[str, str] = {}
    for line in block:
        if not line.strip() or line.startswith((" ", "\t", "-", "#")):
            continue  # nested value, list item, or comment
        match = SCALAR_LINE.match(line)
        if match:
            key, value = match.group(1).strip().lower(), match.group(2).strip()
            if not value:
                # `tags:` introducing a nested block or list. Recording it as an
                # empty string would let it shadow a real key later in the
                # priority order.
                continue
            found[key] = value.strip("'\"")

    if not found:
        # Nothing parsed as front matter, so the opening `---` was a horizontal
        # rule and the "block" was prose. Discarding it would delete real body
        # text — everything up to the next `---` — so the whole file is kept.
        return {}, text

    return found, body.lstrip("\n")


def timestamp_from_filename(stem: str) -> datetime | None:
    """A date, and optionally a time, stated in the filename.

    More trustworthy than file metadata: a name survives copying and syncing,
    which is exactly what strips mtime.
    """
    date_match = FILENAME_DATE.search(stem)
    if not date_match:
        return None

    year, month, day = (int(g) for g in date_match.groups())
    if year not in PLAUSIBLE_YEARS:
        return None
    try:
        base = datetime(year, month, day)
    except ValueError:
        return None  # 2024-99-99 and similar

    # match, not search: the time must sit immediately after the date.
    time_match = FILENAME_TIME.match(stem[date_match.end() :])
    if time_match:
        hour, minute, second = (int(g or 0) for g in time_match.groups())
        if hour < 24 and minute < 60 and second < 60:
            base = base.replace(hour=hour, minute=minute, second=second)

    return base  # naive by design: a filename states wall clock, not an instant


@dataclass
class MarkdownDirectorySource:
    """Every matching file under a directory, recursively."""

    root: Path
    name: str = "markdown"
    patterns: Sequence[str] = ("**/*.md", "**/*.markdown", "**/*.txt")
    skip_directories: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                ".git",
                ".obsidian",
                ".trash",
                "node_modules",
                ".venv",
                "__pycache__",
                ".stfolder",
            }
        )
    )
    use_mtime_fallback: bool = True
    skipped: list[tuple[str, str]] = field(default_factory=list)
    """What was passed over and why, so nothing vanishes between the directory
    and the report."""

    def records(self) -> Iterator[SourceRecord]:
        self.skipped = []
        root = Path(self.root)
        for path in sorted(self._files(root)):
            record = self._to_record(path, root)
            if record is not None:
                yield record

    def _files(self, root: Path) -> Iterator[Path]:
        seen: set[Path] = set()
        for pattern in self.patterns:
            for path in root.glob(pattern):
                if path in seen or not path.is_file():
                    continue
                if self.skip_directories & set(path.relative_to(root).parts[:-1]):
                    continue
                seen.add(path)
                yield path

    def _to_record(self, path: Path, root: Path) -> SourceRecord | None:
        relative = path.relative_to(root).as_posix()
        try:
            # utf-8-sig, not utf-8: a byte-order mark would otherwise leave the
            # text starting "﻿---", so startswith("---") fails, the front
            # matter is never recognised, the date the person wrote is discarded
            # in favour of file metadata, and the raw front matter block ends up
            # in the node body and its search vector. Windows PowerShell writes a
            # BOM by default, so this is the common case here, not an exotic one.
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError) as exc:
            self.skipped.append((relative, f"unreadable: {exc.__class__.__name__}"))
            return None

        front_matter, body = split_front_matter(text)

        captured_at, quality = self._resolve(path, front_matter)
        if captured_at is None:
            self.skipped.append((relative, "no date in front matter or filename"))
            return None

        title = next(
            (front_matter[k] for k in FRONT_MATTER_TITLE_KEYS if front_matter.get(k)),
            None,
        )

        # Path-relative id, not a content hash: editing a note must update the
        # same node rather than creating a second one. The trade is that moving a
        # file re-imports it, which is the less damaging failure — a duplicate is
        # visible, whereas a silently orphaned edit history is not.
        external_id = relative

        return SourceRecord(
            external_id=external_id,
            content=body,
            captured_at=captured_at,
            quality=quality,
            title=title,
            extra={"path": external_id},
        )

    def _resolve(
        self, path: Path, front_matter: dict[str, str]
    ) -> tuple[datetime | None, TimeQuality]:
        for key in FRONT_MATTER_DATE_KEYS:
            if key in front_matter:
                parsed = parse_timestamp(front_matter[key])
                if parsed is not None:
                    return parsed, TimeQuality.LOCALISED

        from_name = timestamp_from_filename(path.stem)
        if from_name is not None:
            return from_name, TimeQuality.LOCALISED

        if not self.use_mtime_fallback:
            return None, TimeQuality.FALLBACK

        try:
            # os.stat directly rather than a cached DirEntry.stat(): the cached
            # form has returned zeroed Windows timestamps in some CPython builds.
            stat = path.stat()
        except OSError:
            return None, TimeQuality.FALLBACK

        # The *earlier* of birth time and modification time, not birth time
        # alone. A copied file gets a fresh birth time while keeping the older
        # mtime, so preferring birth time would date a copied archive to the day
        # it was copied — the exact error this whole module exists to avoid.
        # st_birthtime is available on Windows from Python 3.12.
        candidates = [stat.st_mtime]
        birth = getattr(stat, "st_birthtime", None)
        if birth:
            candidates.append(birth)

        # Marked FALLBACK regardless: this is file metadata, not something the
        # person wrote, and git checkout, sync clients, and archive extraction
        # each destroy it in their own way.
        return (
            datetime.fromtimestamp(min(candidates), tz=timezone.utc),
            TimeQuality.FALLBACK,
        )
