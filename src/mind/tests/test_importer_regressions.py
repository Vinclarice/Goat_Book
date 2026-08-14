"""Regressions from an adversarial review of the import path.

Each of these encodes a bug that was real and shipped. They are grouped by what
the bug would have cost, because that is what makes them worth keeping: almost
all of them produced a *wrong date with no error*, which is the failure mode the
whole import path exists to prevent and the one no downstream check would catch.

Said plainly: these were written after the fixes, not before them.
"""

import json
import os
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind.importers import (
    JsonlSource,
    MarkdownDirectorySource,
    SourceRecord,
    TimeQuality,
    parse_timestamp,
    resolve_captured_at,
    run_import,
)
from mind.importers.markdown_files import split_front_matter, timestamp_from_filename
from mind.models import Node

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
NY = "America/New_York"


def _jsonl(tmp_path, rows, name="s", **kw):
    path = tmp_path / "export.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return JsonlSource(path=path, name=name, **kw)


# ---------------------------------------------------------------------------
# Wrong dates, silently
# ---------------------------------------------------------------------------


def test_iso_basic_format_is_not_mistaken_for_an_epoch():
    """`20240301` is all digits AND a valid ISO date.

    Reading it as an epoch yields nothing plausible, so the date was discarded
    and the caller fell through to filesystem mtime — a silent wrong date.
    """
    assert parse_timestamp("20240301") == datetime(2024, 3, 1)
    assert parse_timestamp("20240301T1430") == datetime(2024, 3, 1, 14, 30)
    # A real epoch is not valid ISO, so it still reaches the epoch branch.
    assert parse_timestamp("1709303400").year == 2024


def test_an_iso_basic_front_matter_date_is_honoured(owner, tmp_path):
    (tmp_path / "note.md").write_text(
        "---\ncreated: 20190704\n---\nA thought.\n", encoding="utf-8"
    )
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    assert Node.objects.get().captured_at.year == 2019
    assert report.quality.get(TimeQuality.FALLBACK.value, 0) == 0


def test_a_byte_order_mark_does_not_hide_front_matter(owner, tmp_path):
    """Windows PowerShell writes a BOM by default, so this is the common case.

    With it unhandled the text began "﻿---", front matter was never
    recognised, the stated date was discarded in favour of file metadata, and the
    raw front matter block landed in the node body and its search vector.
    """
    path = tmp_path / "note.md"
    path.write_bytes(
        "---\ncreated: 2019-07-04\ntitle: Furnace filter\n---\nChanged it.\n".encode(
            "utf-8-sig"
        )
    )
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    node = Node.objects.get()
    assert node.captured_at.year == 2019
    assert report.quality.get(TimeQuality.FALLBACK.value, 0) == 0
    assert "---" not in node.original_content, "front matter must not become body"
    assert "created:" not in node.original_content


@pytest.mark.parametrize(
    "stem,expected",
    [
        # A second date in a range was consumed as a clock: 20:24:03
        ("2024-03-01 to 2024-03-02", datetime(2024, 3, 1)),
        # A bare year became 20:19
        ("2024-03-01 Q3 2019 review", datetime(2024, 3, 1)),
        # Digits far from the date are not a time
        ("2024-03-01-part-12-34", datetime(2024, 3, 1)),
        # A time genuinely adjacent to the date is still read
        ("2024-03-01 0930", datetime(2024, 3, 1, 9, 30)),
        ("2024-03-01T14-30-15", datetime(2024, 3, 1, 14, 30, 15)),
        # Implausible years are false positives, not very old notes
        ("1234-05-06 old", None),
    ],
)
def test_only_a_time_adjacent_to_the_date_is_read_from_a_filename(stem, expected):
    assert timestamp_from_filename(stem) == expected


