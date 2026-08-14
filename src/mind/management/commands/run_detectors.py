"""Run the detectors over recent notes.

Separate from capture, and that is the point rather than a limitation. *Capture is
durable before it is clever*: a thought must never wait on similarity search, a model
file, or a slow machine. So capture writes and returns, and proposing happens here.

A real deployment wants this on a queue or a schedule. Until then it is a command, which
is honest about the fact that nothing proposes anything unless something runs it.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mind import queries
from mind.detectors import (
    propose_concept_assignments,
    propose_dormant_threads,
    propose_open_questions,
    propose_semantic_echoes,
    propose_shared_referents,
)
from mind.detectors.semantic_echo import Unavailable


class Command(BaseCommand):
    help = "Propose connections for a person's recent notes."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)
        parser.add_argument(
            "--since-days",
            type=int,
            default=30,
            help="Only consider notes captured in this window. Detectors look "
            "backwards from a note, so re-scanning the whole corpus every run "
            "mostly re-derives what the fingerprint constraint will reject anyway.",
        )
        parser.add_argument("--all", action="store_true", help="Ignore --since-days.")
        parser.add_argument("--dry-run", action="store_true")

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

        detectors = {
            # First, and deliberately. It is the only one here that can say
            # anything from a cold start, and its proposals feed the concept
            # layer the others read -- so a run that assigns before it looks for
            # connections is a run whose later detectors have more to work with.
            "concept_assignment": propose_concept_assignments,
            "open_question": propose_open_questions,
            "dormant_thread": propose_dormant_threads,
            "shared_referent": propose_shared_referents,
            "semantic_echo": propose_semantic_echoes,
        }
        counts = dict.fromkeys(detectors, 0)
        unavailable: set[str] = set()

        for node in nodes.iterator():
            for name, propose in detectors.items():
                if name in unavailable:
                    continue
                try:
                    if options["dry_run"]:
                        # Nothing is written, so the count is what *would* be
                        # proposed. Useful before tuning a threshold against live
                        # accept rates, which a real run would pollute.
                        from mind.detectors import (
                            find_concept_assignments,
                            find_dormant_threads,
                            find_open_questions,
                            find_semantic_echoes,
                            find_shared_referents,
                        )

                        finder = {
                            "concept_assignment": find_concept_assignments,
                            "open_question": find_open_questions,
                            "dormant_thread": find_dormant_threads,
                            "shared_referent": find_shared_referents,
                            "semantic_echo": find_semantic_echoes,
                        }[name]
                        counts[name] += len(finder(node, now=now))
                    else:
                        counts[name] += len(propose(node, now=now))
                except Unavailable:
                    # No vectors for this model version. Reported once rather than
                    # per note, and the other detectors carry on.
                    unavailable.add(name)

        prefix = "would propose" if options["dry_run"] else "proposed"
        self.stdout.write(f"Across {total} note(s):")
        for name, count in counts.items():
            if name in unavailable:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {name}: unavailable — no sentence vectors. "
                        "Run `manage.py embed_nodes` first."
                    )
                )
            else:
                self.stdout.write(f"  {name}: {prefix} {count}")

        pending = queries.pending_hypotheses(owner).count()
        self.stdout.write(self.style.SUCCESS(f"{pending} proposal(s) awaiting review"))
