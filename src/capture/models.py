from django.db import models


class Idea(models.Model):
    """Something worth keeping that is not a task.

    One model with a status rather than two models, because "an idea I want
    to explore" and "a concept I want to be able to find again" are the same
    shape of object -- text, no due date, no done/not-done -- differing only
    in lifecycle stage. Same reasoning that kept subtasks a self-FK on Item
    instead of a parallel table.

    An idea never gains a due date or a completion state. If it turns out to
    be actionable, it gets promoted into a task, and the task is the live
    record from then on.
    """

    class Status(models.TextChoices):
        EXPLORING = "exploring", "Exploring"
        REFERENCE = "reference", "Reference"
        PROMOTED = "promoted", "Promoted"

    owner = models.ForeignKey(
        "accounts.User", related_name="ideas", on_delete=models.CASCADE
    )
    text = models.TextField()
    # Plain text, not Markdown -- same trade as Item.notes: a renderer plus
    # an XSS surface buys little at this scale.
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EXPLORING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    promoted_task = models.ForeignKey(
        "lists.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # lists.Tag, not a parallel model -- same field Capture.tags already is,
    # same shared vocabulary. design/second-mind-discovery-plan.md 4.1.
    tags = models.ManyToManyField("lists.Tag", blank=True, related_name="ideas")

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            # Backs the library view's only query: this owner's ideas,
            # narrowed by status -- either to one the person picked or by
            # excluding Promoted, which is the default -- in created_at
            # order. Same shape as Capture's Inbox index below, because it
            # is the same kind of scan.
            #
            # Added ahead of the feature that will lean on it: release E's
            # ranked search reads exactly this table, and an index costs a
            # line now against a migration on a grown table later. It does
            # not serve the substring `q` filter, and is not meant to --
            # that one needs full-text or trigram support, which is release
            # E's decision to make, not this index's job to pre-empt.
            models.Index(
                fields=("owner", "status", "-created_at"),
                name="idea_owner_status_idx",
            ),
        ]

    def __str__(self):
        return self.text


class Capture(models.Model):
    """A thought, typed and forgotten about -- text and a timestamp, nothing else.

    No FK *into* capture from lists, and nothing in lists imports this: the
    isolation that matters is that writing something down never forces a
    categorisation decision at the moment of writing. The FKs below point
    the other way and only ever get set later, during triage, which is
    precisely when a decision has been made.

    ``resolved_at`` says whether it's still in the Inbox; ``resolution``
    says what it became. Both, rather than one: a capture can be resolved
    into nothing at all (discarded), and "gone from the inbox" and "became
    a task" are different facts.
    """

    class Resolution(models.TextChoices):
        TASK = "task", "Task"
        IDEA = "idea", "Idea"
        DISCARDED = "discarded", "Discarded"

    owner = models.ForeignKey(
        "accounts.User",
        related_name="captures",
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution = models.CharField(
        max_length=20, choices=Resolution.choices, blank=True
    )
    # Two FKs answering two different questions. This one: did this raw
    # thought become a task directly?
    promoted_task = models.ForeignKey(
        "lists.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # And this one: did it become an idea first? A capture that went
    # Capture -> Idea -> Task has this set and promoted_task null forever,
    # with Idea.promoted_task carrying the second hop. Each link only ever
    # tracks one hop forward, which is what keeps the lineage readable.
    promoted_idea = models.ForeignKey(
        "Idea",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # A mobile client's retry identity, not the server's. Optional --
    # browser captures (the Inbox form) never send one, and that path is
    # unchanged. Scoped per owner rather than globally unique so two
    # different clients can't collide on the same UUID by coincidence, and
    # left NULL for the common case: Postgres (and every backend Django
    # supports) treats NULL as distinct from every other NULL in a unique
    # constraint by default, so any number of keyless captures coexist
    # exactly as before this field existed.
    idempotency_key = models.UUIDField(null=True, blank=True)
    # lists.Tag, not a parallel model -- see design/capture-tags-plan.md 2.
    # Optional at capture time by design: writing something down must never
    # force a categorisation decision.
    tags = models.ManyToManyField(
        "lists.Tag", blank=True, related_name="captures"
    )

    class Meta:
        # Newest first: the Inbox reads as a stack of what you just wrote,
        # not a backlog you work from the bottom of. Tie-broken on id so
        # two captures saved in the same tick still order deterministically.
        ordering = ("-created_at", "-id")
        indexes = [
            # Backs the only query there is: the Inbox's
            # (owner, still-unresolved) scan in created_at order.
            models.Index(
                fields=("owner", "resolved_at", "-created_at"),
                name="capture_owner_inbox_idx",
            ),
        ]
        constraints = [
            # The actual retry-safety guarantee: two rows can never share
            # an (owner, key) pair, so a concurrent retry either creates
            # the one row or loses a race and finds it already there --
            # see services.create_capture_idempotent. NULL keys are exempt from this
            # by ordinary SQL NULL semantics, not a special case here.
            models.UniqueConstraint(
                fields=("owner", "idempotency_key"),
                name="capture_owner_idempotency_key_uniq",
            ),
        ]

    def __str__(self):
        return self.text
