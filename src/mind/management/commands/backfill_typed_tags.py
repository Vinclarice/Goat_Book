"""Turn tags already on the activity log into concepts.

Until step 1 of `one-capture-surface-plan.md`, a tagged mobile capture wrote its
labels onto an `ActivityEvent` under the note *"tags kept, not yet modelled"* —
deliberately not discarding what somebody typed, while having nowhere to put it.
Those events are a real record of real decisions and this is what puts them
where they belong.

**One-time and idempotent.** `record_typed_tags` reuses an existing concept and
refuses to double a mention, so a second run changes nothing. That matters more
than usual here: this reads the append-only log, which cannot be marked as
processed, so re-running is the only recovery from a partial run.

The event's own `occurred_at` is used rather than now. These tags were typed
when the note was captured, and the concept layer measures recurrence across
time — stamping a backfill with today's date would collapse months of history
onto one afternoon and tell the gravity gate a lie.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mind import services
from mind.models import ActivityEvent, EventType

# What the placeholder wrote. Matched on the note rather than on the presence of
# a `tags` key, so this cannot pick up some future event that happens to carry
# one for another reason.
PLACEHOLDER_NOTE = "tags kept, not yet modelled"


class Command(BaseCommand):
    help = "Convert tags recorded on the activity log into confirmed concepts."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Just this person. Omit for everybody.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be converted without writing.",
        )

    def handle(self, *args, **options):
        events = ActivityEvent.objects.filter(
            event_type=EventType.CAPTURED,
            payload__note=PLACEHOLDER_NOTE,
            node__isnull=False,
        ).select_related("node", "owner")

        if options["owner"]:
            try:
                owner = get_user_model().objects.get(username=options["owner"])
            except get_user_model().DoesNotExist:
                raise CommandError(f"no user named {options['owner']!r}")
            events = events.filter(owner=owner)

        events = list(events.order_by("occurred_at"))
        if not events:
            self.stdout.write("No tags waiting on the log.")
            return

        labels = sum(len(e.payload.get("tags") or []) for e in events)
        self.stdout.write(f"{len(events)} event(s), {labels} tag(s)")

        if options["dry_run"]:
            for event in events:
                self.stdout.write(
                    f"  {event.occurred_at:%Y-%m-%d}  "
                    f"{', '.join(event.payload.get('tags') or [])}"
                )
            self.stdout.write("Dry run: nothing written.")
            return

        mentions = 0
        for event in events:
            mentions += len(
                services.record_typed_tags(
                    event.node,
                    event.payload.get("tags") or [],
                    # The moment the tag was typed, not now. Recurrence is
                    # measured across time and a backfill stamped today would
                    # collapse months onto one afternoon.
                    now=event.occurred_at,
                    actor="backfill",
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"{mentions} mention(s) now on the graph")
        )
