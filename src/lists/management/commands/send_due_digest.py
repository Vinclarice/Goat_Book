"""Emails each opted-in user what's overdue or due today.

Intended to run once a morning from cron on the server, e.g.

    0 7 * * * docker exec clarice python manage.py send_due_digest

Users with nothing to report are skipped, so a quiet day stays quiet.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User
from lists import agenda as agenda_reader


def _describe(item, today):
    bucket = agenda_reader.bucket_for(item.due_date, today)
    if bucket == agenda_reader.OVERDUE:
        days = (today - item.due_date).days
        when = "due yesterday" if days == 1 else f"{days} days overdue"
    else:
        when = "due today"
    return f"  - {item.text} ({item.list.title}, {when})"


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

    def handle(self, *args, **options):
        today = timezone.localdate()
        recipients = User.objects.filter(is_active=True, daily_digest=True)
        if options["username"]:
            recipients = recipients.filter(username=options["username"])

        sent = 0
        for user in recipients.order_by("username"):
            items = agenda_reader.digest_items_for(user, today)
            if not items:
                continue

            subject = build_subject(items, today)
            body = build_message(user, items, today)

            if options["dry_run"]:
                self.stdout.write(f"--- {user.email} ---")
                self.stdout.write(subject)
                self.stdout.write(body)
                continue

            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            sent += 1

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Sent {sent} digest email(s).")
            )
