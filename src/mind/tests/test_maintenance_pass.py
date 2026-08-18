"""The scheduled pass, and being able to tell whether it ever happened.

Concept extraction and detection were management commands that nothing invoked.
Production ran one cron job and it was the due-task digest, so on the live site
a node was stored, indexed for full-text search and parsed for a date — and then
nothing. No concepts, no proposals, no graph. Every detector was built, tested,
green, and switched off.

The instrumentation could not report this, which is the sharper half. `/numbers/`
was built precisely so silence would be legible: `detector_readiness` separates
*found nothing* from *cannot run yet*. Neither is the state the system was
actually in — **can run, never asked** — so the one instrument designed to catch
exactly this class of problem could not see it.

So two things here. A command a scheduler can call for everybody, and a record
that it ran, because "ran and found nothing" and "never ran" are the distinction
the whole numbers page exists to draw.
"""

import logging
from datetime import timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from mind import instrumentation, services
from mind.models import ActivityEvent, EventType, NodeSource

pytestmark = pytest.mark.django_db

# Relative to the real clock, not a fixed date. The pass looks back a bounded
# number of days, so a hardcoded capture date silently drifts out of range as
# the calendar moves -- which is exactly how two `lists` tests rotted into
# asserting a defect, and it happened here on the first run of this file.
def now():
    return timezone.now()


def capture(owner, text, ago=timedelta(0)):
    return services.capture(
        owner, content=text, captured_at=now() - ago,
        source=NodeSource.WEB, actor="vince",
    )


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------


def test_it_runs_for_everybody_without_being_told_who(owner, other_owner):
    """A cron line naming one person is a cron line that silently does nothing
    for the next person to sign up."""
    capture(owner, "the woman upstairs is called Marguerite")
    capture(other_owner, "The Gravity is a good car")

    call_command("run_mind_maintenance")

    for person in (owner, other_owner):
        assert ActivityEvent.objects.filter(
            owner=person, event_type=EventType.MAINTENANCE_RAN
        ).exists()


def test_one_person_can_be_named(owner, other_owner):
    capture(owner, "the woman upstairs is called Marguerite")
    capture(other_owner, "The Gravity is a good car")

    call_command("run_mind_maintenance", owner=owner.get_username())

    assert not ActivityEvent.objects.filter(
        owner=other_owner, event_type=EventType.MAINTENANCE_RAN
    ).exists()


def test_one_owners_failure_does_not_cost_everybody_after_them_a_pass(
    owner, other_owner, caplog
):
    """The third loop of this shape, after the digest's and the purge's.
    `run_detectors` catches `Unavailable` and nothing else, so anything the
    extraction or detection of one corpus raised aborted the command -- and
    every owner sorting after them got no maintenance and, because the marker
    is written last and deliberately, no marker either. `/numbers/` would then
    report them as never maintained, which is true and says nothing about why.
    """
    import mind.management.commands.run_mind_maintenance as command_module

    capture(owner, "the woman upstairs is called Marguerite")
    capture(other_owner, "The Gravity is a good car")

    real = command_module.call_command
    failed_for = owner.get_username()

    def fail_for_one(name, *args, **kwargs):
        if name == "run_detectors" and kwargs.get("owner") == failed_for:
            raise RuntimeError("the index went away mid-pass")
        return real(name, *args, **kwargs)

    with mock.patch.object(command_module, "call_command", side_effect=fail_for_one):
        with pytest.raises(CommandError) as raised:
            with caplog.at_level(logging.ERROR):
                call_command("run_mind_maintenance")

    # Logged as well as caught -- see the note at the command's logger. A
    # guarded loop reports through logging or it reports nowhere: the
    # CommandError we raise is swallowed by BaseCommand.run_from_argv.
    [failure] = [r for r in caplog.records if r.levelname == "ERROR"]
    assert failure.exc_info is not None

    assert ActivityEvent.objects.filter(
        owner=other_owner, event_type=EventType.MAINTENANCE_RAN
    ).exists()
    assert not ActivityEvent.objects.filter(
        owner=owner, event_type=EventType.MAINTENANCE_RAN
    ).exists()
    assert failed_for in str(raised.value)


def test_somebody_with_no_notes_is_skipped(owner, other_owner):
    """Not an empty pass recorded as a pass. An account with nothing in it has
    had no maintenance done to it, and saying otherwise would make the liveness
    reading below a lie for every dormant account."""
    capture(owner, "the woman upstairs is called Marguerite")

    call_command("run_mind_maintenance")

    assert not ActivityEvent.objects.filter(
        owner=other_owner, event_type=EventType.MAINTENANCE_RAN
    ).exists()


def test_it_actually_extracts_concepts(owner):
    """The point of running it at all. Three mentions across two days is what
    the gravity gate asks for before a candidate earns a question."""
    for day, text in enumerate(
        # Never sentence-initial. Extraction skips a leading capital on
        # purpose -- every sentence starts with one, so treating those as names
        # would make the gravity gate meaningless. Getting this wrong is what
        # made this test fail first time round.
        [
            "the woman upstairs is called Marguerite",
            "left a note for Marguerite about the boiler",
            "spoke to Marguerite about the roof again",
        ]
    ):
        # Spread across days, because the gravity gate wants three mentions
        # spanning at least one -- four in a single sitting is one moment of
        # attention, not a recurring concern.
        capture(owner, text, ago=timedelta(days=2 - day))

    call_command("run_mind_maintenance")

    assert ActivityEvent.objects.filter(
        owner=owner, event_type=EventType.CONCEPT_PROPOSED
    ).exists()


def test_a_second_pass_does_not_duplicate_what_the_first_found(owner):
    """Cron runs this every night forever. A pass that re-proposed everything
    it already proposed would turn the review into an inbox by the weekend."""
    for day in range(3):
        capture(owner, f"spoke to Marguerite about the roof, note {day}",
                ago=timedelta(days=2 - day))
    call_command("run_mind_maintenance")
    after_first = ActivityEvent.objects.filter(
        owner=owner, event_type=EventType.CONCEPT_PROPOSED
    ).count()

    call_command("run_mind_maintenance")

    assert ActivityEvent.objects.filter(
        owner=owner, event_type=EventType.CONCEPT_PROPOSED
    ).count() == after_first


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------


def test_before_anything_runs_the_answer_is_never(owner):
    capture(owner, "the woman upstairs is called Marguerite")

    assert instrumentation.last_maintenance_run(owner) is None


def test_after_a_pass_the_time_is_reported(owner):
    capture(owner, "the woman upstairs is called Marguerite")

    call_command("run_mind_maintenance")

    assert instrumentation.last_maintenance_run(owner) is not None


def test_the_summary_carries_it_so_the_page_can_show_it(owner):
    """`lab_summary` says it holds "everything worth knowing about whether the
    lab is working". Whether the lab has ever been asked to work is part of
    that, and was the one part missing."""
    capture(owner, "the woman upstairs is called Marguerite")

    summary = instrumentation.lab_summary(owner, now=now())

    assert "last_maintenance_run" in summary
    assert summary["last_maintenance_run"] is None


def test_the_numbers_page_says_so_in_words(client, owner):
    """A timestamp nobody renders is the same as no timestamp. This is the
    failure that hid for a day: the instrument existed and the page did not
    show it."""
    capture(owner, "the woman upstairs is called Marguerite")
    client.force_login(owner)

    response = client.get("/mind/numbers/")

    assert b"never" in response.content.lower()
