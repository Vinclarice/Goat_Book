from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from functional_tests.management.commands.approve_test_user import Command


PASSWORD = "correct horse battery staple 47!"


class ApproveTestUserCommandTest(TestCase):
    @override_settings(DEPLOYMENT_ENVIRONMENT="production")
    def test_refuses_to_run_against_a_production_environment(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD, is_active=False)

        with self.assertRaisesMessage(CommandError, "must be 'test'"):
            Command().handle(username="edith")

        self.assertFalse(User.objects.get(username="edith").is_active)

    @override_settings(DEPLOYMENT_ENVIRONMENT="test")
    def test_raises_for_an_unknown_username(self):
        with self.assertRaisesMessage(CommandError, "No such user"):
            Command().handle(username="nobody")

    @override_settings(DEPLOYMENT_ENVIRONMENT="test")
    def test_activates_the_named_pending_user(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD, is_active=False)

        Command().handle(username="edith")

        self.assertTrue(User.objects.get(username="edith").is_active)
