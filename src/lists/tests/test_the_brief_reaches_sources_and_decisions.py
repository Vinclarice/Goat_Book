"""Notes, decisions **and sources** — **S16, the other two nouns**.

> Vince starts a project on a topic he worked on eighteen months ago. Without
> asking, Clarice offers what he learned last time.

**Done means:** opening the project surfaces **notes, decisions and sources**
from previous work on that topic, each saying why it surfaced, and nothing is
changed on his behalf.

The brief has reached **notes only** since `kestrel`, and S16's verdict said why:
*"`Source` (S15) and `Decision` (S11) do not exist, so 'notes, decisions and
sources' is one of three."* **Both shipped on August 22, 2026**, hours apart,
and this is the clause they unblock.

**Reached through recorded provenance, never through a second similarity
index.** A source is here because a note the brief already surfaced *came from*
it; a decision is here because it *cites* one. Both are columns somebody wrote,
which means:

- **the reason is a fact rather than a score** — *you read this, and this note
  came out of it* — which is what the done-means asks for and what
  `material_bearing_on` fought for with its rare-term gate;
- **nothing new has to be indexed**, and no threshold has to be defended;
- **it cannot drift**, because it follows the same chain `since()` follows.

**What that refuses**, deliberately and in the same words `since()` uses: a
source whose *title* resembles the project's purpose is not reached. Matching on
it would be a similarity score wearing a causal word, and it is available only
by building the thing this design has twice declined to build.

**The cost is that a thin corpus reaches nothing, and the brief says so.** Both
columns got their first writing surface the day before this, so almost nothing
carries provenance yet. An empty section that cannot distinguish *nothing bears
on this* from *nothing records where it came from* would be the absence problem
D5 answered one axis over.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from accounts.models import User
from lists import projects as project_reader
from lists import services
from lists.models import List
from mind import services as mind_services
from mind.models import NodeSource


UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
TODAY = date(2026, 6, 1)

PURPOSE = (
    "Replace the enquiries inbox with a booking form so the venue stops "
    "losing bookings to email."
)

#: Shares the purpose's rare terms, so `material_bearing_on` reaches it. The
#: retrieval is not what is under test here — that it reaches *this note* is
#: assumed, and asserted once below so a failure elsewhere is legible.
BEARS_ON_IT = (
    "The enquiries inbox is losing bookings again — three this month went to "
    "email and nobody saw them. A booking form is the only thing that fixes it."
)


class TheBriefReachesSourcesAndDecisionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", due_date=TODAY + timedelta(days=30),
            purpose=PURPOSE,
        )
        List.objects.create(owner=self.user, title="Site", project=self.project)

    def capture(self, content=BEARS_ON_IT, days_ago=400, came_from=None):
        """Deliberately far back — S16's own sentence is *eighteen months ago*.

        `came_from` is set at capture rather than afterwards, which is the
        application's only way to set it: `/mind/sources/<id>/` captures into a
        source you are reading, so provenance is recorded at the moment it is
        known rather than reconstructed later.
        """
        return mind_services.capture(
            self.user,
            content=content,
            captured_at=NOW - timedelta(days=days_ago),
            source=NodeSource.WEB,
            actor="alice",
            came_from=came_from,
        )

    def brief(self):
        return project_reader.brief_for(self.user, self.project)

    def a_source(self, title="Booking systems for small venues"):
        return mind_services.record_source(
            self.user, title=title, author="Someone", now=NOW - timedelta(days=420)
        )

    # -- the retrieval this is layered on, asserted once ---------------------

    def test_the_note_is_reached_at_all(self):
        """Not S16's content — a guard, so that a failure in the sections below
        is legible as *the source was not attached* rather than *the retrieval
        found nothing*."""
        self.capture()

        assert self.brief().material or self.brief().questions

    # -- sources -------------------------------------------------------------

    def test_a_source_behind_a_surfaced_note_is_offered(self):
        source = self.a_source()
        self.capture(came_from=source)

        offered = [each.source for each in self.brief().sources]

        assert offered == [source]

    def test_it_says_why_the_source_is_here(self):
        """*Each saying why it surfaced.* A fact rather than a score: the note
        that came out of it is the whole reason, and the person can check it."""
        source = self.a_source()
        self.capture(came_from=source)

        (offered,) = self.brief().sources

        assert "came out of it" in offered.reason

    def test_a_source_behind_nothing_the_brief_reached_is_not_offered(self):
        """The narrowing is the retrieval's, not a second one. A source whose
        notes have nothing to do with this project is not *about* the project
        because it exists."""
        source = self.a_source()
        self.capture(
            "Sourdough hydration percentages and the overnight fridge prove.",
            came_from=source,
        )
        self.capture()

        assert self.brief().sources == []

    def test_a_source_matching_only_by_its_title_is_refused(self):
        """**The refusal, in the same words `since()` uses.** This source's
        title is about booking forms and enquiries; nothing of the person's
        came out of it. Reaching it would be a similarity score wearing a
        causal word, and would need an index this design has twice declined to
        build."""
        self.a_source("Replace your enquiries inbox with a booking form")
        self.capture()

        assert self.brief().sources == []

    def test_one_source_appears_once_however_many_notes_it_produced(self):
        """Tested against the grouping directly rather than through the
        retrieval, and the reason is worth recording: **three near-identical
        notes reach the brief not at all.** The rare-term gate counts document
        frequency, so three notes sharing the purpose's terms make those terms
        ordinary and the gate rejects the lot — the mechanism that took the
        lexical detector from 11% to 67% precision, working exactly as designed.

        A fixture bent until it defeated that gate would be testing a corpus
        shape the application never produces. So the grouping is asserted where
        it lives, and the integration above uses one note.
        """
        source = self.a_source()
        nodes = [
            self.capture(f"{BEARS_ON_IT} Note {n}.", came_from=source)
            for n in range(3)
        ]

        (grouped,) = project_reader._sources_behind(nodes)

        assert grouped.source == source
        assert len(grouped.through) == 3
        assert "3 notes here came out of it" in grouped.reason

    def test_it_does_not_reach_another_persons_source(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        theirs = mind_services.record_source(
            bob, title="Theirs", author="", now=NOW - timedelta(days=420)
        )
        self.capture()

        assert theirs not in [each.source for each in self.brief().sources]

    # -- decisions -----------------------------------------------------------

    def test_a_decision_citing_a_surfaced_note_is_offered(self):
        node = self.capture()
        decision = mind_services.record_decision(
            self.user,
            question="how do we take bookings?",
            chose="a form on the site",
            considered="keep the inbox and triage it",
            cites=node,
            now=NOW - timedelta(days=390),
        )

        assert [each.decision for each in self.brief().decisions] == [decision]

    def test_it_says_why_the_decision_is_here(self):
        node = self.capture()
        mind_services.record_decision(
            self.user, question="q", chose="c", considered="", cites=node,
            now=NOW - timedelta(days=390),
        )

        (offered,) = self.brief().decisions

        assert "while looking at" in offered.reason

    def test_a_decision_citing_nothing_is_not_offered(self):
        """Not every decision comes out of something written down, and a
        decision with no citation has no recorded path to this project. Guessing
        one from its wording is the refusal above, in the other model."""
        self.capture()
        mind_services.record_decision(
            self.user, question="unrelated", chose="something",
            considered="", now=NOW - timedelta(days=390),
        )

        assert self.brief().decisions == []

    def test_a_superseded_decision_still_comes_with_it(self):
        """*What he learned last time* includes the answer he later changed. A
        brief that showed only the surviving decision would hide the part that
        makes the record worth keeping."""
        node = self.capture()
        first = mind_services.record_decision(
            self.user, question="q", chose="the first answer", considered="",
            cites=node, now=NOW - timedelta(days=390),
        )
        mind_services.record_decision(
            self.user, question="q", chose="the second answer", considered="",
            cites=node, supersedes=first, now=NOW - timedelta(days=200),
        )

        assert len(self.brief().decisions) == 2

    def test_it_does_not_reach_another_persons_decision(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        node = self.capture()
        mind_services.record_decision(
            bob, question="theirs", chose="theirs", considered="",
            now=NOW - timedelta(days=390),
        )

        assert self.brief().decisions == []

    # -- nothing is changed on his behalf ------------------------------------

    def test_reading_the_brief_still_records_nothing(self):
        """The third of the done-means, and it must survive two new sections.
        A brief assembles what is already the person's, so there is no window to
        start and no inaction to interpret."""
        from mind.models import ActivityEvent

        source = self.a_source()
        self.capture(came_from=source)
        before = ActivityEvent.objects.count()

        self.brief()

        assert ActivityEvent.objects.count() == before


class TheBriefSaysWhatItCouldNotReachTest(TestCase):
    """**A thin corpus reaches nothing, and an empty section says neither why.**

    `Node.came_from` and `Decision.cited_node` both got their first writing
    surface on August 21–22, so almost nothing carries provenance yet. *No
    sources bear on this* and *none of your notes record where they came from*
    are different facts, and the second is the true one today. Same discipline
    as D5, one axis over.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", purpose=PURPOSE,
        )
        List.objects.create(owner=self.user, title="Site", project=self.project)

    def capture(self, content=BEARS_ON_IT, came_from=None):
        return mind_services.capture(
            self.user, content=content, captured_at=NOW - timedelta(days=400),
            source=NodeSource.WEB, actor="alice", came_from=came_from,
        )

    def test_it_says_when_nothing_records_where_it_came_from(self):
        self.capture()

        says = project_reader.brief_for(self.user, self.project).provenance_says

        assert "where they came from" in says

    def test_it_stops_saying_so_once_something_does(self):
        source = mind_services.record_source(
            self.user, title="A source", author="", now=NOW - timedelta(days=420)
        )
        self.capture(came_from=source)

        says = project_reader.brief_for(self.user, self.project).provenance_says

        assert "where they came from" not in says


class TheBriefCarriesTheAbandonmentConditionTest(TestCase):
    """**S10's second clause, which the brief has been dropping.**

    `ProjectBrief.abandon_if` has been set since S10 shipped, with a docstring
    saying *"a field nobody sees at the moment of deciding is a field that may as
    well not exist"* — and the API payload never carried it, so nobody saw it.
    **The object warning against the bug had the bug.** Found while adding the
    two sections above, in the same file.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", purpose=PURPOSE,
        )
        services.set_abandonment_condition(
            self.project, "three months with no booking taken through it"
        )
        self.client.force_login(self.user)

    def test_the_brief_endpoint_carries_it(self):
        payload = self.client.get(
            f"/api/v1/projects/{self.project.id}/brief"
        ).json()

        assert payload["abandon_if"] == (
            "three months with no booking taken through it"
        )
