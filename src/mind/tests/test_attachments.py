"""Switching attachments on — Track D increment 16, and **D9 answered**.

`Attachment` has existed since the first slice with a node key, a `byte_size`
and a cross-table invariant saying *a node may be attachment-only*. `capture()`
takes an `attachments` sequence and writes the rows. And **`FileField`,
`ImageField` and `request.FILES` appear nowhere in `src/`** — the fifth
un-switched-on seam the brief itself names.

**D9 asked where the bytes live, and named the deciding consideration:**
*"Export and deletion shipped August 16 exporting every owned* row *— files are
not rows, so an attachment that cannot be exported or purged breaks a promise
that currently holds."*

**Answered: the bytes are a row.** Not object storage, which the model's own
comment assumed when nothing could create one.

- **Every published promise then holds by construction.** The export ships
  every owned row, so attachments export. `purge_account` deletes rows, so
  attachments purge. The restore drill covers the database, so attachments
  restore. With object storage each of those is separate work, and a restore
  would bring back a database referencing files that are not there.
- **No fourth processor.** `/privacy/` says *"Three companies, each doing one
  job"* and DigitalOcean's paragraph already says the database is where
  everything Clarice stores lives. Object storage would make both sentences
  need editing — a published legal document, changed to suit an implementation
  detail.
- **Postgres is not a blob store, and that is the cost.** It is the right trade
  at this scale — one person, a personal corpus, a managed database that is
  backed up and restore-drilled — and the wrong one later. **The trigger for
  revisiting is a size limit that starts hurting**: video, or many users.
"""

import hashlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from mind import services
from mind.models import Attachment, Node


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def a_file(name="note.png", content=b"\x89PNG\r\n\x1a\nfake", content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def upload(client, **extra):
    return client.post(
        "/mind/", {"content": "a photo of the whiteboard", "attachment": a_file(), **extra}
    )


# ---------------------------------------------------------------------------
# The upload path, which is what was missing
# ---------------------------------------------------------------------------


def test_a_capture_can_carry_a_file(signed_in, owner):
    upload(signed_in)

    assert Attachment.objects.count() == 1


def test_the_bytes_are_kept(signed_in, owner):
    """**D9's answer, asserted directly.** The bytes are a row, so every promise
    that holds for rows holds for them."""
    upload(signed_in)

    assert Attachment.objects.get().content == b"\x89PNG\r\n\x1a\nfake"


def test_the_file_belongs_to_the_note_it_arrived_with(signed_in, owner):
    upload(signed_in)

    attachment = Attachment.objects.get()
    assert attachment.node.original_content == "a photo of the whiteboard"


def test_it_records_what_the_file_was(signed_in, owner):
    upload(signed_in)

    attachment = Attachment.objects.get()
    assert attachment.mime_type == "image/png"
    assert attachment.byte_size == len(b"\x89PNG\r\n\x1a\nfake")


def test_it_checksums_what_it_stored(signed_in, owner):
    """So a restore can be checked against what was uploaded rather than
    against a byte count, which two different files share easily."""
    upload(signed_in)

    attachment = Attachment.objects.get()
    assert attachment.checksum == hashlib.sha256(attachment.content).hexdigest()


def test_a_capture_without_a_file_still_works(signed_in, owner):
    signed_in.post("/mind/", {"content": "just a thought"})

    assert Node.objects.filter(original_content="just a thought").exists()
    assert not Attachment.objects.exists()


# ---------------------------------------------------------------------------
# Limits, because an upload path is a way in for anything
# ---------------------------------------------------------------------------


def test_something_too_large_is_refused(signed_in, owner):
    """A size limit is the whole of what stands between an upload box and the
    disk filling up, on a one-host deployment where the database and the
    application share it."""
    huge = SimpleUploadedFile(
        "big.png", b"x" * (services.MAX_ATTACHMENT_BYTES + 1), content_type="image/png"
    )

    signed_in.post("/mind/", {"content": "too big", "attachment": huge})

    assert not Attachment.objects.exists()


def test_a_note_is_still_kept_when_its_file_is_refused(signed_in, owner):
    """*Capture is durable before it is clever.* Losing the thought because the
    photo was too large is the worst possible reading of a size limit."""
    huge = SimpleUploadedFile(
        "big.png", b"x" * (services.MAX_ATTACHMENT_BYTES + 1), content_type="image/png"
    )

    signed_in.post("/mind/", {"content": "too big", "attachment": huge})

    assert Node.objects.filter(original_content="too big").exists()


def test_a_kind_nobody_offers_is_refused(signed_in, owner):
    """An allowlist rather than a denylist, for the reason every allowlist in
    this codebase exists: the next dangerous type is one nobody thought of."""
    script = SimpleUploadedFile("x.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml")

    signed_in.post("/mind/", {"content": "svg", "attachment": script})

    assert not Attachment.objects.exists()


def test_what_is_allowed_is_a_short_named_list(db):
    assert "image/png" in services.ALLOWED_ATTACHMENT_TYPES
    assert "application/pdf" in services.ALLOWED_ATTACHMENT_TYPES
    assert "image/svg+xml" not in services.ALLOWED_ATTACHMENT_TYPES


# ---------------------------------------------------------------------------
# D9's actual point: the promises that would otherwise break
# ---------------------------------------------------------------------------


def test_an_attachment_is_in_the_export(db, owner):
    """*Export shipped August 16 exporting every owned row.* Files are rows
    here, so this holds without the export knowing anything about files."""
    from accounts import export
    from django.utils import timezone

    services.capture(
        owner,
        content="a photo",
        captured_at=timezone.now(),
        source=Node.Source.WEB,
        actor="vince",
        attachments=[
            services.AttachmentSpec(
                kind="image",
                mime_type="image/png",
                byte_size=4,
                checksum="abcd",
                content=b"data",
            )
        ],
    )

    payload = export._payload(owner, now=timezone.now())

    assert payload["knowledge"]["attachments"]


def test_erasing_an_account_takes_the_files_with_it(db, owner):
    """The other half of D9. An attachment that survived a purge would break
    the promise `/privacy/` makes about deletion, in the one place a person
    would never think to check."""
    from accounts import services as account_services
    from django.utils import timezone

    services.capture(
        owner,
        content="a photo",
        captured_at=timezone.now(),
        source=Node.Source.WEB,
        actor="vince",
        attachments=[
            services.AttachmentSpec(
                kind="image",
                mime_type="image/png",
                byte_size=4,
                checksum="abcd",
                content=b"data",
            )
        ],
    )

    account_services.purge_account(owner, now=timezone.now())

    assert not Attachment.objects.exists()


def test_no_fourth_processor_was_added(db):
    """`/privacy/` says *three companies, each doing one job*, and object
    storage would have made that sentence false. The bytes being a row is what
    keeps a published document true."""
    from pathlib import Path

    policy = Path("src/accounts/templates/accounts/privacy.html").read_text(
        encoding="utf-8"
    )
    assert "Three companies" in policy


# ---------------------------------------------------------------------------
# Getting one back
# ---------------------------------------------------------------------------


def test_an_attachment_can_be_fetched(signed_in, owner):
    upload(signed_in)
    attachment = Attachment.objects.get()

    response = signed_in.get(f"/mind/files/{attachment.public_id}/")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


def test_one_person_cannot_fetch_anothers_file(client, owner, other_owner, signed_in):
    upload(signed_in)
    attachment = Attachment.objects.get()
    client.force_login(other_owner)

    assert client.get(f"/mind/files/{attachment.public_id}/").status_code == 404


def test_fetching_requires_signing_in(client, owner, signed_in):
    upload(signed_in)
    attachment = Attachment.objects.get()
    client.logout()

    response = client.get(f"/mind/files/{attachment.public_id}/")

    assert response.status_code == 302


def test_a_deleted_notes_file_is_not_served(signed_in, owner):
    """`live_nodes` is the visibility rule and a file is part of the note."""
    upload(signed_in)
    attachment = Attachment.objects.get()
    from django.utils import timezone

    services.delete_node(attachment.node, now=timezone.now(), actor="vince")

    assert signed_in.get(f"/mind/files/{attachment.public_id}/").status_code == 404
