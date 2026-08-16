"""The entry points.

Commands are kept thin here and their pieces tested directly, so this file only
covers what a thin command can still get wrong: not being wired to anything.

That is not hypothetical. `services.extract_and_record_concepts` existed, was
tested, and was called by nothing outside its own tests — so no concept candidate
was ever created in real use, and the layer `cold-start.md` makes the whole
cold-start mechanic could not have worked however good it was. A test that runs
the command end to end is the cheapest guard against that recurring.

Regression guards rather than a failing-test-first cycle, and said plainly per
this project's own rule about tests that pass on their first run.
"""

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from mind import queries
from mind.models import ConceptCandidate, Mention, Node

pytestmark = pytest.mark.django_db


def _run(command, *args, **options):
    """Positional arguments stay positional.

    `call_command` maps keywords onto option strings, and a positional argument
    has none -- passing one by name fails with `min() iterable argument is
    empty`, which names neither the command nor the argument.
    """
    from io import StringIO

    out = StringIO()
    call_command(command, *args, stdout=out, **options)
    return out.getvalue()


def test_extraction_reaches_real_notes(owner, make_node):
    """The guard the missing caller needed.

    Note the names sit mid-sentence. `extraction` deliberately ignores a
    capitalised word at a sentence start, because that position says nothing
    about whether it names anything -- so a corpus where every mention opens a
    sentence extracts nothing, which is correct and surprising enough to be
    worth writing down here.
    """
    make_node("Practised with Mondly again this evening", captured="2026-03-01")
    make_node("Going better with Mondly today", captured="2026-03-04")

    _run("extract_concepts", owner=owner.username, all=True)

    assert ConceptCandidate.objects.filter(owner=owner, label="Mondly").exists()
    assert Mention.objects.count() >= 2


def test_it_reports_what_earned_a_question_not_just_what_was_found(owner, make_node):
    """Two numbers, because they answer different things. A run that extracts
    forty names and surfaces none of them is working correctly, and a report of
    only the first would make that look productive."""
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        make_node(f"Practised Indonesian on {day}", captured=day)
    # Seen once: extracted, and deliberately never asked about.
    make_node("A note about Reykjavik", captured="2026-03-02")

    output = _run("extract_concepts", owner=owner.username, all=True)

    assert "Indonesian" in output
    assert "Reykjavik" not in output
    assert [c.label for c in queries.concept_candidates(owner)] == ["Indonesian"]


def test_a_dry_run_writes_nothing(owner, make_node):
    """The point of a dry run is deciding whether the rules are picking up
    referents or picking up sentence starts, and a run that pollutes the corpus
    to tell you cannot be repeated."""
    make_node("Practised with Mondly again this evening", captured="2026-03-01")

    output = _run("extract_concepts", owner=owner.username, all=True, dry_run=True)

    assert "Mondly" in output
    assert not ConceptCandidate.objects.exists()
    assert not Mention.objects.exists()


def test_extraction_is_idempotent(owner, make_node):
    """Re-running is ordinary — after every capture, or after changing a rule —
    so a second pass must not double every mention it already recorded."""
    make_node("Practised with Mondly again this evening", captured="2026-03-01")

    _run("extract_concepts", owner=owner.username, all=True)
    first = Mention.objects.count()
    _run("extract_concepts", owner=owner.username, all=True)

    assert Mention.objects.count() == first


def test_it_will_not_silently_do_nothing_for_an_unknown_person(owner):
    """A typo'd username that reported "no notes in range" would look like an
    empty corpus rather than a mistake."""
    with pytest.raises(CommandError):
        _run("extract_concepts", owner="nobody-by-that-name")


def test_another_persons_notes_are_not_extracted(owner, other_owner, make_node):
    from mind.models import Node

    Node.objects.create(
        owner=other_owner,
        original_content="Reykjavik and Mondly and Indonesian",
        captured_at=timezone.now(),
        source=Node.Source.WEB,
    )

    _run("extract_concepts", owner=owner.username, all=True)

    assert not ConceptCandidate.objects.filter(owner=other_owner).exists()
    assert not Mention.objects.exists()


# ---------------------------------------------------------------------------
# Moving a corpus in from the standalone project
# ---------------------------------------------------------------------------


