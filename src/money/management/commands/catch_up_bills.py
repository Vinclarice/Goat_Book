"""Create the bill occurrences that have come due — increment 6 of
`design/bill-as-a-model-plan.md`.

**Why a command and not a read.** `principles.md` asks that reads and writes
stay distinct, and this writes. Putting it in `money.open_bills_for` would have
made every page load of the agenda, the day and the digest a write, and would
have hidden a durable side effect behind a GET.

**Why not folded into the digest**, which already runs hourly and already walks
every user: bills would then stop appearing for anybody who turned email off,
which is a dependency nobody would guess at from either end.

**Hourly, and no `--owner`.** The command decides nothing about time zones —
`catch_up` compares due dates against each owner's today — so an hourly pass
simply means a newly due bill shows up within the hour rather than at whatever
o'clock a daily run happened to be. Covering everybody means an account created
tomorrow is caught up without anybody remembering to add a line to the
playbook, which is the reason `run_mind_maintenance` takes no owner either.
"""
import logging

from django.core.management.base import BaseCommand

from accounts.models import User
from money import services as bills

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create bill occurrences for periods that have elapsed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            help="Just this username. Everybody by default.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Say what would be created, and create nothing.",
        )

    def handle(self, *args, **options):
        owner = None
        if options["owner"]:
            owner = User.objects.filter(username=options["owner"]).first()
            if owner is None:
                self.stderr.write(self.style.ERROR("No such user."))
                return

        if options["dry_run"]:
            # Counted by asking for it and rolling back, rather than by a second
            # implementation that predicts what the first would do. Two versions
            # of this arithmetic is exactly the drift `principles.md` means by
            # one rule, one authoritative definition.
            from django.db import transaction

            try:
                with transaction.atomic():
                    would = bills.catch_up(owner)
                    raise _Rollback()
            except _Rollback:
                pass
            self.stdout.write(f"would create {would} occurrence(s)")
            return

        created = bills.catch_up(owner)
        # Written even when it is zero: a quiet run and a run that did not
        # happen look identical otherwise, which is how three seams in this
        # repository turned out never to have been switched on.
        self.stdout.write(f"created {created} occurrence(s)")
        if created:
            logger.info("catch_up_bills created %s occurrence(s)", created)


class _Rollback(Exception):
    """Unwinds the dry run's transaction. Never leaves this module."""
