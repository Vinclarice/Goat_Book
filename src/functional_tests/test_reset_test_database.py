import os
from unittest import mock

from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from functional_tests.management.commands.reset_test_database import Command


class ResetTestDatabaseCommandTest(SimpleTestCase):
    @mock.patch(
        "functional_tests.management.commands.reset_test_database.call_command"
    )
    @override_settings(DEPLOYMENT_ENVIRONMENT="production")
    def test_refuses_to_flush_a_production_database(self, mock_call_command):
        with mock.patch.dict(os.environ, {"ALLOW_DATABASE_FLUSH": "1"}):
            with self.assertRaisesMessage(CommandError, "must be 'test'"):
                Command().handle()

        mock_call_command.assert_not_called()

    @mock.patch(
        "functional_tests.management.commands.reset_test_database.call_command"
    )
    @override_settings(DEPLOYMENT_ENVIRONMENT="test")
    def test_requires_server_side_flush_confirmation(self, mock_call_command):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "must be '1'"):
                Command().handle()

        mock_call_command.assert_not_called()

    @mock.patch(
        "functional_tests.management.commands.reset_test_database.call_command"
    )
    @override_settings(DEPLOYMENT_ENVIRONMENT="test")
    def test_flushes_only_when_both_server_guards_pass(self, mock_call_command):
        with mock.patch.dict(os.environ, {"ALLOW_DATABASE_FLUSH": "1"}):
            Command().handle()

        mock_call_command.assert_called_once_with("flush", interactive=False)