def _dump(tmp_path, records):
    import json

    path = tmp_path / "dump.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def _node_record(pk, public_id, owner_pk, content="a thought from elsewhere"):
    return {
        "model": "mind.node",
        "pk": pk,
        "fields": {
            "public_id": public_id,
            # The source project's user id, which is a different person's row
            # number here. Re-pointing this is the whole job.
            "owner": owner_pk,
            "original_content": content,
            "captured_at": "2026-03-01T09:00:00Z",
            "created_at": "2026-03-01T09:00:00Z",
            "source": "web",
            "import_key": None,
            "archived_at": None,
            "deleted_at": None,
        },
    }


def test_a_corpus_arrives_owned_by_the_named_account(owner, tmp_path):
    """The two projects have unrelated user tables, so the id in the export
    belongs to somebody else's row number here."""
    dump = _dump(tmp_path, [_node_record(1, "11111111-1111-4111-8111-111111111111", 999)])

    _run("import_second_mind", dump, owner=owner.username)

    node = Node.objects.get()
    assert node.owner == owner
    assert str(node.public_id) == "11111111-1111-4111-8111-111111111111"


def test_public_ids_survive_the_move(owner, tmp_path):
    """A device holding one must not be stranded, and a public id is the only
    thing that says two rows are the same thought."""
    dump = _dump(tmp_path, [_node_record(7, "22222222-2222-4222-8222-222222222222", 2)])

    _run("import_second_mind", dump, owner=owner.username)

    assert Node.objects.get().pk == 7


def test_it_refuses_to_load_over_an_existing_corpus(owner, tmp_path, make_node):
    """A one-time move, not a sync. Reconciling two divergent copies is a
    different and much harder problem, and a command that attempted it quietly
    would be the wrong tool wearing the right name."""
    make_node("already here")
    dump = _dump(tmp_path, [_node_record(1, "33333333-3333-4333-8333-333333333333", 2)])

    with pytest.raises(CommandError):
        _run("import_second_mind", dump, owner=owner.username)


def test_force_is_available_for_when_that_is_actually_meant(owner, tmp_path, make_node):
    make_node("already here")
    dump = _dump(tmp_path, [_node_record(1, "44444444-4444-4444-8444-444444444444", 2)])

    _run("import_second_mind", dump, owner=owner.username, force=True)

    assert Node.objects.count() == 2


def test_credentials_are_left_behind(owner, tmp_path):
    """A token authenticates a device against a particular server, and the
    server is what this step changes. Carrying the hash across would leave a
    credential that looks valid and addresses somewhere that no longer serves.

    **`ApiToken` no longer exists** — the knowledge core's own API went with the
    crossover, and this endpoint's job is now done by the application's single
    `/api/v1/capture` on a `PersonalAccessToken`. So there is nowhere for these
    records to land even by accident, and what this asserts is the part still
    worth asserting: a dump that contains them still imports rather than
    tripping over a model that is not there.
    """
    dump = _dump(
        tmp_path,
        [
            _node_record(1, "55555555-5555-4555-8555-555555555555", 2),
            {
                "model": "mind.apitoken",
                "pk": 1,
                "fields": {
                    "owner": 2,
                    "label": "Android",
                    "token_hash": "a" * 64,
                    "display_prefix": "sm_abc",
                    "created_at": "2026-03-01T09:00:00Z",
                    "last_used_at": None,
                    "revoked_at": None,
                },
            },
        ],
    )

    out = _run("import_second_mind", dump, owner=owner.username)

    assert Node.objects.count() == 1
    # Skipped by name rather than by model, which is what makes it survive the
    # model's deletion -- and said out loud, so a dump full of credentials does
    # not silently look like a dump full of nothing.
    assert "skipped (credentials do not move)" in out


def test_a_dry_run_writes_nothing(owner, tmp_path):
    dump = _dump(tmp_path, [_node_record(1, "66666666-6666-4666-8666-666666666666", 2)])

    output = _run("import_second_mind", dump, owner=owner.username, dry_run=True)

    assert "mind.node" in output
    assert Node.objects.count() == 0


def test_an_unknown_account_is_refused_rather_than_guessed(owner, tmp_path):
    dump = _dump(tmp_path, [_node_record(1, "77777777-7777-4777-8777-777777777777", 2)])

    with pytest.raises(CommandError):
        _run("import_second_mind", dump, owner="nobody-by-that-name")
