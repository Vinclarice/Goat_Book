"""What would tell him it went wrong — S10, and **D4 answered**.

> He commits to a piece of work and writes down what he is trying to achieve
> and what would tell him it went wrong.

**Done means:** the purpose and the abandonment condition live with the
project, and are still there when he is deciding whether to continue.

`Project.purpose` shipped in `kestrel` and is the load-bearing third of this.
What still fought him is that *"what would tell him it went wrong"* went into
the purpose text or nowhere — where **the abandonment condition is
indistinguishable from the ambition, which is precisely the distinction the
story is about.**

**D4 asked whether `desired_outcome` is the same field**, since *both describe
how a project ends* and *deciding them apart risks two text areas nobody
fills*. **Answered: two fields, and the deciding argument is not aesthetic.**

**A tripwire you cannot tell from an ambition can never be checked.** Merged,
nothing can ever ask *has the abandonment condition been met?*, because nothing
can tell which half of the text is the condition. That is not a presentation
problem; it removes the only thing the field is for.

**They also have different readers.** `desired_outcome` says what done looks
like and answers *are we there?*; an abandonment condition answers *should we
stop?*, which is the question v3's *first question* release is built around —
its dispositions are continue, change, release, investigate. One field read by
both would satisfy neither.

**And D4's real risk is answered by optionality rather than by merging.**
`purpose` is already optional and staying optional, because *requiring it would
put a writing task in front of somebody who only wants to group three areas.*
The same holds here: two empty boxes cost nothing, and one confused box costs
the story.
"""

import datetime

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Project


class TheAbandonmentConditionTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "v@example.com", "a secure password"
        )
        self.project = Project.objects.create(owner=self.vince, title="The book")

    def test_a_project_can_record_what_going_wrong_looks_like(self):
        services.set_abandonment_condition(
            self.project, "three months with no chapter finished"
        )

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.abandon_if, "three months with no chapter finished"
        )

    def test_it_is_separate_from_what_done_looks_like(self):
        """**D4's answer, asserted rather than described.** A tripwire you
        cannot tell from an ambition can never be checked."""
        services.set_desired_outcome(self.project, "a finished draft")
        services.set_abandonment_condition(
            self.project, "three months with no chapter finished"
        )

        self.project.refresh_from_db()
        self.assertEqual(self.project.desired_outcome, "a finished draft")
        self.assertEqual(
            self.project.abandon_if, "three months with no chapter finished"
        )

    def test_it_starts_empty_and_stays_optional(self):
        """D4's real risk is two text areas nobody fills, and the answer is the
        one `purpose` already uses: optional, never asked for at creation."""
        self.assertEqual(self.project.abandon_if, "")

    def test_it_can_be_cleared(self):
        services.set_abandonment_condition(self.project, "something")

        services.set_abandonment_condition(self.project, "")

        self.project.refresh_from_db()
        self.assertEqual(self.project.abandon_if, "")

    def test_it_is_blank_never_null(self):
        """The contract `purpose` and `desired_outcome` already keep, so a
        client has one representation of *nothing written* rather than two."""
        self.assertIsNotNone(self.project.abandon_if)

    def test_a_project_can_carry_notes(self):
        """S10's other missing third. Not in the done-means, which turns on the
        abandonment condition -- but named in the requires, and the same shape.
        """
        services.set_project_notes(self.project, "Talked to Sam about scope.")

        self.project.refresh_from_db()
        self.assertEqual(self.project.notes, "Talked to Sam about scope.")

    def test_notes_start_empty_too(self):
        self.assertEqual(self.project.notes, "")


class StillThereWhenDecidingTest(TestCase):
    """*...and are still there when he is deciding whether to continue.*

    The second half of the done-means, and the reason a field alone would not
    finish this story: the check-in is where continuing is decided.
    """

    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "v@example.com", "a secure password"
        )
        self.project = Project.objects.create(
            owner=self.vince,
            title="The book",
            purpose="because it will not write itself",
        )
        services.set_abandonment_condition(
            self.project, "three months with no chapter finished"
        )

    def test_the_project_brief_carries_it(self):
        from lists import projects

        brief = projects.brief_for(self.vince, self.project)

        self.assertEqual(
            brief.abandon_if, "three months with no chapter finished"
        )

    def test_a_project_without_one_says_nothing_rather_than_inventing(self):
        from lists import projects

        bare = Project.objects.create(
            owner=self.vince, title="Nothing written", purpose="a reason"
        )

        self.assertEqual(projects.brief_for(self.vince, bare).abandon_if, "")
