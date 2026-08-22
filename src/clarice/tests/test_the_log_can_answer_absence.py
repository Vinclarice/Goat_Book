"""Whether the log was looking — **D5, answered August 22, 2026**.

> **D5. Can the log answer absence?** *"Since then, nothing has been recorded"*
> is honest only if the log can prove it was looking. `MAINTENANCE_RAN` is the
> precedent. **Part 3's sobriety refusal is the same decision** in the place a
> person will feel it.

**Answered: yes, and it needs no new row.** The log's own other events are the
proof. If a note produced nothing in six months and the log holds four hundred
other events over those months, the silence is about the note — the person was
here, recording, and this thought went nowhere. If the log holds *nothing at
all* for those months, the silence is about the log, and the note page must not
present it as a fact about the thought.

**Pure derivation, which is why the answer is yes rather than "add an event".**
`MAINTENANCE_RAN` is the precedent for *a machine proving it ran*, and it had to
be written down because a pass that finds nothing leaves no other trace. **A
person leaves traces constantly** — every completion, every capture, every
confirmation — so the evidence already exists and writing a heartbeat beside it
would be a row a read could have produced, which Part 1 forbids.

**This is the third axis to get the same discipline, and the shape is now
settled.** Track C counts `nights_not_recorded`; D17's `this_time_before`
separates a *silent year* from one *before the record*; this separates
*nothing came of it* from *nobody was here*. All three refuse to let an empty
result mean whatever the reader assumes.

**And it is built on D16**, like everything on this axis: *days you were
recording* is a count of calendar days, and a calendar day belongs to whoever
lived it.
"""

import datetime

from django.test import TestCase

from clarice import recall
from clarice.testing import make_area, make_event, make_node, make_task, make_user
from mind.models import EventType


NEW_YORK = "America/New_York"

WROTE_IT = datetime.datetime(2026, 3, 1, 15, 0, tzinfo=datetime.timezone.utc)
NOW = datetime.datetime(2026, 5, 1, 15, 0, tzinfo=datetime.timezone.utc)


def days_later(days, hour=15):
    return WROTE_IT.replace(hour=hour) + datetime.timedelta(days=days)


class TheLogCanSayWhetherItWasLookingTest(TestCase):
    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.area = make_area(self.vince)
        self.note = make_node(self.vince, when=WROTE_IT)

    def elsewhere(self, when, text=None):
        """An event with nothing to do with the note — the evidence itself."""
        # Unique per call including the hour: `create_item` refuses a
        # duplicate in one area, and two of these tests place two events on
        # one day on purpose.
        task = make_task(self.area, text or f"Something else ({when:%Y-%m-%d %H%M})")
        return make_event(self.vince, EventType.TASK_COMPLETED, when, task=task)

    def test_a_silent_log_is_named_as_a_silent_log(self):
        """**The case D5 exists for.** Nothing came of the note, and nothing
        came of anything — so the page cannot say this is a fact about the
        note."""
        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertFalse(came_of_it.attendance.was_looking)
        self.assertIn("nothing else was recorded", came_of_it.absence_says)

    def test_a_busy_log_makes_the_silence_mean_something(self):
        """The other half, and the half that makes the read worth having: the
        person was here throughout and this thought still went nowhere. That
        is a real finding rather than an absence of data."""
        for day in (3, 10, 25, 40):
            self.elsewhere(days_later(day))

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertTrue(came_of_it.attendance.was_looking)
        self.assertEqual(came_of_it.attendance.days_recorded, 4)
        self.assertIn("you were recording on 4", came_of_it.absence_says)

    def test_two_events_on_one_day_are_one_day(self):
        """Days, not events. *You were recording on 60 of 61 days* and *you
        recorded 60 things in one afternoon* are different claims about how
        much silence means, and only the first is the one being made."""
        self.elsewhere(days_later(3, hour=14))
        self.elsewhere(days_later(3, hour=18))

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertEqual(came_of_it.attendance.days_recorded, 1)

    def test_it_counts_the_days_in_the_window_too(self):
        """A denominator, for the reason Track C states: a count whose
        denominator is unstated is a count somebody reads as *of all days*."""
        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertEqual(came_of_it.attendance.days, 62)

    def test_a_note_that_did_develop_claims_no_absence(self):
        """There is no absence to explain, so there is no sentence. A page that
        printed one anyway would be answering a question nobody asked."""
        task = make_task(self.area, "The thing it became")
        make_event(self.vince, EventType.TASK_COMPLETED, days_later(4), task=task)
        from mind.models import Facet, FacetKind, InferenceOrigin

        Facet.objects.create(
            node=self.note,
            kind=FacetKind.ACTIONABLE,
            origin=InferenceOrigin.EXPLICIT,
            task=task,
            confirmed_at=days_later(1),
            data={},
        )

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertTrue(came_of_it.has_anything)
        self.assertEqual(came_of_it.absence_says, "")

    def test_another_persons_activity_is_not_evidence_you_were_here(self):
        priya = make_user("priya", time_zone=NEW_YORK)
        make_event(
            priya,
            EventType.TASK_COMPLETED,
            days_later(3),
            task=make_task(make_area(priya)),
        )

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertFalse(came_of_it.attendance.was_looking)

    def test_activity_before_the_note_is_not_evidence_either(self):
        """The window starts where the question does. Somebody who used Clarice
        heavily and then stopped the day they wrote this is exactly the case
        that must not read as *you were here throughout*."""
        self.elsewhere(days_later(-20))

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertFalse(came_of_it.attendance.was_looking)

    def test_the_day_boundary_is_the_owners(self):
        """**D16 underneath D5.** Two events at 22:00 and 23:00 in New York are
        the 3rd and the 4th in UTC, and they are one evening."""
        self.elsewhere(days_later(3, hour=2))   # 21:00 local, the day before
        self.elsewhere(days_later(3, hour=3))   # 22:00 local, the same evening

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertEqual(came_of_it.attendance.days_recorded, 1)


