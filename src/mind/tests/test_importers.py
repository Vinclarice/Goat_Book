"""The import path.

The requirement worth most of these tests: an imported item keeps its
**original** timestamp. Getting that wrong would be invisible — no error, no
failed assertion in production, just every temporal detector quietly wrong on
the material most likely to trigger one.

The DST cases are the sharp edge. `zoneinfo` does not raise on a nonexistent
local time; it returns something plausible. So the only way to know a date was
guessed is to check explicitly and record it.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from mind import importers, queries
from mind.importers import (
    JsonlSource,
    MarkdownDirectorySource,
    SourceRecord,
    TimeQuality,
    import_key,
    parse_timestamp,
    resolve_captured_at,
    run_import,
)
from mind.importers.markdown_files import (
    split_front_matter,
    timestamp_from_filename,
)
from mind.models import ActivityEvent, EventType, Node, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
NY = "America/New_York"


# ---------------------------------------------------------------------------
# Timestamp resolution — the part that must not be wrong
# ---------------------------------------------------------------------------


def test_an_aware_timestamp_is_trusted_unchanged():
    stated = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    resolved, quality = resolve_captured_at(stated, NY)
    assert resolved == stated
    assert quality is TimeQuality.AWARE


def test_a_naive_timestamp_is_read_in_the_owners_zone():
    """Not the server's zone and not UTC — either would shift a decade of
    journal entries by hours."""
    resolved, quality = resolve_captured_at(datetime(2024, 3, 1, 9, 0), NY)
    assert quality is TimeQuality.LOCALISED
    assert resolved.utcoffset() == timedelta(hours=-5)  # EST in March
    assert resolved.astimezone(UTC).hour == 14


def test_the_same_wall_clock_resolves_differently_per_owner_zone():
    wall = datetime(2024, 6, 1, 9, 0)
    ny, _ = resolve_captured_at(wall, NY)
    tokyo, _ = resolve_captured_at(wall, "Asia/Tokyo")
    assert ny.astimezone(UTC) != tokyo.astimezone(UTC)


def test_an_ambiguous_local_time_picks_the_earlier_instant_and_says_so():
    """2026-11-01 01:30 happens twice in New York — clocks go back.

    Choosing silently would be defensible. Choosing silently and forgetting
    would not, which is why the quality is recorded.
    """
    resolved, quality = resolve_captured_at(datetime(2026, 11, 1, 1, 30), NY)
    assert quality is TimeQuality.AMBIGUOUS
    assert resolved.utcoffset() == timedelta(hours=-4), "the earlier, DST instant"


def test_a_nonexistent_local_time_shifts_forward_and_says_so():
    """2026-03-08 02:30 never happens in New York — clocks skip it.

    `zoneinfo` does not raise here; it returns something plausible. Without the
    explicit check this would pass unnoticed forever.
    """
    resolved, quality = resolve_captured_at(datetime(2026, 3, 8, 2, 30), NY)
    assert quality is TimeQuality.NONEXISTENT
    assert resolved.utcoffset() == timedelta(hours=-4), "past the gap"
    assert resolved.astimezone(ZoneInfo(NY)).hour == 3


def test_ordinary_times_near_a_transition_are_not_misreported():
    """The DST checks must not cry wolf on the hours either side."""
    for wall in (datetime(2026, 3, 8, 1, 30), datetime(2026, 3, 8, 4, 30)):
        _, quality = resolve_captured_at(wall, NY)
        assert quality is TimeQuality.LOCALISED, wall


@hyp_settings(max_examples=200, deadline=None)
@given(
    naive=st.datetimes(
        min_value=datetime(2015, 1, 1), max_value=datetime(2030, 12, 31)
    ),
    zone=st.sampled_from([NY, "Europe/London", "Australia/Sydney", "UTC", "Asia/Kolkata"]),
)
def test_resolution_always_produces_a_usable_instant(naive, zone):
    """Whatever the date and zone, resolution yields an aware datetime whose
    wall clock is either exactly what was asked for or, in a gap, later than it.

    Property-based because the interesting inputs are the two hours a year per
    zone that example-based tests never happen to pick.
    """
    resolved, quality = resolve_captured_at(naive, zone)

    assert resolved.tzinfo is not None
    assert resolved.utcoffset() is not None

    local_wall = resolved.astimezone(ZoneInfo(zone)).replace(tzinfo=None)
    if quality is TimeQuality.NONEXISTENT:
        assert local_wall > naive, "a skipped reading moves forward, never back"
    else:
        assert local_wall == naive


# ---------------------------------------------------------------------------
# Import keys
# ---------------------------------------------------------------------------


def test_import_keys_are_namespaced_by_source():
    """Two sources both numbering from 1 is not hypothetical, and a collision
    would silently drop the second as an already-imported duplicate."""
    assert import_key("dayone", "1") != import_key("keep", "1")


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


def _jsonl(tmp_path, rows, name="testsrc", **kw):
    path = tmp_path / "export.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return JsonlSource(path=path, name=name, **kw)


def test_import_creates_nodes_with_the_sources_own_dates(owner, tmp_path):
    source = _jsonl(
        tmp_path,
        [
            {"id": "a", "content": "older thought", "created_at": "2019-05-01T08:00:00"},
            {"id": "b", "content": "newer thought", "created_at": "2023-11-02T21:15:00"},
        ],
    )
    report = run_import(owner, source, now=NOW)

    assert (report.created, report.skipped, report.failed) == (2, 0, 0)
    years = sorted(n.captured_at.year for n in Node.objects.all())
    assert years == [2019, 2023], "the source's dates, not today's"
    assert all(n.source == NodeSource.IMPORT for n in Node.objects.all())


def test_imported_material_is_already_old(owner, tmp_path):
    """The reason import exists: dormancy cannot be waited for, but it can be
    imported."""
    source = _jsonl(
        tmp_path, [{"id": "a", "content": "x", "created_at": "2019-05-01T08:00:00"}]
    )
    run_import(owner, source, now=NOW)
    node = Node.objects.get()
    assert node.captured_at < node.created_at
    assert NOW - node.captured_at > timedelta(days=365 * 5)


def test_rerunning_an_import_creates_nothing_new(owner, tmp_path):
    rows = [{"id": "a", "content": "x", "created_at": "2019-05-01"}]
    source = _jsonl(tmp_path, rows)

    first = run_import(owner, source, now=NOW)
    second = run_import(owner, source, now=NOW)

    assert (first.created, first.skipped) == (1, 0)
    assert (second.created, second.skipped) == (0, 1)
    assert Node.objects.count() == 1


def test_an_interrupted_import_resumes_where_it_stopped(owner, tmp_path):
    """A run that died partway must not re-create what it already wrote, and
    must not skip what it did not."""
    rows = [
        {"id": str(i), "content": f"thought {i}", "created_at": "2020-01-01"}
        for i in range(10)
    ]
    source = _jsonl(tmp_path, rows)

    partial = run_import(owner, source, now=NOW, limit=4)
    assert partial.created == 4

    rest = run_import(owner, source, now=NOW)
    assert (rest.created, rest.skipped) == (6, 4)
    assert Node.objects.count() == 10


def test_one_unparseable_record_does_not_cost_the_rest(owner, tmp_path):
    """A single bad entry in a decade of journal must not lose the decade."""
    path = tmp_path / "export.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"id": "a", "content": "good", "created_at": "2020-01-01"}),
                "{ this is not json",
                json.dumps({"id": "c", "content": "also good", "created_at": "2021-01-01"}),
            ]
        ),
        encoding="utf-8",
    )
    report = run_import(owner, JsonlSource(path=path, name="s"), now=NOW)
    assert report.created == 2


def test_records_with_no_content_are_counted_not_created(owner, tmp_path):
    source = _jsonl(
        tmp_path,
        [
            {"id": "a", "content": "   ", "created_at": "2020-01-01"},
            {"id": "b", "content": "real", "created_at": "2020-01-01"},
        ],
    )
    report = run_import(owner, source, now=NOW)
    assert (report.created, report.empty) == (1, 1)


def test_a_dry_run_writes_nothing_but_reports_what_would_happen(owner, tmp_path):
    source = _jsonl(
        tmp_path,
        [{"id": str(i), "content": f"t{i}", "created_at": "2020-01-01"} for i in range(3)],
    )
    report = run_import(owner, source, now=NOW, dry_run=True)

    assert report.created == 3
    assert Node.objects.count() == 0
    assert ActivityEvent.objects.count() == 0


def test_the_import_records_one_bookkeeping_event(owner, tmp_path):
    source = _jsonl(
        tmp_path, [{"id": "a", "content": "x", "created_at": "2020-01-01"}]
    )
    run_import(owner, source, now=NOW)

    summary = ActivityEvent.objects.filter(node__isnull=True).get()
    assert summary.event_type == EventType.IMPORTED
    assert summary.occurred_at == NOW
    assert summary.payload["created"] == 1
    assert summary.payload["source"] == "testsrc"


def test_per_record_events_use_the_records_own_date(owner, tmp_path):
    """The event says when the thought happened, not when it was ingested."""
    source = _jsonl(
        tmp_path, [{"id": "a", "content": "x", "created_at": "2019-05-01T08:00:00"}]
    )
    run_import(owner, source, now=NOW)
    event = ActivityEvent.objects.filter(node__isnull=False).get()
    assert event.event_type == EventType.IMPORTED
    assert event.occurred_at.year == 2019


def test_two_sources_may_share_record_ids(owner, tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    for path in (a, b):
        path.write_text(
            json.dumps({"id": "1", "content": f"from {path.stem}", "created_at": "2020-01-01"}),
            encoding="utf-8",
        )

    run_import(owner, JsonlSource(path=a, name="dayone"), now=NOW)
    run_import(owner, JsonlSource(path=b, name="keep"), now=NOW)
    assert Node.objects.count() == 2


def test_batching_does_not_change_the_outcome(owner, tmp_path):
    source = _jsonl(
        tmp_path,
        [{"id": str(i), "content": f"t{i}", "created_at": "2020-01-01"} for i in range(25)],
    )
    report = run_import(owner, source, now=NOW, batch_size=4)
    assert report.created == 25
    assert Node.objects.count() == 25


def test_imports_are_owner_scoped(owner, other_owner, tmp_path):
    source = _jsonl(
        tmp_path, [{"id": "a", "content": "mine", "created_at": "2020-01-01"}]
    )
    run_import(owner, source, now=NOW)
    run_import(other_owner, source, now=NOW)

    assert Node.objects.count() == 2, "the same file imports separately per person"
    assert queries.live_nodes(owner).count() == 1


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_year",
    [
        ("2024-03-01T14:30:00Z", 2024),
        ("2024-03-01T14:30:00+02:00", 2024),
        ("2024-03-01 14:30:00", 2024),
        ("2024-03-01", 2024),
        ("2024/03/01", 2024),
        (1709304600, 2024),
        (1709304600000, 2024),
        (1709304600000000, 2024),
    ],
)
def test_parse_timestamp_reads_the_shapes_exports_actually_use(value, expected_year):
    parsed = parse_timestamp(value)
    assert parsed is not None
    assert parsed.year == expected_year


@pytest.mark.parametrize("value", [None, "", "   ", "not a date", "yesterday", True])
def test_parse_timestamp_returns_none_rather_than_raising(value):
    assert parse_timestamp(value) is None


def test_a_chromium_bookmark_timestamp_is_read_with_the_right_epoch():
    """Chromium's date_added counts microseconds since 1601, not 1970.

    A magnitude-based unit guess reads this as the year 2394 — a wrong date with
    no error attached, which is the worst kind. Every unit and epoch is tried and
    only the plausible interpretation is kept.
    """
    # 2024-03-01T14:30:00Z as Chromium base::Time
    chromium = (1709303400 + 11_644_473_600) * 1_000_000
    parsed = parse_timestamp(chromium)
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2024, 3, 1)


def test_an_implausible_epoch_is_refused_rather_than_guessed():
    assert parse_timestamp(99) is None, "1970 plus a minute is not a real note date"
    assert parse_timestamp(10**20) is None


def test_a_quoted_numeric_string_is_still_an_epoch():
    """JSON exports quote these constantly."""
    assert parse_timestamp("1709303400").year == 2024


@pytest.mark.parametrize(
    "value,expected",
    [
        # Obsidian Linter's default, which is what sits in real vaults
        ("Wednesday, January 1st 2020, 12:00:00 am", datetime(2020, 1, 1, 0, 0)),
        ("Saturday, March 7, 2026 11:42:18 AM", datetime(2026, 3, 7, 11, 42, 18)),
        ("Friday, 7 June 2024 22:47:03", datetime(2024, 6, 7, 22, 47, 3)),
    ],
)
def test_human_readable_stamps_are_read(value, expected):
    assert parse_timestamp(value) == expected


def test_a_nested_front_matter_key_cannot_shadow_a_real_date():
    """`date:` introducing a block must not be recorded as an empty value, or it
    would win the priority order over a later usable key."""
    keys, _ = split_front_matter("---\ndate:\n  - nested\ncreated: 2021-04-05\n---\nbody\n")
    assert "date" not in keys
    assert keys["created"] == "2021-04-05"


def test_modification_keys_are_not_treated_as_creation_dates(owner, tmp_path):
    """`updated` and `lastmod` would misdate exactly the notes revisited most,
    which are the ones a detector cares about."""
    (tmp_path / "note.md").write_text(
        "---\nupdated: 2026-01-01\nlastmod: 2026-02-01\n---\nA thought.\n",
        encoding="utf-8",
    )
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)
    assert report.quality[TimeQuality.FALLBACK.value] == 1, "fell through to metadata"


def test_a_trailing_z_is_read_as_utc():
    assert parse_timestamp("2024-03-01T14:30:00Z").utcoffset() == timedelta(0)


def test_a_bare_date_stays_naive_for_the_owners_zone_to_interpret():
    assert parse_timestamp("2024-03-01").tzinfo is None


# ---------------------------------------------------------------------------
# Markdown files
# ---------------------------------------------------------------------------


def test_front_matter_scalars_are_read_and_the_body_kept():
    keys, body = split_front_matter(
        "---\ntitle: On hesitation\ncreated: 2021-04-05\ntags:\n  - one\n---\nThe body.\n"
    )
    assert keys["title"] == "On hesitation"
    assert keys["created"] == "2021-04-05"
    assert "tags" not in keys, "nested values are skipped, not misread"
    assert body.strip() == "The body."


def test_a_file_without_front_matter_is_all_body():
    keys, body = split_front_matter("Just a thought.\n")
    assert keys == {}
    assert body.strip() == "Just a thought."


def test_an_unterminated_fence_is_treated_as_body():
    keys, body = split_front_matter("---\ntitle: broken\nno closing fence")
    assert keys == {}
    assert "title: broken" in body


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("2024-03-01", datetime(2024, 3, 1)),
        ("2024_03_01", datetime(2024, 3, 1)),
        ("20240301", datetime(2024, 3, 1)),
        ("journal-2024-03-01", datetime(2024, 3, 1)),
        ("2024-03-01 0930", datetime(2024, 3, 1, 9, 30)),
        ("not a date", None),
        ("2024-99-99", None),
    ],
)
def test_dates_are_read_out_of_filenames(stem, expected):
    """A name survives copying and syncing, which is exactly what strips mtime."""
    assert timestamp_from_filename(stem) == expected


def test_front_matter_beats_the_filename(owner, tmp_path):
    (tmp_path / "2024-03-01.md").write_text(
        "---\ncreated: 2019-07-04\n---\nA thought.\n", encoding="utf-8"
    )
    run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)
    assert Node.objects.get().captured_at.year == 2019


def test_the_filename_is_used_when_front_matter_has_no_date(owner, tmp_path):
    (tmp_path / "2024-03-01.md").write_text("A daily note.\n", encoding="utf-8")
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    assert Node.objects.get().captured_at.year == 2024
    assert report.quality.get(TimeQuality.FALLBACK.value, 0) == 0


def test_file_metadata_is_used_last_and_flagged_as_a_guess(owner, tmp_path):
    """A corpus resting on mtime cannot support a temporal detector, so the
    count is reported rather than buried."""
    (tmp_path / "undated.md").write_text("A thought with no date.\n", encoding="utf-8")
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    assert report.created == 1
    assert report.quality[TimeQuality.FALLBACK.value] == 1
    assert report.guessed_timestamps == 1


def test_undated_files_can_be_skipped_instead_of_guessed(owner, tmp_path):
    (tmp_path / "undated.md").write_text("no date anywhere\n", encoding="utf-8")
    (tmp_path / "2024-03-01.md").write_text("dated\n", encoding="utf-8")

    report = run_import(
        owner,
        MarkdownDirectorySource(root=tmp_path, use_mtime_fallback=False),
        now=NOW,
    )
    assert report.created == 1
    assert Node.objects.get().captured_at.year == 2024


def test_a_title_becomes_part_of_the_body(owner, tmp_path):
    (tmp_path / "note.md").write_text(
        "---\ntitle: On hesitation\ncreated: 2021-04-05\n---\nI keep putting it off.\n",
        encoding="utf-8",
    )
    run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)
    body = Node.objects.get().original_content
    assert body.startswith("On hesitation")
    assert "putting it off" in body


def test_a_title_already_opening_the_content_is_not_repeated():
    record = SourceRecord(
        external_id="x",
        content="On hesitation\n\nthe body",
        captured_at=datetime(2021, 4, 5),
        title="On hesitation",
    )
    assert record.body().count("On hesitation") == 1


def test_tooling_directories_are_skipped(owner, tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "workspace.md").write_text("config\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "2024-03-01.md").write_text("real note\n", encoding="utf-8")

    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)
    assert report.created == 1
    assert "real note" in Node.objects.get().original_content


def test_a_moved_file_is_re_imported_rather_than_silently_orphaned(owner, tmp_path):
    """The path-based id trades a visible duplicate for a hidden lost edit
    history, deliberately — a duplicate can be seen and merged."""
    original = tmp_path / "a.md"
    original.write_text("---\ncreated: 2021-04-05\n---\nbody\n", encoding="utf-8")
    run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    original.rename(tmp_path / "b.md")
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    assert report.created == 1
    assert Node.objects.count() == 2


def test_editing_a_file_does_not_create_a_second_node(owner, tmp_path):
    path = tmp_path / "a.md"
    path.write_text("---\ncreated: 2021-04-05\n---\nfirst\n", encoding="utf-8")
    run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    path.write_text("---\ncreated: 2021-04-05\n---\nedited\n", encoding="utf-8")
    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)

    assert (report.created, report.skipped) == (0, 1)
    assert Node.objects.count() == 1


def test_an_unreadable_file_is_skipped(owner, tmp_path):
    (tmp_path / "binary.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    (tmp_path / "2024-03-01.md").write_text("fine\n", encoding="utf-8")

    report = run_import(owner, MarkdownDirectorySource(root=tmp_path), now=NOW)
    assert report.created == 1