def test_an_ambiguous_slash_date_is_refused_rather_than_guessed():
    """03/01/2024 is 3 January or 1 March depending on the locale.

    Guessing is the worst option: whenever the day is 12 or lower the wrong
    reading succeeds silently, so half a corpus lands months out and half is
    correct with nothing to distinguish them.
    """
    assert parse_timestamp("03/01/2024") is None
    assert parse_timestamp("3/1/24") is None
    # Year-first is unambiguous and still parsed.
    assert parse_timestamp("2024/03/01") == datetime(2024, 3, 1)


def test_a_naive_fold_one_value_still_shifts_forward_out_of_a_gap():
    """The contract is "forward to the first real instant"; a fold=1 input
    shifted backwards instead."""
    resolved, quality = resolve_captured_at(
        datetime(2026, 3, 8, 2, 30, fold=1), NY
    )
    assert quality is TimeQuality.NONEXISTENT
    assert resolved.utcoffset() == timedelta(hours=-4), "past the gap, not before it"


# ---------------------------------------------------------------------------
# Lost material
# ---------------------------------------------------------------------------


def test_body_text_is_not_deleted_by_an_opening_thematic_break():
    """A file legitimately opening with `---` as a horizontal rule lost
    everything up to the next `---`."""
    keys, body = split_front_matter(
        "---\nI wrote this on a napkin.\n---\nThe real body follows.\n"
    )
    assert keys == {}
    assert "napkin" in body
    assert "The real body follows." in body


def test_an_undatable_jsonl_record_is_reported_not_vanished(owner, tmp_path):
    """Previously these returned None inside the adapter and were counted
    nowhere at all."""
    source = _jsonl(
        tmp_path,
        [
            {"id": "a", "content": "good", "created_at": "2020-01-01"},
            {"id": "b", "content": "no date here"},
            {"id": "c", "content": "bad date", "created_at": "sometime last year"},
        ],
    )
    report = run_import(owner, source, now=NOW)

    assert report.created == 1
    assert len(source.skipped) == 2
    reasons = dict(source.skipped)
    assert "no 'created_at' field" in reasons["line-2"]
    assert "unparseable" in reasons["line-3"]


def test_a_field_name_mismatch_is_visible_rather_than_a_silent_no_op(owner, tmp_path):
    """The worst case found: an export using `date` instead of `created_at`
    dropped every record and the command reported success over a whole corpus."""
    source = _jsonl(
        tmp_path,
        [{"id": str(i), "content": f"t{i}", "date": "2020-01-01"} for i in range(5)],
    )
    report = run_import(owner, source, now=NOW)

    assert report.created == 0
    assert report.reached_runner == 0, "nothing reached the runner — the signal"
    assert len(source.skipped) == 5, "and every dropped record is accounted for"