class TheNotePageSaysItTest(TestCase):
    """The read carries the sentence; the page prints it. Track C's rule about
    a count and its meaning not travelling separately."""

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.vince.set_password("a secure password")
        self.vince.save()
        self.note = make_node(self.vince, when=WROTE_IT)
        self.client.force_login(self.vince)

    def test_the_page_says_whether_the_log_was_looking(self):
        body = self.client.get(f"/mind/notes/{self.note.public_id}/").content.decode()

        assert "Nothing has grown out of this note" in body
        # Capitalised on the page, because it follows a full stop and reads as a
        # fragment otherwise. The read owns the sentence; the template owns
        # whether it starts a new one.
        assert "Nothing else was recorded" in body


class ReviewingIsNotADevelopmentTest(TestCase):
    """**Found in a browser, minutes after D15 wired the review loop.**

    `since()` follows recorded provenance and matches on `node=node`, so the
    `REVIEWED` event D15 introduced landed under *What came of it* — the note
    page reported *reviewed* as something the note had grown into.

    **It is not.** Saying *keep showing me this* is an act about a note's
    attention, not a development of the thought. `since()` refuses a shared
    concept and a close embedding for the same reason: *presenting them as "what
    came of this" would be a similarity score wearing a causal word.* This is
    the same slide with a housekeeping row instead.

    **And it silently ate D5's sentence**, which is what makes it worth a test
    rather than a tidy-up: any note somebody had ever answered about now had
    `has_anything` true, so the page stopped saying whether the log had been
    looking and started implying something had come of the note. Two decisions
    answered an hour apart, and the second broke the first.
    """

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.note = make_node(self.vince, when=WROTE_IT)

    def test_answering_a_resurfaced_note_is_not_something_it_grew_into(self):
        from mind import services

        services.mark_reviewed(
            self.note,
            response=services.ReviewResponse.KEPT,
            now=days_later(5),
            actor="vince",
        )

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertEqual(came_of_it.developments, [])

    def test_and_the_absence_sentence_survives_it(self):
        from mind import services

        services.mark_reviewed(
            self.note,
            response=services.ReviewResponse.KEPT,
            now=days_later(5),
            actor="vince",
        )

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertNotEqual(came_of_it.absence_says, "")

    def test_a_revision_is_still_a_development(self):
        """The line is *about the note* versus *the thought moved*. A rewrite is
        the thought moving, and dropping it would over-correct."""
        from mind import services

        services.revise(
            self.note, body="Actually it was the other thing.",
            now=days_later(5), actor="vince",
        )

        came_of_it = recall.since(self.vince, self.note, now=NOW)

        self.assertEqual(len(came_of_it.developments), 1)
