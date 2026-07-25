import os
from unittest import mock

from django.test import SimpleTestCase

from functional_tests import container_commands


class RemoteResetSafetyTest(SimpleTestCase):
    @mock.patch("functional_tests.container_commands._exec_in_container")
    def test_remote_reset_requires_exact_host_confirmation(self, mock_exec):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(RuntimeError, "reset refused"):
                container_commands.reset_database("staging.example.com")

        mock_exec.assert_not_called()

    @mock.patch("functional_tests.container_commands._exec_in_container")
    def test_confirmed_remote_reset_uses_guarded_management_command(self, mock_exec):
        with mock.patch.dict(
            os.environ,
            {"ALLOW_REMOTE_DB_RESET": "staging.example.com"},
            clear=True,
        ):
            container_commands.reset_database("staging.example.com")

        mock_exec.assert_called_once_with(
            "staging.example.com",
            ["/usr/local/bin/python", "/src/manage.py", "reset_test_database"],
        )
