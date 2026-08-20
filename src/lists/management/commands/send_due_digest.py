"""Emails each opted-in user what's overdue or due today, in their morning.

Runs hourly from cron on the server, e.g.

    0 * * * * docker exec clarice python manage.py send_due_digest

Hourly rather than once at 07:00 because users are in different time
zones: a single daily run can only be somebody's morning. The schedule no
longer expresses an intended send time at all -- it just wakes the command
up, and the command decides per recipient. That takes the server's own
zone out of the picture entirely, which is better than configuring it
correctly, since nothing then has to stay correct.

Users with nothing to report are skipped, so a quiet day stays quiet.
"""
import logging
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User
from clarice.scheduled_mail import deliver_once_a_day
from lists import agenda as agenda_reader


# The local hours a digest is considered due, as [start, end). Not a
# per-user preference yet: everyone gets their own morning, nobody gets to
# move it.
#
# The end matters as much as the start. Without it, a container that was
# down all morning delivers "Good morning, here is your day" at 20:00 --
# by which point the summary is not late, it is wrong. Past the window the
# day is written off instead: nothing sent, but recorded as decided so the
# next morning starts clean.
DIGEST_HOUR = 7
DIGEST_LAST_HOUR = 12


def _app_url(subpath):
    """An absolute link into the SPA, for a message with no request behind it.

    `settings.SITE_URL` rather than `build_absolute_uri`, which is the same
    choice `accounts/apps.py` already makes for the login link in an approval
    mail -- a management command has no request to build one against.
    """
    return f"{settings.SITE_URL}{reverse('app_shell_path', args=[subpath])}"


def _describe(item, today):
    bucket = agenda_reader.bucket_for(item.due_date, today)
    if bucket == agenda_reader.OVERDUE:
        days = (today - item.due_date).days
        when = "due yesterday" if days == 1 else f"{days} days overdue"
    else:
        when = "due today"
    # Named only when there is one. An unfiled task borrows no Area here for
    # the same reason it borrows no colour and no restore destination
    # (`0857835`): the absence of the signal rather than another value of it.
    # `list_id`, not `list`, so a task without one costs no query.
    where = f"{item.list.title}, " if item.list_id else ""
    # The link on its own line rather than inline: this is plain text, mail
    # clients linkify a bare URL, and a wrapped one mid-sentence is what stops
    # them. `commercial-blueprint.md` Part 3 -- the product's only outbound
    # channel had nothing clickable in it, so the one message that reaches
    # somebody on a phone made them go and find the task by hand.
    return "\n".join(
        [
            f"  - {item.text} ({where}{when})",
            f"    {_app_url(f'tasks/{item.id}')}",
        ]
    )


def _coming(item, today):
    days = (item.due_date - today).days
    when = "tomorrow" if days == 1 else f"in {days} days"
    where = f"{item.list.title}, " if item.list_id else ""
    return "\n".join(
        [
            f"  - {item.text} ({where}due {when})",
            f"    {_app_url(f'tasks/{item.id}')}",
        ]
    )


def build_message(user, items, coming, today):
    overdue = [
        item for item in items
        if agenda_reader.bucket_for(item.due_date, today)
        == agenda_reader.OVERDUE
    ]
    due_today = [item for item in items if item not in overdue]

    lines = [f"Good morning, {user.username}.", ""]
    if overdue:
        lines.append(f"Overdue ({len(overdue)}):")
        lines += [_describe(item, today) for item in overdue]
        lines.append("")
    if due_today:
        lines.append(f"Due today ({len(due_today)}):")
        lines += [_describe(item, today) for item in due_today]
        lines.append("")
    if coming:
        # Its own section, below what is actually due. A lead time says
        # "mention this early", not "this is due early" -- folding it into the
        # lists above would make the digest claim something is due when it is
        # not.
        lines.append(f"Coming up ({len(coming)}):")
        lines += [_coming(item, today) for item in coming]
        lines.append("")
    lines.append(f"Work through them: {_app_url('day')}")
    return "\n".join(lines)


