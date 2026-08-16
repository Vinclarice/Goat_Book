"""Erase accounts whose grace period has run out.

Run daily from cron. Deleting an account is immediate in effect and delayed in
fact: `accounts.services.request_deletion` writes a timestamp and changes
nothing else, and this is what eventually makes it true.

**Reports what it would do, not what exists.** `migrate_inbox` printed its
input — every row in the table it read — so one new capture read as thirty-five
and somebody used that number to decide whether to proceed. A dry run here lists
the accounts it would take and nothing else.

**Says something on a quiet day.** A command that prints nothing when there is
nothing to do is indistinguishable from a command that did not run, which is how
a cron job stops being noticed at all.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts import services


class Command(BaseCommand):
    help = "Erase accounts whose deletion grace period has passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would be erased without touching anything.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        due = list(services.due_for_purge(now))

        self.stdout.write(f"{len(due)} account(s) past the grace period")
        for user in due:
            self.stdout.write(
                f"  {user.get_username()}  requested "
                f"{user.deletion_requested_at:%Y-%m-%d}"
            )

        if options["dry_run"]:
            self.stdout.write("Dry run: nothing erased.")
            return

        for user in due:
            username = user.get_username()
            removed = services.purge_account(user, now=now)
            total = sum(removed.values())
            # Per model, not just a total. "1,204 rows removed" cannot be
            # checked against anything; a breakdown can be read against what
            # that person actually had.
            self.stdout.write(self.style.SUCCESS(f"  erased {username}: {total} row(s)"))
            for model, count in sorted(removed.items()):
                if count:
                    self.stdout.write(f"      {count:>6}  {model}")
