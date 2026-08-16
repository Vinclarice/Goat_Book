"""Asking to be deleted, and changing your mind, in a real browser.

`commercial-blueprint.md` calls account deletion and data export a legal blocker
rather than a feature gap. Both live on Preferences, which is an SPA route
posting to `/api/v1/`, so this covers the seams the other suites cannot: a real
session cookie, a real CSRF token on a POST, and the banner appearing on a
*different* route from the one that scheduled it.

The purge itself is not walked here — it is a cron job thirty days later, and
`accounts/tests/test_account_deletion.py` covers what it removes.
"""

from django.core import mail
from playwright.sync_api import expect

from accounts.models import User
from functional_tests.base import PASSWORD, BrowserTest


class LeavingTest(BrowserTest):
    def test_a_person_can_schedule_their_deletion_and_call_it_off(self):
        user = self.make_user()
        self.log_in(user)

        self.visit("/app/preferences")

        # 1. The way out is offered before the way off.
        expect(self.page.get_by_role("link", name="Download my data")).to_have_attribute(
            "href", "/api/v1/me/export"
        )

        # 2. Two gates, guarding different mistakes. The checkbox guards a
        #    misunderstanding; the password guards a different person at an
        #    unlocked screen.
        self.page.get_by_role("button", name="Delete my account…").click()
        schedule = self.page.get_by_role("button", name="Schedule deletion")
        expect(schedule).to_be_disabled()

        self.page.get_by_label("Confirm your password").fill(PASSWORD)
        expect(schedule).to_be_disabled()
        self.page.get_by_role("checkbox").check()
        expect(schedule).to_be_enabled()
        schedule.click()

        expect(
            self.page.get_by_role("heading", name="This account is scheduled for permanent deletion")
        ).to_be_visible()
        user.refresh_from_db()
        self.assertIsNotNone(user.deletion_requested_at)

        # 3. Nothing has actually gone. The account still works, which is what
        #    makes cancelling reachable at all.
        self.assertTrue(user.is_active)

        # 4. And they were told, at the address on the account -- the half that
        #    protects somebody who did not do this.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("scheduled for deletion", mail.outbox[0].subject)

        # 5. The warning follows them off this page. A scheduled erasure that is
        #    only visible where it was scheduled is one somebody can forget.
        self.visit("/app/agenda")
        banner = self.page.get_by_role("alert")
        expect(banner).to_contain_text("permanent deletion")

        # 6. And it can be called off from there, not only from Preferences.
        banner.get_by_role("button", name="Keep my account").click()

        expect(self.page.get_by_role("alert")).to_have_count(0)
        user.refresh_from_db()
        self.assertIsNone(user.deletion_requested_at)

    def test_the_export_downloads_and_is_a_readable_archive(self):
        """The file, not just the link.

        A download that 200s and produces an unopenable file would pass every
        other test in this repository. This is the only place the bytes are
        actually handled by a browser.
        """
        import zipfile
        from io import BytesIO

        user = self.make_user()
        self.log_in(user)
        self.visit("/app/preferences")

        with self.page.expect_download() as download:
            self.page.get_by_role("link", name="Download my data").click()
        path = download.value.path()

        with zipfile.ZipFile(path) as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                ["clarice.json", "notes.md", "tasks.md"],
            )
            self.assertIn(
                user.username, archive.read("clarice.json").decode("utf-8")
            )
