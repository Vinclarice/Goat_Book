"""Completing a project needs no transaction opened for it — and briefly did.

`services.complete_project` locks its row with `select_for_update()`, which
Postgres refuses outside a transaction, so without `@transaction.atomic` the
call raises `TransactionManagementError` and `PATCH /api/v1/projects/{id}`
returns a 500.

**It lost that decorator for four hours on August 23, 2026, and to a slip worth
naming.** S12 inserted `record_what_was_learned` immediately above it by
anchoring a text replacement on `def complete_project(project):` — which placed
the new function **between the decorator and its def**. The new function
silently acquired it and this one lost it. Nothing looked wrong: both read
correctly in isolation, and the diff showed an addition rather than a move.
**Anchoring an insertion on a `def` line is unsafe wherever a decorator can sit
above it.**

**Every unit test covering completion still passed**, because Django's
`TestCase` wraps each test in a transaction and so supplied exactly the thing
the code had lost. That is the failure this file closes: **a test that provides
the conditions production code depends on cannot discover that it depends on
them.**

**`TransactionTestCase`, deliberately**, which commits rather than wrapping. It
is slower and it is the only kind of test that can see this.

**It never reached production.** CI's browser job failed on the commit that
introduced it and on the next, and the fix went out in the same deploy — so the
`LIVE` before it and the `LIVE` after it both have the decorator. An earlier
version of this docstring said it had been live since Release D; that was wrong,
and the correction is the interesting part, because the browser suite that
caught it locally is the same one CI had already gone red on.
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
