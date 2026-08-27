from django.db import models


class WeeklyReview(models.Model):
    """What somebody concluded about one week, and what they meant to do next.

    The review app's only stored record. Everything else it serves is
    derived from tables that already existed -- charter rule 5, reference
    rather than copy -- because a week is a lens over durable records and
    not a second place to keep them. What cannot be derived is the part a
    person writes.

    **Why the counts are here at all**, which looks like the rule-5
    violation it is not. `DailyFocus` snapshots `task_text`, so the planned
    denominator survives a task being permanently deleted from the archive;
    that is the number `daily-operating-system-vision.md` says "cannot be
    reconstructed after the fact". The numerator has no such protection --
    it is read through `DailyFocus.task`, which `delete_archived_item`
    leaves NULL -- so a live recount of a reviewed week can quietly fall
    afterwards. A completed review is a record of what somebody concluded
    on a day, and it carries its own copy of the figure they concluded it
    from. That is charter rule 3, snapshot what a record's meaning depends
    on, applied to a conclusion rather than to a target.

    They are null until the review is completed, and null again if it is
    reopened, because an unfinished review has concluded nothing.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1: `owner` is direct and non-null in this first migration.
    - Rule 2: no UUID. Nothing writes a review offline -- the Android
      client captures and nothing else -- so there is no identity to
      reconcile.
    - Rule 3: the recorded counts above.
    - Rule 6: no delete path, deliberately, and for the same reason a day
      has none. A review emptied of text stays as a row: "I reviewed that
      week and had little to say" and "I never reviewed that week" are
      different facts, and a product that could not tell them apart would
      be unable to say whether the practice is happening at all. Deleting
      an account still cascades.
    - Rule 7: the unique constraint below is the index. Every read is
      "this owner, this week", which it covers exactly.
    - Rule 8: does not apply. A week recurs in the calendar sense but has
      no template holding a rule, and inventing one would be the overload
      that rule exists to prevent -- the same call `DailyEntry` made.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="weekly_reviews",
        on_delete=models.CASCADE,
    )
    # The Monday the week starts on, always from
    # routines.periods.period_start_for. Any date in the week addresses the
    # same record, so two links to one week cannot make two rows -- see
    # crane-plan.md §6 on why a second definition of "this week" would be
    # wrong in a way nobody would see.
    week_start = models.DateField()
    # Plain text, blank rather than null, exactly as the day's three fields
    # are: "wrote nothing" and "cleared it" are the same state, so nothing
    # downstream has to handle both.
    reflections = models.TextField(blank=True, default="")
    # What the coming week was for, and **nothing writes this any more** --
    # `planning-assistant-v2-plan.md` D7, August 26, 2026. `WeeklyIntention`
    # answers that question now; this page was asking it twice, a few hundred
    # pixels apart, and the intention is the one with a life cycle because the
    # Day page reads it all week.
    #
    # **Kept rather than dropped, and this is not a dark seam.** Rows written
    # before that date hold a person's own sentence about a week, which §4's
    # rule 6 keeps for the same reason `WeeklyReview` has no delete path at all:
    # what somebody said on a Sunday is history, not state. It is still read --
    # `ReviewOut` returns it and the review page renders it read-only where one
    # exists -- so "unused column, drop it" is the wrong reading and
    # `review/tests/test_the_plan_field_is_retired.py` fails if anybody acts on
    # it.
    #
    # The original reasoning, still true of what is stored: deliberately a
    # person's sentence rather than a list of tasks the system would then own.
    # The vision document asks for "a short planning area", and anything that
    # scheduled work from here would be the automatic rescheduling it forbids.
    plan = models.TextField(blank=True, default="")
    # When the week was reviewed. Null means still open, which is not the
    # same as never started -- the row exists because something was written.
    completed_at = models.DateTimeField(null=True, blank=True)
    recorded_planned_total = models.PositiveIntegerField(null=True, blank=True)
    recorded_planned_met = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Most recent first, like the day: the weeks worth reopening are
        # the recent ones.
        ordering = ("-week_start",)
        constraints = [
            # One week, one review, one person. Enforced here rather than
            # by a service remembering to check, because two rows for one
            # week would surface as a plan that silently vanished.
            models.UniqueConstraint(
                fields=("owner", "week_start"),
                name="unique_weekly_review_per_owner_week",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: week of {self.week_start}"


class WeeklyIntention(models.Model):
    """What a person decided a week was *for*, written before or during it.

    S9 -- "On Sunday she decides what the week is about. On Wednesday the day
    knows." Planning existed only at day scale, which `product-stories.md`
    calls a hole in a product whose pitch is "design the future", and which
    `planning-assistant-plan.md` increment 6 cannot draft a week without.

    **Its own model rather than a field on WeeklyReview**, which is keyed
    identically and would have been the cheap answer. Two reasons, and the
    second is the one that settles it:

    - **Different life cycles**, which is `architecture-trajectory.md` §4's
      actual test. An intention is a commitment made before a week; a review is
      a conclusion drawn after one.
    - **`WeeklyReview`'s existence is itself a fact.** It has no delete path
      precisely so "I reviewed that week and had little to say" stays
      distinguishable from "I never reviewed that week". Writing an intention
      into it would create rows for weeks nobody reviewed, and that model would
      stop being able to say whether the practice is happening -- the only
      thing its row-presence is for.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1, owned at birth: `owner` is non-null in this first migration.
    - Rule 2, public identifier: none. No client writes a week offline -- the
      Android app captures and nothing else -- so there is no identity to
      reconcile. Revisit if one ever does.
    - Rule 3, snapshot: nothing to snapshot. The text is its own meaning and
      depends on no other row. Note the contrast with `WeeklyReview`, which
      records counts precisely because a *conclusion* depends on figures that
      can move underneath it; an intention concludes nothing.
    - Rule 5, reference never copy: nothing is duplicated. A day displays this
      text; it does not own a copy that could drift.
    - Rule 6, deletion: no delete path, the same call `DailyEntry` and
      `WeeklyReview` both make. An intention cleared to empty stays as a row,
      because "I set none this week" and "I never opened it" are different
      facts and only one of them says the practice lapsed. Deleting an account
      still cascades.
    - Rule 7, index the query: the unique constraint below is the index. Every
      read is "this owner, this week", which it covers exactly.
    - Rule 8, template and occurrences: does not apply. A week recurs in the
      calendar sense but holds no rule, and inventing one would be the overload
      that rule exists to prevent -- the same call `DailyEntry` made.

    Kept in the `review` app because that app already owns what a week *is*
    (`review/weeks.py`). A second home would mean a second definition of when a
    week starts, and two answers to that is the drift `crane-plan.md` §6 warns
    about.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="weekly_intentions",
        on_delete=models.CASCADE,
    )
    # The Monday the week starts on, always from routines.periods
    # via review.weeks -- never a raw date from a caller. Any day of the week
    # addresses the same record, which is what lets Wednesday read what Sunday
    # wrote.
    week_start = models.DateField()
    # Plain text, blank rather than null, exactly as the day's three fields
    # are: "wrote nothing" and "cleared it" are the same state, so nothing
    # downstream has to handle both. No Markdown, per roadmap.md's settled
    # boundary.
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-week_start",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "week_start"),
                name="unique_weekly_intention_per_owner_week",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: intention for week of {self.week_start}"


