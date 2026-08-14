"""Import primitives: what a source yields, and how its timestamps are resolved.

Backfill import is not a migration nicety. Every detector is corpus-dependent —
*Dormant thread* specifically cannot fire before nodes have had time to become
dormant — so importing material that is already old is what makes the connection
lab testable in week one rather than month three. It is also a rehearsal: the
same code path eventually absorbs Clarice's own captures, so the migration gets
exercised continuously instead of designed once and attempted at the end.

The single most important requirement here is that an imported item keeps its
**original** timestamp. Stamping ingestion time instead would silently make
every time-based detector wrong on precisely the material most likely to trigger
one, and nothing downstream would report an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo

from ..services import AttachmentSpec


class TimeQuality(Enum):
    """How much to trust a resolved timestamp — recorded, never discarded.

    An import that quietly guessed at half its dates would look identical to one
    that read them all correctly, so the guess is always recorded on the event.
    """

    AWARE = "aware"
    """The source stated an absolute instant. Used unchanged."""

    LOCALISED = "localised"
    """Naive local time, interpreted in the owner's zone. The common case."""

    AMBIGUOUS = "ambiguous"
    """Naive local time inside a repeated hour — it happened twice that day."""

    NONEXISTENT = "nonexistent"
    """Naive local time inside a skipped hour — that clock reading never
    occurred. Shifted forward to the first real instant after the gap."""

    FALLBACK = "fallback"
    """No timestamp in the source at all; something weaker was used, such as
    filesystem mtime. The least trustworthy, and worth reporting a count of."""


@dataclass(frozen=True)
class SourceRecord:
    """One item as a source presents it, before it becomes a Node.

    `captured_at` may be naive: most note formats store local wall-clock time
    with no offset, and the correct absolute instant is only recoverable using
    the owner's own time zone. Resolution happens in `resolve_captured_at`, at
    the boundary, rather than being left to each adapter to get wrong
    separately.
    """

    external_id: str
    """Stable within this source, across re-runs. See `import_key`."""

    content: str
    captured_at: datetime
    quality: TimeQuality = TimeQuality.LOCALISED
    title: str | None = None
    attachments: Sequence[AttachmentSpec] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    def body(self) -> str:
        """Title and content as one text, since a node has one body.

        A title already stated at the top of the content is not repeated. The
        comparison is against the first line with any markdown heading markers
        stripped, because the standard file shape — `title:` in front matter and
        `# Title` as the opening line — does not match a plain prefix test, and
        the duplicate would land in both the node body and its search vector.

        Compared as a whole line rather than a prefix in the other direction too:
        a title of "Meeting" must not be swallowed by content opening "Meetings
        with Bob".
        """
        if not self.title:
            return self.content

        first_line = self.content.lstrip().split("\n", 1)[0]
        if first_line.lstrip("#").strip() == self.title.strip():
            return self.content

        return f"{self.title}\n\n{self.content}".strip()


class ImportSource(Protocol):
    """A format adapter. Yields records; knows nothing about the database.

    Deliberately narrow: adapters do no writing, no deduplication, and no
    timestamp interpretation beyond reading what the format states. Everything
    that could be got subtly wrong lives in one place instead of once per
    format.
    """

    name: str
    """Short, stable identifier — namespaces `import_key`, so renaming it
    orphans every record already imported from this source."""

    def records(self) -> Iterator[SourceRecord]: ...


def import_key(source_name: str, external_id: str) -> str:
    """Namespaced so two sources cannot collide on a shared id.

    Both formats numbering their notes from 1 is not hypothetical, and an
    unnamespaced collision would silently drop the second source's material as
    an already-imported duplicate.
    """
    return f"{source_name}:{external_id}"


def _wall_clock(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def _is_nonexistent(aware: datetime) -> bool:
    """True when this wall-clock reading never occurred in this zone.

    Detected by round-tripping through UTC and comparing **wall clock** rather
    than the datetimes themselves: two aware datetimes compare by instant, so a
    direct `!=` is always False and would detect nothing.
    """
    round_tripped = aware.astimezone(timezone.utc).astimezone(aware.tzinfo)
    return _wall_clock(round_tripped) != _wall_clock(aware)


def _is_ambiguous(aware: datetime) -> bool:
    """True when this wall-clock reading occurred twice — a repeated hour.

    Must be tested only after `_is_nonexistent`: a gap time also changes offset
    with `fold`, so this would report True for it as well.
    """
    return aware.replace(fold=0).utcoffset() != aware.replace(fold=1).utcoffset()


def resolve_captured_at(
    value: datetime, owner_time_zone: str
) -> tuple[datetime, TimeQuality]:
    """Turn what a source stated into an absolute instant, and say how.

    An aware value is trusted as-is. A naive value is a wall-clock reading in
    the person's own zone — never in the server's, and never in UTC, both of
    which would shift a year of journal entries by hours and quietly corrupt
    every dormancy and recurrence judgement made over them.

    Two clock changes break the naive case, and both are handled explicitly
    rather than left to whatever `zoneinfo` does by default:

    * **Ambiguous** (the hour repeats when clocks go back): the earlier of the
      two instants is chosen, and the ambiguity is recorded. Picking silently
      would be defensible; picking silently *and forgetting* would not.
    * **Nonexistent** (the hour is skipped when clocks go forward): shifted
      forward to the first real instant after the gap. Note that `zoneinfo`
      does not raise here — it returns something plausible — so without an
      explicit check this passes unnoticed.
    """
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value, TimeQuality.AWARE

    zone = ZoneInfo(owner_time_zone)
    # fold=0 explicitly. A naive value carrying fold=1 would otherwise shift
    # *backwards* out of a gap rather than forwards, breaking the contract stated
    # below. Not reachable through any current parser — fromisoformat, strptime
    # and the datetime constructor all produce fold=0 — but the invariant should
    # not depend on that staying true.
    localised = value.replace(tzinfo=zone, fold=0)

    if _is_nonexistent(localised):
        # The round trip lands on the first real instant after the gap, which is
        # exactly the forward shift we want.
        shifted = localised.astimezone(timezone.utc).astimezone(zone)
        return shifted, TimeQuality.NONEXISTENT

    if _is_ambiguous(localised):
        return localised.replace(fold=0), TimeQuality.AMBIGUOUS

    return localised, TimeQuality.LOCALISED
