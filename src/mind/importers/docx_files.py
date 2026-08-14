"""Word documents — which, on this machine, is where the actual corpus is.

A survey of the machine found no Obsidian vault, no markdown notes, and no
note-app export. What it did find was a flat archive of ~200 readable `.docx`
files spanning 2011 to 2026: a commonplace book, journals, goal documents,
trading notes, drafts. That is the corpus, so this is the adapter that matters.

Two facts about it shape the code:

**`dcterms:created` is reliable and is a real instant.** Every readable file in
the archive carries it in `docProps/core.xml`, in ISO 8601 with a `Z`. It is
therefore timezone-*aware* — unlike almost every other source — and needs no
interpretation against the owner's zone.

**Filesystem mtime is actively wrong here and is never consulted.** OneDrive sync
has rewritten these files: a 2022 document carries an mtime in 2026. An adapter
that fell back to file metadata would confidently misdate a decade of personal
writing, which is the exact failure the import path exists to prevent. When the
document properties are missing, this adapter yields nothing rather than guess.

Encrypted documents are reported, not skipped in silence. Password-protected Word
files store an OLE `EncryptedPackage`, which hides the text *and* the metadata —
so nothing at all is recoverable from them without the password.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence
from xml.etree import ElementTree

from .base import SourceRecord, TimeQuality
from .jsonl import parse_timestamp

# OLE compound-file magic. A .docx is a zip; when it is this instead, the file is
# an encrypted package wrapping the real document.
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

CORE_PROPERTIES = "docProps/core.xml"
DOCUMENT_BODY = "word/document.xml"

DCTERMS = "{http://purl.org/dc/terms/}"
DC = "{http://purl.org/dc/elements/1.1/}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# A date on its own near the top of the body, which many of these documents open
# with. Used only as a cross-check against the metadata, never as the primary.
BODY_DATE = re.compile(
    r"^\s*((?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4})\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def is_encrypted(path: Path) -> bool:
    """True for a password-protected document.

    Cheap to check and worth checking: an encrypted file is a valid OLE
    container, so `zipfile` fails on it with an error that reads like corruption
    rather than like a locked door.
    """
    try:
        with open(path, "rb") as handle:
            return handle.read(8) == OLE_MAGIC
    except OSError:
        return False


def read_core_properties(archive: zipfile.ZipFile) -> dict[str, str]:
    """The document's own metadata: created, modified, creator, title."""
    try:
        raw = archive.read(CORE_PROPERTIES)
    except KeyError:
        return {}

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return {}

    found: dict[str, str] = {}
    for tag, key in (
        (f"{DCTERMS}created", "created"),
        (f"{DCTERMS}modified", "modified"),
        (f"{DC}creator", "creator"),
        (f"{DC}title", "title"),
        (f"{DC}subject", "subject"),
    ):
        element = root.find(tag)
        if element is not None and element.text:
            found[key] = element.text.strip()
    return found


def extract_text(archive: zipfile.ZipFile) -> str:
    """Body text, one line per paragraph.

    Deliberately plain: runs are concatenated, tabs and breaks become
    whitespace, and everything else — styling, comments, revision marks — is
    dropped. What a detector needs is the words.
    """
    try:
        raw = archive.read(DOCUMENT_BODY)
    except KeyError:
        return ""

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return ""

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{W}p"):
        pieces: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{W}t" and node.text:
                pieces.append(node.text)
            elif node.tag in (f"{W}tab", f"{W}br"):
                pieces.append(" ")
        line = "".join(pieces).strip()
        if line:
            paragraphs.append(line)

    return "\n\n".join(paragraphs)


@dataclass
class DocxDirectorySource:
    """Word documents in a directory.

    `skipped` accumulates what was passed over and why — encrypted files above
    all — so the caller can report it rather than have the count vanish. It is
    only complete once iteration finishes.
    """

    root: Path
    name: str = "docx"
    recursive: bool = False
    """The real archive is flat. Recursion is opt-in because these directories
    also contain thousands of photos and videos in subfolders."""

    exclude: Sequence[str] = ()
    """Case-insensitive substrings matched against the filename. The archive is
    mixed: coursework and admin paperwork sit beside personal writing, and
    filtering by name is cruder than reading each one but costs nothing."""

    cross_check_body_date: bool = True
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def records(self) -> Iterator[SourceRecord]:
        self.skipped = []
        root = Path(self.root)
        pattern = "**/*.docx" if self.recursive else "*.docx"

        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.name.startswith("~$"):
                continue  # ~$ prefixes are Word's lock files

            relative = path.relative_to(root).as_posix()

            if any(term.lower() in path.name.lower() for term in self.exclude):
                self.skipped.append((relative, "excluded by name"))
                continue

            if is_encrypted(path):
                # Neither text nor metadata is readable — core.xml is inside the
                # encrypted payload — so there is genuinely nothing to salvage.
                self.skipped.append((relative, "password protected"))
                continue

            record = self._to_record(path, relative)
            if record is not None:
                yield record

    def _to_record(self, path: Path, relative: str) -> SourceRecord | None:
        try:
            with zipfile.ZipFile(path) as archive:
                properties = read_core_properties(archive)
                text = extract_text(archive)
        except (zipfile.BadZipFile, OSError) as exc:
            self.skipped.append((relative, f"unreadable: {exc}"))
            return None

        created = parse_timestamp(properties.get("created")) or parse_timestamp(
            properties.get("modified")
        )
        if created is None:
            # No fallback to file metadata, deliberately: OneDrive sync has
            # rewritten mtime across this archive, so guessing from it would
            # misdate the material rather than merely fail to date it.
            self.skipped.append((relative, "no creation date in document properties"))
            return None

        quality = (
            TimeQuality.AWARE if created.tzinfo is not None else TimeQuality.LOCALISED
        )

        if self.cross_check_body_date:
            stated = self._body_date(text)
            if stated is not None and stated.year != created.year:
                # Word metadata gets reset by "save as" and by some converters,
                # while a date the person typed at the top of the page does not.
                # Trust the typed one and say that it was used.
                self.skipped.append(
                    (
                        relative,
                        f"body date {stated:%Y-%m-%d} overrode properties "
                        f"{created:%Y-%m-%d}",
                    )
                )
                created, quality = stated, TimeQuality.LOCALISED

        title = properties.get("title") or path.stem

        return SourceRecord(
            external_id=relative,
            content=text,
            captured_at=created,
            quality=quality,
            title=title,
            extra={
                "path": relative,
                "creator": properties.get("creator"),
                "word_count": len(text.split()),
            },
        )

    @staticmethod
    def _body_date(text: str):
        """A date on its own line in the opening of the document."""
        head = "\n".join(text.splitlines()[:6])
        match = BODY_DATE.search(head)
        # Passed through as written: parse_timestamp handles the comma and its
        # absence as separate formats, so stripping it here would only defeat
        # the one that expects it.
        return parse_timestamp(match.group(1)) if match else None
