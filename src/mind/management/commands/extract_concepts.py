"""Find the referents notes name, and record them as unconfirmed candidates.

Separate from capture for the same reason `run_detectors` is: *capture is durable
before it is clever*. Extraction is a regex over capitalised runs and would cost
almost nothing inline, but almost nothing is not nothing, and the capture path is
the one path in this system that must never acquire a way to fail.

So it is a command, which is honest about the fact that the concept layer does not
build itself. `cold-start.md` treats that layer as the whole cold-start mechanic —
a brain dump has nothing forgotten in it to discover, only unconsolidated
structure — so this is the step between capturing forty fragments and being handed
back the few things they are about.

Everything it writes is a proposal. Over-generation is the design: a false
candidate costs a row, and `queries.concept_candidates` is what keeps the surplus
from ever reaching a person.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mind import queries, services


class Command(BaseCommand):
    help = "Extract concept candidates from a person's notes."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)
        parser.add_argument(
            "--since-days",
            type=int,
            default=30,
            help="Only consider notes captured in this window.",
        )
        parser.add_argument("--all", action="store_true", help="Ignore --since-days.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be extracted without writing anything.",
        )

    def handle(self, *args, **options):
        try:
            owner = get_user_model().objects.get(username=options["owner"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"no user named {options['owner']!r}")

        now = timezone.now()
        nodes = queries.live_nodes(owner)
        if not options["all"]:
            nodes = nodes.filter(
                captured_at__gte=now - timedelta(days=options["since_days"])
            )

        total = nodes.count()
        if not total:
            self.stdout.write("No notes in range.")
            return

        if options["dry_run"]:
            # Reads the extractor directly rather than the service, so nothing is
            # written. Reports labels rather than a count, because the useful
            # question before a real run is whether the rules are picking up
            # referents or picking up sentence starts.
            from mind.extraction import extract_concepts

            known = list(
                queries.concept_candidates(owner).values_list("label", flat=True)
            )
            found: dict[str, int] = {}
            for node in nodes.iterator():
                for mention in extract_concepts(node.original_content, known_labels=known):
                    found[mention.label] = found.get(mention.label, 0) + 1

            self.stdout.write(f"Across {total} note(s), would extract:")
            for label, count in sorted(found.items(), key=lambda kv: (-kv[1], kv[0])):
                self.stdout.write(f"  {count:>3}  {label}")
            if not found:
                self.stdout.write("  nothing")
            return

        recorded = 0
        for node in nodes.iterator():
            recorded += len(services.extract_and_record_concepts(node, now=now))

        self.stdout.write(f"Across {total} note(s): recorded {recorded} new mention(s)")

        # The number that matters is not how much was extracted but how much
        # earned a question, because the gate between them is what keeps this from
        # becoming an inbox. Reporting only the first would make a noisy run look
        # productive.
        earned = queries.concept_candidates(owner)
        self.stdout.write(
            self.style.SUCCESS(f"{earned.count()} concept(s) worth asking about")
        )
        for candidate in earned[:10]:
            self.stdout.write(f"  {candidate.mention_count:>3}  {candidate.label}")