def test_an_unreadable_markdown_file_is_reported(owner, tmp_path):
    (tmp_path / "binary.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    (tmp_path / "2024-03-01.md").write_text("fine\n", encoding="utf-8")

    source = MarkdownDirectorySource(root=tmp_path)
    report = run_import(owner, source, now=NOW)

    assert report.created == 1
    assert any("unreadable" in reason for _, reason in source.skipped)


def test_an_undated_skipped_markdown_file_is_reported(owner, tmp_path):
    (tmp_path / "undated.md").write_text("no date anywhere\n", encoding="utf-8")
    source = MarkdownDirectorySource(root=tmp_path, use_mtime_fallback=False)
    run_import(owner, source, now=NOW)

    assert source.skipped == [("undated.md", "no date in front matter or filename")]


# ---------------------------------------------------------------------------
# Dedupe and identity
# ---------------------------------------------------------------------------


def test_reordering_an_export_does_not_reimport_or_lose_records(owner, tmp_path):
    """Line-number ids aliased catastrophically: prepending one entry shifted
    every key, re-importing the corpus; removing one made a line number name a
    different record, which was then silently skipped as already-imported."""
    rows = [
        {"content": "first thought", "created_at": "2020-01-01"},
        {"content": "second thought", "created_at": "2020-01-02"},
    ]
    source = _jsonl(tmp_path, rows, id_field=None)
    assert run_import(owner, source, now=NOW).created == 2

    reordered = _jsonl(
        tmp_path,
        [{"content": "prepended", "created_at": "2019-01-01"}, *rows],
        id_field=None,
    )
    report = run_import(owner, reordered, now=NOW)

    assert report.created == 1, "only the genuinely new entry"
    assert report.skipped == 2
    assert Node.objects.count() == 3


def test_an_empty_id_field_does_not_collapse_every_record(owner, tmp_path):
    """`{"id": ""}` made every row share one key, so all but the first vanished."""
    source = _jsonl(
        tmp_path,
        [
            {"id": "", "content": "first", "created_at": "2020-01-01"},
            {"id": "", "content": "second", "created_at": "2020-01-02"},
        ],
    )
    assert run_import(owner, source, now=NOW).created == 2


# ---------------------------------------------------------------------------
# Batch integrity and limits
# ---------------------------------------------------------------------------


def test_an_unexpected_exception_costs_one_record_not_the_batch(owner, tmp_path, monkeypatch):
    """The caught tuple honoured "one bad record does not lose the rest" only
    for three exception classes. Anything else unwound the enclosing batch
    transaction and discarded the report with it."""
    source = _jsonl(
        tmp_path,
        [{"id": str(i), "content": f"t{i}", "created_at": "2020-01-01"} for i in range(5)],
    )

    from mind import services

    real_capture = services.capture
    calls = {"n": 0}

    def exploding_capture(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise TypeError("not in the old caught tuple")
        return real_capture(*args, **kwargs)

    monkeypatch.setattr("mind.importers.runner.services.capture", exploding_capture)

    report = run_import(owner, source, now=NOW, batch_size=10)

    assert report.created == 4
    assert report.failed == 1
    assert Node.objects.count() == 4, "the other four survived"
    assert "TypeError" in report.failures[0][1]


def test_recorded_failures_are_bounded_but_the_count_is_exact(owner, tmp_path):
    from mind.importers.runner import MAX_RECORDED_FAILURES, ImportReport

    report = ImportReport(source="s")
    for i in range(MAX_RECORDED_FAILURES + 50):
        report.failed += 1
        report.record_failure(f"id-{i}", "systemic fault")

    assert report.failed == MAX_RECORDED_FAILURES + 50
    assert len(report.failures) == MAX_RECORDED_FAILURES


def test_limit_counts_new_records_so_a_repeated_run_makes_progress(owner, tmp_path):
    """`--limit` sliced the source stream before dedupe, so a resumed run spent
    its whole budget re-recognising material it already held — a nightly cap
    stalled permanently after the first night while reporting success."""
    source = _jsonl(
        tmp_path,
        [{"id": str(i), "content": f"t{i}", "created_at": "2020-01-01"} for i in range(10)],
    )

    first = run_import(owner, source, now=NOW, limit=4)
    assert first.created == 4

    second = run_import(owner, source, now=NOW, limit=4)
    assert second.created == 4, "progress, not four re-recognitions"

    third = run_import(owner, source, now=NOW, limit=4)
    assert third.created == 2
    assert Node.objects.count() == 10


# ---------------------------------------------------------------------------
# Body assembly
# ---------------------------------------------------------------------------


def test_a_markdown_heading_matching_the_title_is_not_duplicated():
    """`title:` in front matter plus `# Title` as the first line is the standard
    file shape, and it duplicated the title in the body and the search vector."""
    record = SourceRecord(
        external_id="x",
        content="# On hesitation\n\nI keep putting it off.",
        captured_at=datetime(2021, 4, 5),
        title="On hesitation",
    )
    assert record.body().count("On hesitation") == 1


def test_a_title_that_merely_prefixes_the_content_is_still_kept():
    """The prefix test also dropped titles it should have kept: "Meeting"
    against content opening "Meetings with Bob"."""
    record = SourceRecord(
        external_id="x",
        content="Meetings with Bob are always long.",
        captured_at=datetime(2021, 4, 5),
        title="Meeting",
    )
    assert record.body().startswith("Meeting\n\n")
