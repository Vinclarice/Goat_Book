"""Emails whoever asked for it an evening nudge to close the day.

Runs hourly from cron beside the morning digest, and for the same reason: users
are in different time zones, so a single daily run can only ever be somebody's
evening. The schedule wakes the command; the command decides per recipient.

**S5's third absence.** Its verdict named three -- *"no evening surface, no
prompt, no reminder"* -- and the first two shipped with the closing ritual. An
in-page prompt asks when you open the day and does nothing if you do not; this
is the half that reaches somebody who did not.

**Off by default**, unlike the digest. A second recurring message is a
different thing to agree to.

**Nothing hard about scheduling lives here.** The zone, the stamp, at-or-after,
the closing window, stamping a quiet day and one recipient's failure staying
theirs are all `clarice.scheduled_mail`'s -- extracted before this was written
so it could not copy them.
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User
from clarice.scheduled_mail import deliver_once_a_day
from daily import reads


# The local hours an evening nudge is due, as [start, end). The start is
# `reads.CLOSING_HOUR`, borrowed rather than repeated, because the page and the
# mail asking at different times would be two answers to when the day is over.
#
# The end matters as much as it does for the morning: past it the day is
# written off unsent, so a container down all evening does not ask "what
# happened today?" at 04:00 the next morning, by which point the question is
# not late but wrong.
NUDGE_LAST_HOUR = 23

logger = logging.getLogger(__name__)


def _day_url(day):
    """`settings.SITE_URL`, since a management command has no request to build
    an absolute URL against -- the same choice the digest and the approval
    mail already make."""
    return f"{settings.SITE_URL}{reverse('app_shell_path', args=[f'day/{day}'])}"


def build_message(user, closing, day):
    lines = [f"Evening, {user.username}."]
    if closing.chosen:
        held = f"You finished {closing.finished} of {closing.chosen}"
        if closing.released:
            held += f", and set {closing.released} aside"
        lines += ["", f"{held}."]
    lines += [
        "",
        "What happened today, while it is still true?",
        "",
        _day_url(day),
    ]
    return "\n".join(lines)


def build_subject(day):
    return f"Clarice · {date_format(day, 'M j')} · close the day"


class Command(BaseCommand):
    help = "Email opted-in users an evening nudge to write the day down."

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
            default=reads.CLOSING_HOUR,
            help=(
                "The local hour the nudge becomes due. Defaults to the same "
                "hour the page starts asking at."
            ),
        )
        parser.add_argument(
            "--until-hour",
            type=int,
            default=NUDGE_LAST_HOUR,
            help=(
                "The local hour the evening is considered over (exclusive). "
                "Past it the day is written off unsent."
            ),
        )
        parser.add_argument(
            "--now",
            help=(
                "An ISO instant to run as, instead of the real clock. For "
                "tests: the clock is injected here at the edge, per "
                "principles.md, rather than frozen."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        recipients = User.objects.filter(is_active=True, closing_nudge=True)
        if options["username"]:
            recipients = recipients.filter(username=options["username"])

        def compose(user, today):
            # The same read the page uses, so the mail and the prompt cannot
            # disagree about what the day held or about whether it has already
            # been written. The hour has been decided by the scheduler by the
            # time this runs, which is why this asks for the summary rather
            # than the gated version.
            closing = reads.closing_summary_for(user, today)
            if closing is None:
                return None
            return build_subject(today), build_message(user, closing, today)

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

        sent, failed = deliver_once_a_day(
            recipients=recipients,
            stamp_field="last_closing_nudge_date",
            send_hour=options["send_hour"],
            until_hour=options["until_hour"],
            now=(
                datetime.fromisoformat(options["now"])
                if options["now"]
                else timezone.now()
            ),
            compose=compose,
            deliver=show if dry_run else send,
            stamp=not dry_run,
            logger=logger,
            label="closing nudge",
        )
        for username in failed:
            self.stderr.write(self.style.ERROR(f"  {username}: delivery failed"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
        elif sent:
            # Silent otherwise: this runs 24 times a day, and a line per run
            # is 24 pieces of cron mail saying nothing happened.
            self.stdout.write(self.style.SUCCESS(f"Sent {sent} nudge(s)."))

        if failed:
            raise CommandError("closing nudge failed for: " + ", ".join(failed))
