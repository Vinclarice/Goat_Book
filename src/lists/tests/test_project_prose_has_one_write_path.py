"""Three project fields, one write path each -- the half August 22 left open.

`services.set_desired_outcome` says why it exists, in its own docstring: *"A
service rather than a line in the API handler, which is where this field has
been written since August 20 ... one of a pair living in the API while the
other lives here is how two fields that must stay distinguishable start
drifting apart."*

**The service was written and the call site was never switched over.** So the
handler kept assigning `project.desired_outcome` directly, and the pairing the
refactor existed to protect -- `desired_outcome` against `abandon_if`, *an
ambition against a tripwire you cannot tell it from* -- was left with the two
halves in two places, which is the state the docstring describes as the
failure.

**Nothing is broken today**, and that is worth saying rather than implying
otherwise: both paths `.strip()` and both store `""` for the cleared state, so
no test could have caught this by asserting on values. What is at risk is the
next change to either half, which is exactly what the service was created to
make impossible. These tests assert the *route*, because the route is the
thing that was supposed to change.

`set_project_notes` is here for the same reason and by the same omission.
"""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from lists import services


User = get_user_model()


class ProjectProseWritePathTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.user)
        self.project = services.create_project(self.user, "Website launch")

    def patch(self, body):
        return self.client.patch(
            f"/api/v1/projects/{self.project.pk}",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_an_outcome_is_written_through_its_service(self):
        with mock.patch.object(
            services, "set_desired_outcome", wraps=services.set_desired_outcome
        ) as setter:
            response = self.patch({"desired_outcome": "  The form is live.  "})

        self.assertEqual(response.status_code, 200)
        setter.assert_called_once()
        self.project.refresh_from_db()
        self.assertEqual(self.project.desired_outcome, "The form is live.")

    def test_an_abandonment_condition_is_written_through_its_service(self):
        """The twin, and the one the pairing argument is actually about."""
        with mock.patch.object(
            services,
            "set_abandonment_condition",
            wraps=services.set_abandonment_condition,
        ) as setter:
            response = self.patch({"abandon_if": "  Nobody books in a month.  "})

        self.assertEqual(response.status_code, 200)
        setter.assert_called_once()
        self.project.refresh_from_db()
        self.assertEqual(self.project.abandon_if, "Nobody books in a month.")

    def test_notes_are_written_through_their_service(self):
        with mock.patch.object(
            services, "set_project_notes", wraps=services.set_project_notes
        ) as setter:
            response = self.patch({"notes": "  Waiting on the copy.  "})

        self.assertEqual(response.status_code, 200)
        setter.assert_called_once()
        self.project.refresh_from_db()
        self.assertEqual(self.project.notes, "Waiting on the copy.")

    def test_a_field_nobody_mentioned_calls_nothing(self):
        """The route must not fire on absence -- `None` means *not mentioned*,
        and a setter called with it would write `""` over real prose."""
        self.project.desired_outcome = "The form is live."
        self.project.save(update_fields=["desired_outcome"])

        with mock.patch.object(services, "set_desired_outcome") as setter:
            self.patch({"title": "Site launch"})

        setter.assert_not_called()
        self.project.refresh_from_db()
        self.assertEqual(self.project.desired_outcome, "The form is live.")

    def test_the_cleared_state_still_reaches_the_service(self):
        """`""` is a value, not an absence -- the distinction `ProjectUpdateIn`
        already documents, asserted here because routing is where it could be
        lost."""
        self.project.desired_outcome = "Something"
        self.project.save(update_fields=["desired_outcome"])

        with mock.patch.object(
            services, "set_desired_outcome", wraps=services.set_desired_outcome
        ) as setter:
            self.patch({"desired_outcome": ""})

        setter.assert_called_once()
        self.project.refresh_from_db()
        self.assertEqual(self.project.desired_outcome, "")
