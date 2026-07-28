from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Activate a pending account, but only against a test deployment."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        if settings.DEPLOYMENT_ENVIRONMENT != "test":
            raise CommandError(
                "Account approval refused: DJANGO_ENVIRONMENT must be 'test'."
            )

        User = get_user_model()
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as error:
            raise CommandError(f"No such user: {username}") from error

        user.is_active = True
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Approved {username}."))
