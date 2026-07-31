from django.db import models


class Capture(models.Model):
    """A thought, typed and forgotten about -- text and a timestamp, nothing else.

    Deliberately isolated from lists.List/lists.Item: no FK either way (see
    design/roadmap.md, Track B). The whole point of the MVP is that writing
    something down must never force a categorisation decision at the moment
    of writing, and a FK to a list would do exactly that.

    ``resolved_at`` is the one concession to the Inbox being finite: null
    means "still in the inbox", a timestamp means it's been dealt with
    somehow. What "dealt with" turns into -- promote to a task, an idea, a
    someday -- is the triage design the roadmap checkpoint exists to defer,
    so nothing here records which of those happened.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="captures",
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

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

    def __str__(self):
        return self.text
