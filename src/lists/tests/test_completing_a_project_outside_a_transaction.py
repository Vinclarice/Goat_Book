"""Completing a project 500s in production — **found by the browser suite**.

`services.complete_project` locks its row with `select_for_update()` and is the
**only one of its four siblings without `@transaction.atomic`**:
`reopen_project`, `pause_project` and `resume_project` all have it. Postgres
refuses `SELECT … FOR UPDATE` outside a transaction, so the call raises
`TransactionManagementError` and `PATCH /api/v1/projects/{id}` returns a 500.

**It has been live since Release D**, and every unit test covering it passed the
whole time — because Django's `TestCase` wraps each test in a transaction, which
supplies the very thing the code is missing. That is the failure mode this file
exists to close: **a test that provides the conditions the production code
depends on cannot discover that the code depends on them.**

**`TransactionTestCase`, deliberately**, which commits rather than wrapping. It
is slower and it is the only kind of test that can see this.

**Found on August 23, 2026 by `functional_tests`**, run before a deploy because
routing and session handling had changed. Two smoke tests had been failing on
this; the suite is not part of the ordinary edit-and-test loop, which is how a
live 500 stayed invisible while five other suites were green.
"""

from django.db import transaction
from django.test import TransactionTestCase

from accounts.models import User
from lists import services
from lists.models import Project


class CompletingAProjectOutsideATransactionTest(TransactionTestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.project = services.create_project(self.vince, "Website launch")

    def test_completing_one_does_not_need_a_caller_to_open_a_transaction(self):
        """The web request does not open one, and neither does a management
        command. Requiring the caller to remember is the same shape as the
        token endpoints that each forgot to activate a time zone."""
        services.complete_project(self.project)

        self.project.refresh_from_db()
        self.assertTrue(self.project.is_completed)

    def test_the_three_siblings_were_always_fine(self):
        """Which is what makes this an omission rather than a design. All three
        carry `@transaction.atomic`; only completion did not."""
        with transaction.atomic():
            services.complete_project(self.project)

        services.reopen_project(self.project)
        services.pause_project(self.project)
        services.resume_project(self.project)

        self.project.refresh_from_db()
        self.assertFalse(self.project.is_completed)
        self.assertIsNone(self.project.paused_at)

    def test_the_endpoint_no_longer_returns_a_500(self):
        """The shape a person actually meets: pressing *Mark complete* in the
        SPA. `LiveServerTestCase` caught this through the browser; this catches
        it in a second rather than a minute."""
        self.client.force_login(self.vince)

        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            {"is_completed": True},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Project.objects.get(pk=self.project.pk).is_completed)
