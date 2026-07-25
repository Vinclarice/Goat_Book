import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reset a database only when the deployed server is explicitly a test target."

    def handle(self, *args, **options):
        if settings.DEPLOYMENT_ENVIRONMENT != "test":
            raise CommandError(
                "Database reset refused: DJANGO_ENVIRONMENT must be 'test'."
            )
        if os.environ.get("ALLOW_DATABASE_FLUSH") != "1":
            raise CommandError(
                "Database reset refused: ALLOW_DATABASE_FLUSH must be '1'."
            )

        call_command("flush", interactive=False)
        self.stdout.write(self.style.SUCCESS("Test database reset complete."))
