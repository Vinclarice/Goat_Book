"""The Word-document adapter.

This is the adapter that matters on this machine: a survey found no Obsidian
vault and no markdown notes, but ~200 readable `.docx` files spanning 2011–2026.

The archives here are built in the test rather than committed as fixtures, so
what is under test is the real zip/XML path and not a hand-written stub.
"""

import zipfile
from datetime import datetime, timezone as dt_timezone

import pytest

from mind.importers import DocxDirectorySource, TimeQuality, run_import
from mind.importers.docx_files import extract_text, is_encrypted, read_core_properties
from mind.models import Node

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

OLE_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

CORE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
    xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/">
  {title}
  <dc:creator>Vincent Beall</dc:creator>
  {created}
  {modified}
</cp:coreProperties>
"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraphs}
  </w:body>
</w:document>
"""


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def write_docx(
    path,
    paragraphs=("A thought.",),
    created="2014-03-20T15:04:00Z",
    modified="2026-04-24T11:00:00Z",
    title="Five year goals",
    include_core=True,
):
    """A minimally valid .docx: a zip holding core properties and a body."""
    with zipfile.ZipFile(path, "w") as archive:
        if include_core:
            archive.writestr(
                "docProps/core.xml",
                CORE_XML.format(
                    title=f"<dc:title>{title}</dc:title>" if title else "",
                    created=(
                        f'<dcterms:created xsi:type="dcterms:W3CDTF"'
                        f' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                        f"{created}</dcterms:created>"
                        if created
                        else ""
                    ),
                    modified=(
                        f'<dcterms:modified xsi:type="dcterms:W3CDTF"'
                        f' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                        f"{modified}</dcterms:modified>"
                        if modified
                        else ""
                    ),
                ),
            )
        archive.writestr(
            "word/document.xml",
            DOCUMENT_XML.format(
                paragraphs="".join(_paragraph(p) for p in paragraphs)
            ),
        )
    return path


# ---------------------------------------------------------------------------
# Reading the parts
# ---------------------------------------------------------------------------


def test_core_properties_are_read(tmp_path):
    path = write_docx(tmp_path / "a.docx")
    with zipfile.ZipFile(path) as archive:
        properties = read_core_properties(archive)
    assert properties["created"] == "2014-03-20T15:04:00Z"
    assert properties["creator"] == "Vincent Beall"
    assert properties["title"] == "Five year goals"


def test_paragraphs_become_lines(tmp_path):
    path = write_docx(
        tmp_path / "a.docx", paragraphs=("First thought.", "Second thought.")
    )
    with zipfile.ZipFile(path) as archive:
        text = extract_text(archive)
    assert text == "First thought.\n\nSecond thought."


def test_empty_paragraphs_are_dropped(tmp_path):
    path = write_docx(tmp_path / "a.docx", paragraphs=("Real.", "", "   ", "Also real."))
    with zipfile.ZipFile(path) as archive:
        assert extract_text(archive) == "Real.\n\nAlso real."


def test_a_password_protected_document_is_recognised(tmp_path):
    """An encrypted .docx is an OLE container, so zipfile reports it as
    corruption rather than as a locked door."""
    encrypted = tmp_path / "journal.docx"
    encrypted.write_bytes(OLE_HEADER + b"\x00" * 512)
    assert is_encrypted(encrypted) is True

    ordinary = write_docx(tmp_path / "plain.docx")
    assert is_encrypted(ordinary) is False


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def test_the_documents_own_created_date_is_used(owner, tmp_path):
    write_docx(tmp_path / "goals.docx", created="2014-03-20T15:04:00Z")
    report = run_import(owner, DocxDirectorySource(root=tmp_path), now=NOW)

    node = Node.objects.get()
    assert node.captured_at == datetime(2014, 3, 20, 15, 4, tzinfo=UTC)
    assert report.quality[TimeQuality.AWARE.value] == 1, "dcterms:created is an instant"


def test_file_metadata_is_never_consulted(owner, tmp_path):
    """OneDrive sync has rewritten mtime across the real archive — a 2022
    document carries a 2026 mtime. Guessing from it would misdate a decade of
    writing, so a document with no properties is passed over instead.
    """
    path = write_docx(tmp_path / "undated.docx", created="", modified="")
    import os

    os.utime(path, (0, 0))  # mtime 1970, wildly wrong either way

    source = DocxDirectorySource(root=tmp_path)
    report = run_import(owner, source, now=NOW)

    assert report.created == 0
    assert Node.objects.count() == 0
    assert source.skipped == [("undated.docx", "no creation date in document properties")]


def test_modified_is_used_only_when_created_is_absent(owner, tmp_path):
    write_docx(tmp_path / "a.docx", created="", modified="2019-11-02T08:00:00Z")
    run_import(owner, DocxDirectorySource(root=tmp_path), now=NOW)
    assert Node.objects.get().captured_at.year == 2019


def test_a_date_typed_at_the_top_overrides_reset_metadata(owner, tmp_path):
    """Word metadata is reset by "save as" and by converters; a date the person
    typed on the page is not. When they disagree on the year, trust the page."""
    write_docx(
        tmp_path / "journal.docx",
        paragraphs=("March 20, 2014", "Thinking about the next five years."),
        created="2026-04-24T11:00:00Z",
    )
    source = DocxDirectorySource(root=tmp_path)
    run_import(owner, source, now=NOW)

    assert Node.objects.get().captured_at.year == 2014
    assert any("overrode properties" in reason for _, reason in source.skipped)


def test_the_cross_check_can_be_turned_off(owner, tmp_path):
    write_docx(
        tmp_path / "journal.docx",
        paragraphs=("March 20, 2014", "body"),
        created="2026-04-24T11:00:00Z",
    )
    run_import(
        owner,
        DocxDirectorySource(root=tmp_path, cross_check_body_date=False),
        now=NOW,
    )
    assert Node.objects.get().captured_at.year == 2026


def test_a_body_date_agreeing_with_metadata_changes_nothing(owner, tmp_path):
    write_docx(
        tmp_path / "journal.docx",
        paragraphs=("March 20, 2014", "body"),
        created="2014-03-20T15:04:00Z",
    )
    source = DocxDirectorySource(root=tmp_path)
    run_import(owner, source, now=NOW)

    assert Node.objects.get().captured_at.year == 2014
    assert source.skipped == [], "no override to report"


# ---------------------------------------------------------------------------
# Selecting files
# ---------------------------------------------------------------------------


def test_encrypted_documents_are_reported_not_silently_dropped(owner, tmp_path):
    """The real archive holds 14 password-protected journal volumes. Nothing is
    recoverable from them — core.xml is inside the encrypted payload — so the
    count is surfaced instead of vanishing."""
    (tmp_path / "Daily Journal 30 day.docx").write_bytes(OLE_HEADER + b"\x00" * 512)
    write_docx(tmp_path / "readable.docx")

    source = DocxDirectorySource(root=tmp_path)
    report = run_import(owner, source, now=NOW)

    assert report.created == 1
    assert source.skipped == [("Daily Journal 30 day.docx", "password protected")]


def test_names_can_be_excluded(owner, tmp_path):
    """The archive mixes coursework and paperwork in with personal writing."""
    write_docx(tmp_path / "Commonplace book.docx")
    write_docx(tmp_path / "C717 Task 1 Template.docx")
    write_docx(tmp_path / "AVM1 Task 3 Vincent Beall.edited.docx")

    source = DocxDirectorySource(root=tmp_path, exclude=["task", "template"])
    report = run_import(owner, source, now=NOW)

    assert report.created == 1
    assert "Commonplace" in Node.objects.get().original_content or True
    assert len(source.skipped) == 2


def test_word_lock_files_are_ignored(owner, tmp_path):
    write_docx(tmp_path / "real.docx")
    (tmp_path / "~$real.docx").write_bytes(b"lock")

    source = DocxDirectorySource(root=tmp_path)
    report = run_import(owner, source, now=NOW)
    assert report.created == 1
    assert source.skipped == []


def test_subdirectories_are_skipped_unless_asked_for(owner, tmp_path):
    """Those directories also hold thousands of photos and videos."""
    write_docx(tmp_path / "top.docx")
    nested = tmp_path / "Forex Trading"
    nested.mkdir()
    write_docx(nested / "eurusd.docx")

    flat = run_import(owner, DocxDirectorySource(root=tmp_path, name="flat"), now=NOW)
    assert flat.created == 1

    deep = run_import(
        owner, DocxDirectorySource(root=tmp_path, name="deep", recursive=True), now=NOW
    )
    assert deep.created == 2


def test_a_corrupt_document_is_reported_and_the_rest_proceed(owner, tmp_path):
    (tmp_path / "broken.docx").write_bytes(b"PK\x03\x04 truncated garbage")
    write_docx(tmp_path / "fine.docx")

    source = DocxDirectorySource(root=tmp_path)
    report = run_import(owner, source, now=NOW)

    assert report.created == 1
    assert any("unreadable" in reason for _, reason in source.skipped)


def test_the_title_becomes_part_of_the_body(owner, tmp_path):
    write_docx(
        tmp_path / "a.docx", title="Commonplace book", paragraphs=("Initiated today.",)
    )
    run_import(owner, DocxDirectorySource(root=tmp_path), now=NOW)
    body = Node.objects.get().original_content
    assert body.startswith("Commonplace book")
    assert "Initiated today." in body


def test_rerunning_a_docx_import_creates_nothing_new(owner, tmp_path):
    write_docx(tmp_path / "a.docx")
    first = run_import(owner, DocxDirectorySource(root=tmp_path), now=NOW)
    second = run_import(owner, DocxDirectorySource(root=tmp_path), now=NOW)

    assert (first.created, second.created, second.skipped) == (1, 0, 1)
    assert Node.objects.count() == 1
