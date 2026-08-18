"""The scheduled pass: extract concepts, then look for connections.

**This is the thing cron calls**, and it exists because nothing did. Concept
extraction and detection had been management commands since the knowledge core
arrived, and production ran exactly one scheduled job — the due-task digest. So
a node was stored, indexed and date-parsed, and then nothing looked at it again.
Every detector was built, tested, green, and never invoked.

A wrapper rather than a third implementation. `extract_concepts` and
`run_detectors` keep their own logic, including the deliberate detector ordering
and the graceful handling of an unavailable encoder; this decides *who* and
*when* and writes down that it happened.

**It takes no owner by default.** A cron line naming one person is a cron line
that silently does nothing for the next person who signs up, and that failure is
invisible precisely because the system is supposed to be quiet.

`embed_nodes` is deliberately not called. Sentence embeddings need
`sentence-transformers`, which is optional and not installed in production —
see `requirements-embeddings.txt` and `mind.embeddings.encoder_available`. The
semantic-echo detector reports itself unavailable on `/numbers/` rather than
failing here, which is the honest arrangement while that dependency stays out of
the production image.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mind import services
from mind.models import Node


class Command(BaseCommand):
    help = "Run the scheduled extraction and detection pass."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            help="Just this person. Omit to cover everybody with notes.",
        )
        parser.add_argument(
            "--since-days",
            type=int,
            default=30,
            help=(
                "How far back to look. The default overlaps a nightly run "
                "generously on purpose: re-proposing is idempotent, and a "
                "missed night should heal itself rather than leave a gap."
            ),
        )

    def handle(self, *args, **options):
        User = get_user_model()
        if options["owner"]:
            try:
                owners = [User.objects.get(username=options["owner"])]
            except User.DoesNotExist:
                raise CommandError(f"no user named {options['owner']!r}")
        else:
            # Only people with something to work on. An account with no notes
            # has had no maintenance done to it, and recording a pass for it
            # would make the "last run" reading on /numbers/ a lie for every
            # dormant account.
            owners = list(
                User.objects.filter(
                    pk__in=Node.objects.filter(
                        deleted_at__isnull=True, archived_at__isnull=True
                    ).values("owner")
                )
            )

        if not owners:
            self.stdout.write("No corpora to maintain.")
            return

        since_days = options["since_days"]
        # The third loop of this shape, after the digest's and the purge's.
        # `run_detectors` handles `Unavailable` and nothing else, so one
        # corpus raising anything else ended the pass -- and every owner
        # sorting after them got no maintenance and no marker, which
        # `/numbers/` then reports as never maintained. True, and silent about
        # why.
        failed = []
        for owner in owners:
            username = owner.get_username()
            self.stdout.write(f"— {username}")
            try:
                call_command(
                    "extract_concepts", owner=username, since_days=since_days,
                    verbosity=options["verbosity"],
                )
                call_command(
                    "run_detectors", owner=username, since_days=since_days,
                    verbosity=options["verbosity"],
                )
            except Exception as error:
                failed.append(username)
                self.stderr.write(self.style.ERROR(f"  {username}: {error}"))
                continue
            # Last, and only on the way out: the record says a pass *completed*.
            # Written before the work, it would report health for a run that
            # died halfway, which is the reading this exists to make honest.
            # A failed corpus therefore gets no marker, deliberately -- that is
            # the same guarantee, not a gap in it.
            services.record_maintenance_run(
                owner, now=timezone.now(), actor="scheduler"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Maintained {len(owners) - len(failed)} corpus/corpora."
            )
        )

        # After the summary, so a partial pass still says how much of it
        # worked -- the same order the digest command uses.
        if failed:
            raise CommandError("maintenance failed for: " + ", ".join(failed))