def build_subject(items, today, coming=()):
    overdue = sum(
        1 for item in items
        if agenda_reader.bucket_for(item.due_date, today)
        == agenda_reader.OVERDUE
    )
    parts = []
    if overdue:
        parts.append(f"{overdue} overdue")
    remaining = len(items) - overdue
    if remaining:
        parts.append(f"{remaining} due today")
    # Only when there is nothing due, so a quiet week's advance warning still
    # has a subject that says something -- and a busy day's subject is not
    # diluted by a bill a week away.
    if not parts and coming:
        parts.append(f"{len(coming)} coming up")
    return f"Clarice · {date_format(today, 'M j')} · " + ", ".join(parts)


# Logged, not only written to stderr. Guarding these loops (D6/D11) stopped
# the exception propagating, and `BaseCommand.run_from_argv` catches the
# CommandError we raise instead -- so nothing reaches Sentry by exception any
# more, and cron has no MAILTO and the host no MTA, so stderr reaches nobody
# either. sentry-sdk installs LoggingIntegration by default at event level
# ERROR, so `logger.exception` restores the report without this command
# importing the SDK.
#
# Found from a real one: a 2026-08-16 SMTP connection timeout in production,
# which is the incident that proved the guard was needed and would have been
# the last one anybody heard about.
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Email opted-in users a summary of overdue and due-today tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without sending anything.",
        )
        parser.add_argument(
            "--username",
            help="Only consider this one user (useful for testing).",
        )
        parser.add_argument(
            "--send-hour",
            type=int,
            default=DIGEST_HOUR,
            help=(
                "The local hour a digest becomes due (default 7). Lowering "
                "it lets a manual run happen without waiting for morning "
                "somewhere."
            ),
        )
        parser.add_argument(
            "--until-hour",
            type=int,
            default=DIGEST_LAST_HOUR,
            help=(
                "The local hour the morning is considered over (default "
                "12, exclusive). Past it the day is written off unsent. "
                "Raise it to 24 to send at any hour."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        send_hour = options["send_hour"]
        until_hour = options["until_hour"]
        recipients = User.objects.filter(is_active=True, daily_digest=True)
        if options["username"]:
            recipients = recipients.filter(username=options["username"])

        def compose(user, today):
            items = agenda_reader.digest_items_for(user, today)
            coming = agenda_reader.coming_up_for(user, today)
            # Either alone is worth a message. Gating on `items` only would
            # leave the one channel that exists to warn you in advance silent
            # on exactly the quiet day it is for.
            if not items and not coming:
                return None
            return (
                build_subject(items, today, coming),
                build_message(user, items, coming, today),
            )

        def show(user, subject, body):
            self.stdout.write(f"--- {user.email} ({user.time_zone}) ---")
            self.stdout.write(subject)
            self.stdout.write(body)

        def send(user, subject, body):
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )

        # Every subtlety this loop used to hold in line -- the per-user zone,
        # the stamp, at-or-after, the closing window, stamping a quiet day, and
        # one recipient's failure staying theirs -- now lives in
        # `clarice.scheduled_mail`, because the evening nudge was about to copy
        # all six.
        sent, failed = deliver_once_a_day(
            recipients=recipients,
            stamp_field="last_digest_date",
            send_hour=send_hour,
            until_hour=until_hour,
            now=timezone.now(),
            compose=compose,
            deliver=show if dry_run else send,
            stamp=not dry_run,
            logger=logger,
            label="digest",
        )
        for username in failed:
            self.stderr.write(self.style.ERROR(f"  {username}: delivery failed"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
        elif sent:
            # Silent otherwise: this runs 24 times a day now, and a line
            # per run is 24 pieces of cron mail saying nothing happened.
            self.stdout.write(
                self.style.SUCCESS(f"Sent {sent} digest email(s).")
            )

        # After the summary, not before it: a partial run should still say how
        # much of it worked. Caught so the run completes, raised so a daily
        # failure is not invisible -- without this the command exits 0 having
        # delivered nothing to somebody, every morning, leaving no trace in
        # the data.
        if failed:
            raise CommandError("digest failed for: " + ", ".join(failed))