class PlanningSession(models.Model):
    """That somebody sat down and planned a week — v2 increment 4.

    **Its existence is the fact**, which is the whole reason it is a row and
    not a flag. `WeeklyReview` has no delete path so that *"I reviewed that
    week and had little to say"* stays distinguishable from *"I never reviewed
    that week"*; the same distinction is the only way to answer whether the
    planning ritual is actually happening. Without it there is no denominator
    for whether v2 worked, and a planner nobody opens looks identical to one
    that had nothing to say.

    **Written by an act, never by a page view.** `review.reads` must not write,
    and a session recorded when the review loaded would make every refresh a
    planning session -- which would destroy the only number this model exists
    to produce. It is created by an explicit POST when somebody starts the
    check-in.

    **`unusual` lives here rather than on `WeeklyIntention`**, which is keyed
    identically and which `planning-assistant-v2-plan.md` originally named. The
    plan was written before this record existed. An intention is *what the week
    is for* and survives the week; this is a correction somebody makes **while
    planning**, to what the system believed about their capacity. If nobody
    plans, there is no correction to record -- which is exactly the life-cycle
    test §4 asks, and it lands this on the session.

    **It does not compete with the derived figure.** `typical_week_for` remains
    the authority on what a week holds; this says only that *this* week is not
    a typical one, and nothing multiplies the two together. A declared number
    standing beside a derived one is two authorities for one rule, which
    `principles.md` refuses -- so what is stored is a direction, stated back to
    the person, and no coefficient is invented.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1, owned at birth: `owner` is non-null in this first migration.
    - Rule 2, public identifier: none. No client plans a week offline.
    - Rule 3, snapshot: nothing yet. A session that has only *started* has
      concluded nothing, so there is no figure whose movement could rewrite its
      meaning. When confirming a plan lands, what it was confirmed against is
      exactly what will need stamping -- the call `WeeklyReview` already makes
      for its counts, and for the same reason.
    - Rule 5, reference never copy: the week's intention, capacity and projects
      are all read live. This copies none of them.
    - Rule 6, deletion: no delete path, the same call `WeeklyReview`,
      `DailyEntry` and `WeeklyIntention` all make. Deleting an account still
      cascades.
    - Rule 7, index the query: the unique constraint below is the index, and
      "this owner, this week" is the only read there is.
    - Rule 8, template and occurrences: does not apply, for `WeeklyIntention`'s
      reason exactly.
    """

    class Unusual(models.TextChoices):
        """How this week differs from a typical one, in the person's words.

        Named for what is scarce rather than for how the week *feels*: a
        "lighter week" means less work to some people and more free time to
        others, and a planner cannot afford that ambiguity.
        """

        USUAL = "usual", "About usual"
        LESS_TIME = "less_time", "Less time than usual"
        MORE_TIME = "more_time", "More time than usual"

    owner = models.ForeignKey(
        "accounts.User",
        related_name="planning_sessions",
        on_delete=models.CASCADE,
    )
    # The Monday of the week being *planned*, from review.weeks like every
    # other week-keyed record here -- never a raw date from a caller.
    week_start = models.DateField()
    unusual = models.CharField(
        max_length=16, choices=Unusual, default=Unusual.USUAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-week_start",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "week_start"),
                name="unique_planning_session_per_owner_week",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: planned week of {self.week_start}"


class WeeklyOutcome(models.Model):
    """A thing a person decided would be true by the end of a week.

    **D3, answered: outcomes and intentions are different questions.** An
    intention is one sentence about what a week is *for* and survives the week
    as context a Wednesday reads; an outcome is one of two or three concrete
    things that will be true by Friday, each chosen separately, each carrying
    the evidence that put it on the list. One record per owner per week could
    not hold several, and folding them together would mean the sentence and the
    commitments shared a confirmation state -- which is exactly the collapse
    §4's life-cycle test exists to catch.

    **Nothing here is generated.** The proposal is a *project* plus the facts
    that make it this week's, and the sentence offered is the project's own
    `desired_outcome` -- the person's words, which is why that field was added
    in increment 3. D1 defers composed prose and this surface does not need it:
    what a model would add is a rephrasing, and a rephrasing of somebody's own
    sentence is the least defensible generation in the plan.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1, owned at birth: `owner` is non-null in this first migration.
    - Rule 2, public identifier: none. Nothing plans a week offline.
    - Rule 3, snapshot: `project_title` is copied at confirmation. An outcome
      that read its project's title live would be silently rewritten by a
      rename, and "what I committed to three weeks ago" is exactly the kind of
      history `RoutineOccurrence.target_quantity` copies for. The FK stays as a
      reference for reaching the project, and goes SET_NULL rather than taking
      the outcome with it -- deleting a project does not unmake the week you
      spent on it.
    - Rule 5, reference never copy: the project's *current* state is read live
      wherever it is shown. Only what gives this record its meaning is copied.
    - Rule 6, deletion: **hard delete, and this model is the exception to the
      week-keyed pattern around it.** `WeeklyReview`, `DailyEntry`,
      `WeeklyIntention` and `PlanningSession` all keep their rows because their
      *existence* answers "did this practice happen" -- and here
      `PlanningSession` already answers that. An outcome is a chosen thing;
      choosing three and dropping one is ordinary editing, not rewriting
      history, and a tombstone would make the week's own list unreadable.
    - Rule 7, index the query: the constraint below covers "this owner, this
      week, in order", which is the only read.
    - Rule 8, template and occurrences: does not apply.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="weekly_outcomes",
        on_delete=models.CASCADE,
    )
    # The Monday of the week this is an outcome *for*, from review.weeks.
    week_start = models.DateField()
    # The person's own words. Seeded from the project's `desired_outcome` when
    # one is confirmed from a proposal, and editable afterwards -- an outcome
    # for a week is not the same sentence as the project's standing definition
    # of done, even when it starts as a copy of it.
    text = models.TextField()
    # What it came from, when it came from something. Null for one written from
    # nothing, which is allowed: a week can be about something that is not a
    # project.
    project = models.ForeignKey(
        "lists.Project",
        related_name="weekly_outcomes",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # Rule 3. What the project was called when this was chosen, so a rename
    # cannot rewrite what somebody committed to.
    project_title = models.CharField(max_length=100, blank=True, default="")
    # The order they were chosen in, which is the order they are shown in. Not
    # a priority: the plan is explicit that ranking work is the person's, and a
    # number the system sorted by would become one.
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("week_start", "position", "id")
        indexes = [
            models.Index(
                fields=("owner", "week_start", "position"),
                name="outcome_owner_week_idx",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: {self.text[:40]} (week of {self.week_start})"
