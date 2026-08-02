"""The critical journeys, end to end in a browser.

Each of these crosses at least one boundary no other suite can reach. See
design/bittern-plan.md, B2.2.
"""
from playwright.sync_api import expect

from functional_tests.base import BrowserTest
from lists.models import Item, List


class TaskJourneyTest(BrowserTest):
    def test_logging_in_then_creating_and_completing_a_task(self):
        """Journey 1. Proves the whole stack stands up together: the login
        form's CSRF token and session cookie, the built bundle loading and
        booting React, the SPA's router, and two authenticated API calls
        made by a real browser rather than the test client.
        """
        user = self.make_user()
        List.objects.create(owner=user, title="Work")

        self.log_in(user)
        self.visit("/app/agenda")

        self.page.fill("#agenda-add-text", "Write the smoke test")
        self.page.get_by_role("button", name="Add").click()

        # A task with no due date lands in the "No due date" bucket, which
        # the server marks collapsed -- so the row exists in the DOM but
        # nobody can see it until the section is opened. Opening it is
        # honest about how the page works; asserting on the hidden row
        # would be a test that passes while the thing it claims to have
        # created is invisible.
        self.page.get_by_role("button", name="No due date").click()

        # exact=True because the confirmation toast quotes the same text,
        # and matching that instead would assert something was announced
        # rather than that a row exists. Rendered from the server's
        # response, so seeing it means the POST was accepted and the client
        # placed the result -- not merely that something was typed in a box.
        expect(
            self.page.get_by_text("Write the smoke test", exact=True)
        ).to_be_visible()

        self.page.get_by_role(
            "button", name="Complete “Write the smoke test”"
        ).click()

        expect(
            self.page.get_by_role("button", name="Reopen “Write the smoke test”")
        ).to_be_visible()


class DirectLoadTest(BrowserTest):
    """Journey 2. Deep links are the case a client-side router most easily
    gets wrong: every SPA path is served by the same Django view, so a
    direct load has to boot the bundle and resolve the route from the URL
    alone, with no in-app navigation to have set anything up first.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.work = List.objects.create(owner=self.user, title="Work")
        self.task = Item.objects.create(
            list=self.work, text="Deep-linked task", position=0
        )
        self.log_in(self.user)

    def test_a_list_url_pasted_into_the_address_bar_loads(self):
        self.visit(f"/app/lists/{self.work.id}")

        expect(self.page.get_by_text("Deep-linked task", exact=True)).to_be_visible()

    def test_a_task_detail_url_pasted_into_the_address_bar_loads(self):
        self.visit(f"/app/tasks/{self.task.id}")

        # The detail view puts the task text in an editable field, so
        # the value is the evidence the route resolved and fetched.
        expect(self.page.locator("#task-text")).to_have_value("Deep-linked task")


class CaptureTriageTest(BrowserTest):
    """Journey 3. Capture is Django-rendered rather than SPA, so this is
    the one journey covering the other half of the application -- server
    forms, POST-redirect-GET, and the capture/idea domain boundary.
    """

    def test_a_captured_thought_can_be_kept_as_an_idea(self):
        user = self.make_user()
        self.log_in(user)

        self.visit("/capture/")
        self.page.fill("#id_text", "Read more about spaced repetition")
        self.page.get_by_role("button", name="Capture").click()

        expect(
            self.page.get_by_text("Read more about spaced repetition")
        ).to_be_visible()

        self.page.get_by_role("button", name="Keep for reference").click()

        # It left the Inbox, which is the half people notice. Asserting
        # the text is gone would fail for the wrong reason -- the undo
        # banner quotes it back. No triage buttons means no captures.
        expect(
            self.page.get_by_role("button", name="Keep for reference")
        ).to_have_count(0)

        # ...and arrived in Ideas, which is the half that matters. A triage
        # that quietly dropped the thought would pass the assertion above.
        self.visit("/capture/ideas/")
        expect(
            self.page.get_by_text("Read more about spaced repetition")
        ).to_be_visible()


class LogoutTest(BrowserTest):
    """Journey 4. B2's logout shipped without any test that a browser
    session actually ends -- the Django tests prove the endpoint returns
    204 and the Vitest tests prove the button calls it, and neither can see
    a cookie afterwards.
    """

    def test_logging_out_leaves_protected_routes_unreachable(self):
        user = self.make_user()
        List.objects.create(owner=user, title="Work")
        self.log_in(user)
        self.visit("/app/agenda")

        self.page.get_by_role("button", name="Log out").click()

        # B2 performs a full navigation to / once the endpoint answers.
        # Waiting for it is not politeness: without this the goto() below
        # races the SPA's own navigation, which either aborts it or lands
        # after it. That failed three runs in five, and in two different
        # ways, which is exactly how a suite stops being believed.
        expect(self.page).to_have_url(f"{self.live_server_url}/")

        # Straight back to a protected route, not merely wherever logout
        # sent us: the question is whether the session is gone, not whether
        # the redirect looked right.
        self.visit("/app/agenda")
        expect(self.page).to_have_url(
            f"{self.live_server_url}/accounts/login/?next=/app/agenda"
        )


class MobileNavigationTest(BrowserTest):
    """Journey 5. This is the one with history: B0 was a nav sealed inside
    a <details> that nothing ever opened, above a breakpoint where the CSS
    hides its <summary>. It was invisible to every test that existed, and
    was found by looking at production.
    """

    NARROW = {"width": 480, "height": 900}
    WIDE = {"width": 1280, "height": 900}

    def test_the_navigation_is_simply_there_on_a_wide_screen(self):
        """The actual B0 regression guard.

        Worth being precise about, because it is easy to assume the
        disclosure test below covers this and it does not. B0 was not a
        mobile bug: above the breakpoint the CSS hides the <summary>, so a
        <details> that nothing ever opened sealed the navigation shut on
        desktop and left an empty 210px gutter. A narrow-width test would
        have passed happily throughout that outage -- which is precisely
        what every test that existed at the time did.
        """
        user = self.make_user()
        List.objects.create(owner=user, title="Work")
        self.log_in(user)
        self.page.set_viewport_size(self.WIDE)
        self.visit("/app/agenda")

        # No clicking. On a wide screen the navigation is not something you
        # open, it is something that is there.
        nav = self.page.get_by_role("navigation", name="Main")
        expect(nav.get_by_role("link", name="Archive")).to_be_visible()
        expect(nav.get_by_role("link", name="Agenda")).to_be_visible()

    def test_the_disclosure_opens_navigates_and_closes(self):
        user = self.make_user()
        List.objects.create(owner=user, title="Work")
        self.log_in(user)
        self.page.set_viewport_size(self.NARROW)
        self.visit("/app/agenda")

        # Scoped to the nav: the agenda body has its own Archive link,
        # which is visible at every width and would make this vacuous.
        nav = self.page.get_by_role("navigation", name="Main")
        archive = nav.get_by_role("link", name="Archive")

        # Closed to begin with: the nav is not simply always on screen at
        # this width, which is what makes the rest of this meaningful.
        expect(archive).not_to_be_visible()

        self.page.get_by_label("Menu").click()
        expect(archive).to_be_visible()

        archive.click()

        # Navigating has to close it. Leaving it open covers the page you
        # just asked for with the menu you used to ask.
        expect(self.page).to_have_url(f"{self.live_server_url}/app/archive")
        expect(archive).not_to_be_visible()
