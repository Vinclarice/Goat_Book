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
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User, resolve_time_zone
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
    return f"  - {item.text} ({where}{when})"


def build_message(user, items, today):
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
    lines.append("Open Clarice to work through them.")
    return "\n".join(lines)


def build_subject(items, today):
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
    return f"Clarice · {date_format(today, 'M j')} · " + ", ".join(parts)


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

        now = timezone.now()
        sent = 0
        # One recipient must not cost everybody else their morning. The loop
        # orders by username, so an unguarded raise here did not delay the
        # rest -- it never delivered to them at all, and the write-off path
        # below stamped the day as decided anyway. The other
        # one-user-blocks-everyone failure in this loop was already guarded
        # (`resolve_time_zone(...) or ...` two lines down); this is the
        # likelier instance of the same class.
        #
        # Deliberately not stamping on failure: their day was *not* decided,
        # so the next hourly run tries again, and the existing until_hour
        # write-off is what eventually closes it out. That keeps a transient
        # rejection from silently costing a whole day.
        failed = []
        for user in recipients.order_by("username"):
            try:
                zone = resolve_time_zone(user.time_zone) or ZoneInfo(settings.TIME_ZONE)
                local_now = now.astimezone(zone)
                today = local_now.date()

                # Their day is already decided, so an hourly run is a no-op for
                # them. This is what makes running twelve more times today safe.
                if user.last_digest_date == today:
                    continue

                # "At or after" rather than "equals": an equality test silently
                # drops a whole day whenever the 07:00 run is missed -- a
                # reboot, a slow image pull, or a spring-forward transition that
                # skips the hour outright in some zones.
                if local_now.hour < send_hour:
                    continue

                # Inside the window this sends; past it the day falls straight
                # through to being stamped, which is how a missed morning is
                # written off rather than delivered stale in the evening.
                if local_now.hour < until_hour:
                    items = agenda_reader.digest_items_for(user, today)
                    if items:
                        subject = build_subject(items, today)
                        body = build_message(user, items, today)

                        if dry_run:
                            self.stdout.write(
                                f"--- {user.email} ({user.time_zone}) ---"
                            )
                            self.stdout.write(subject)
                            self.stdout.write(body)
                        else:
                            send_mail(
                                subject=subject,
                                message=body,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[user.email],
                            )
                            sent += 1

                if not dry_run:
                    # Stamped even when nothing was sent, which is the whole
                    # difference between a morning digest and an alarm. Without
                    # it the hourly job keeps reconsidering, and a task that
                    # becomes overdue at 14:00 mails a "good morning" at 15:00.
                    user.last_digest_date = today
                    user.save(update_fields=["last_digest_date"])
            except Exception as error:
                # Broad on purpose: the mail backend's failure modes are not
                # ours to enumerate, and any of them costs the same thing.
                failed.append(user.get_username())
                self.stderr.write(
                    self.style.ERROR(f"  {user.get_username()}: {error}")
                )

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
