import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Appointment(models.Model):
    """Something that happens at a time whether or not you act.

    `superlists-2.0-plan.md`'s *Appointment*, and the model
    [`clarice-v3-plan.md`](../../design/clarice-v3-plan.md) argued for as `Event`
    on August 20, 2026 against `architecture-trajectory.md` §4's test -- *a
    concept earns its own model when it has a different life cycle, not when it
    has a different name*. This one does: **it happens at a time whether or not
    you act, and is never completed.** A task you did not do is unfinished; a
    dentist appointment you did not attend still happened to the afternoon.

    **The name is D1, answered by using Vince's word.** *"I think an appointment
    should have its own model. This should include events such as me going to
    Dutch Wonderland this weekend."* `Engagement` is the more exact English for
    any fixed claim on time and reads better over a theme park; `Event` is taken
    twice in the knowledge core -- `ActivityEvent`, `EventType` -- and a third
    meaning would make every reader disambiguate. What settled it is that the
    field list is identical under all three, so the only thing at stake is which
    word a person reads, and the person is Vince. §7's precedent stands if that
    ever changes: the boundary may say a different word without the table
    moving.

    **A span with an optional time of day, not an instant.** That example
    settles the shape -- no time, two days, attended rather than finished. The
    Day page is keyed on the owner's local date decided at the request boundary;
    an all-day event stored as midnight UTC lands on the wrong day away from
    Greenwich, and a weekend stored as two instants is a pair of datetimes
    pretending to be two dates.

    **Charter compliance** (`architecture-trajectory.md` §4), rule by rule, as
    the plan states them:

    - **Rule 1, owned at birth**: `owner` is direct and non-null in the first
      migration.
    - **Rule 2, public identifier**: included now, because the Android
      full-client direction is live in `roadmap.md` and identity cannot be
      retrofitted onto records a device already holds.
    - **Rule 3, snapshot**: nothing external to snapshot. Text, span and
      location are the record's own meaning. If `location` later references a
      place concept -- D6 -- the name is copied at that point.
    - **Rule 4, reads and services from the first slice**: its own app, on the
      `routines` precedent, with `reads.py` and `services.py` split from the
      first commit.
    - **Rule 5, reference never copy**: the day reads appointments for its date
      live; nothing is written onto `DailyEntry`.
    - **Rule 6, deletion**: two states with two meanings. *Cancelled* is a fact
      about a life and stays visible on its day, struck. *Deleted* is a typo,
      soft, and is the tombstone rule 2 requires. No hard delete outside
      `purge_account`.
    - **Rule 7, index the query**: `(owner, starts_on)` serves the day, the week
      ahead and the pool's fixed lines.
    - **Rule 8, template and occurrences**: **deliberately not in the first
      cut.** A weekly standup wants a series template; the nullable foreign key
      it needs is added when one exists, and nothing here changes to allow it.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    #: Client-suppliable, so a device that made this offline keeps its identity.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    text = models.CharField(max_length=200)

    # -- the span ---------------------------------------------------------
    #
    # Dates and a separate time, never an aware datetime. See the class note.
    starts_on = models.DateField()
    #: Null means one day. Not defaulted to `starts_on`, because *"this is a
    #: one-day thing"* and *"this runs from the 5th to the 5th"* are the same
    #: fact said twice, and a column that can disagree with itself will.
    ends_on = models.DateField(null=True, blank=True)
    #: Null means all day -- the Dutch Wonderland case, and the reason this is
    #: not a datetime.
    starts_at = models.TimeField(null=True, blank=True)
    #: Null means *no stated end*, which is the ordinary case for an
    #: appointment somebody wrote down in five seconds. It is not a duration of
    #: zero.
    ends_at = models.TimeField(null=True, blank=True)

    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # -- how it ends, rule 6 ----------------------------------------------
    #
    #: Called off. **Stays visible on its day, struck**: a cancelled Thursday
    #: afternoon is a fact about that Thursday, and a row that vanished would
    #: make *"the parents' evening was cancelled"* unanswerable a month later.
    cancelled_at = models.DateTimeField(null=True, blank=True)
    #: A typo, removed. Soft, because rule 2's public identifier needs a
    #: tombstone: a device that has the id must not be able to recreate the row
    #: by retrying.
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Soonest first, then by time of day, with all-day ones ahead of timed
        # ones on the same date -- an all-day thing frames the day the timed
        # ones sit inside. Nulls sort first on `starts_at` in Postgres ASC only
        # with an explicit direction, so it is stated rather than inherited.
        ordering = ("starts_on", models.F("starts_at").asc(nulls_first=True), "id")
        constraints = [
            # A span that ends before it starts is not a span. Cheap to say
            # here and impossible to say later, once rows exist that break it.
            models.CheckConstraint(
                condition=Q(ends_on__isnull=True) | Q(ends_on__gte=models.F("starts_on")),
                name="appointment_span_ends_after_it_starts",
            ),
            # An end time on something with no start time is an end to nothing.
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(starts_at__isnull=False),
                name="appointment_end_time_needs_a_start_time",
            ),
        ]
        indexes = [
            models.Index(fields=("owner", "starts_on"), name="appointment_owner_start"),
        ]

    def __str__(self):
        return f"{self.starts_on}: {self.text}"

    @property
    def last_day(self):
        """The last date this covers. `ends_on` or, for a one-day thing, its
        own start -- so callers never have to write that ``or`` themselves.
        """
        return self.ends_on or self.starts_on

    @property
    def is_all_day(self):
        return self.starts_at is None
