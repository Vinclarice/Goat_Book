"""Crane 1 slice 7 — the assembled Daily Page, at a phone's width.

Every slice before this was built mobile-aware as it landed, which the
vision document asks for so the home surface is not retrofitted later. This
is the first point there is a whole page to measure: Compass, Focus, Action
Items, capture and the day's own fields, stacked together at a narrow
width, against the built bundle.

**It measures rather than eyeballs.** "Looks fine on my phone" is not a
test, and the failure this guards against -- a control pushed off the right
edge, or a page that scrolls sideways -- is exactly the kind that a
screenshot at the wrong scroll position hides. Horizontal overflow is
asserted as a number, and when it is not zero the failure names the
elements responsible.

375x812 is a small modern phone (iPhone X and most Androids at their CSS
width). Deliberately not the narrowest device ever made: this is the width
real use will meet, and a page that survives it is what M4's pilot needs.
"""
from playwright.sync_api import expect

from functional_tests.base import BrowserTest
from lists.models import List
from lists import services as list_services


PHONE = {"width": 375, "height": 812}


class DailyPageOnAPhoneTest(BrowserTest):
    viewport = PHONE

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.user.compass_purpose = "Build something worth maintaining."
        self.user.compass_question = "What is the most I can do?"
        self.user.save(
            update_fields=["compass_purpose", "compass_question"]
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")

    def a_full_day(self):
        """A day with something in every section, since an empty page
        cannot overflow and would prove nothing."""
        from django.utils import timezone

        from daily import services as daily_services

        today = timezone.localdate()
        task = list_services.create_item(
            self.list_,
            "Pay the rent before the landlord emails again",
            due_date=today,
        )
        list_services.create_item(
            self.list_, "Call the plumber about the upstairs leak"
        )
        daily_services.pin_task(self.user, today, task)
        daily_services.write_entry(
            self.user,
            today,
            intentions="Finish the slice and write it down honestly",
            gratitude="A test suite that tells the truth",
        )

    def test_the_whole_page_fits_the_width_of_a_phone(self):
        """The acceptance condition, as a number rather than an opinion."""
        self.a_full_day()
        self.log_in(self.user)
        self.visit("/app/day")
        expect(self.page.get_by_role("heading", level=2, name="Focus")).to_be_visible()

        overflow = self.horizontal_overflow()

        self.assertEqual(
            overflow,
            0,
            f"Page scrolls {overflow}px sideways. Widest offenders: "
            f"{self.overflowing_elements()}",
        )

    def test_every_section_of_the_day_is_actually_on_screen(self):
        self.a_full_day()
        self.log_in(self.user)
        self.visit("/app/day")

        # The compass, the two lists, capture, and the day's own writing --
        # the whole assembled page from slices 1 through 6.
        expect(
            self.page.get_by_text("Build something worth maintaining.")
        ).to_be_visible()
        expect(self.page.get_by_role("heading", level=2, name="Focus")).to_be_visible()
        expect(
            self.page.get_by_role("heading", level=2, name="Action items")
        ).to_be_visible()
        expect(self.page.get_by_label("Capture a thought")).to_be_visible()
        expect(self.page.get_by_label("Intentions")).to_be_visible()
        expect(self.page.get_by_label("Grateful for")).to_be_visible()
        expect(self.page.get_by_label("Happenings")).to_be_visible()

    def test_no_control_is_clipped_off_the_right_edge(self):
        """Visible is not the same as reachable.

        An element can be `visible` to Playwright while sitting past the
        right edge of a viewport that does not scroll -- which is a button
        nobody can press.
        """
        self.a_full_day()
        self.log_in(self.user)
        self.visit("/app/day")
        expect(self.page.get_by_role("button", name="Save the day")).to_be_visible()

        width = self.page.evaluate("document.documentElement.clientWidth")
        clipped = []
        for control in self.page.get_by_role("button").all():
            box = control.bounding_box()
            if box and box["x"] + box["width"] > width + 1:
                clipped.append((control.inner_text(), round(box["x"] + box["width"])))

        self.assertEqual(clipped, [], f"Controls past the {width}px edge: {clipped}")

    def test_the_home_surface_needs_no_menu_on_a_phone(self):
        """A front door nobody can find is not a front door.

        This used to require opening the disclosure, because Today lived in
        the side rail with everything else. It is in the sub-nav under the app
        bar now, which does not collapse -- so on a phone the core's surfaces
        are reachable without opening anything, and the drawer holds only the
        areas and projects it was always better suited to.

        Still asserted at this width rather than assumed: "in the DOM" and
        "reachable with a thumb" are the distinction this test exists for, and
        that has not changed just because the answer got easier.
        """
        self.log_in(self.user)
        self.visit("/app/agenda")
        views = self.page.get_by_role("navigation", name="Views")
        today = views.get_by_role("link", name="Today")

        expect(today).to_be_visible()

        today.click()

        expect(self.page).to_have_url(f"{self.live_server_url}/app/day")

    def test_the_day_can_still_be_written_and_saved_on_a_phone(self):
        """Fits is necessary and not sufficient -- the point is using it."""
        self.log_in(self.user)
        self.visit("/app/day")

        self.page.get_by_label("Intentions").fill("Typed on a phone")
        self.page.get_by_role("button", name="Save the day").click()

        expect(self.page.get_by_text("Saved.")).to_be_visible()

    def test_a_thought_can_be_captured_on_a_phone(self):
        """Rapid logging is the affordance the vision document calls
        'especially important on mobile'.

        The confirmation is asserted because it has to keep being true. It read
        "Sent to your Inbox." until Heron 4a moved the destination to the graph,
        and a confirmation naming the wrong place is worse than none — somebody
        goes and looks there. This test would have passed either way, which is
        why the string is checked against where the thought actually went.

        **The box is the composer since September 3, 2026** —
        `superlists-2.0-plan.md` increment 4 — so the button reads *Add* and the
        confirmation names which of four destinations the line took. The
        default is a note, which is exactly what this test has always been
        about, and what is asserted is unchanged: the words are kept, and they
        are where the link says.
        """
        self.log_in(self.user)
        self.visit("/app/day")

        self.page.get_by_label("Capture a thought").fill("A thought on the move")
        # `exact=True`, because the page grew a second Add-ish button when
        # appointments arrived -- Playwright matches an accessible name by
        # substring unless told otherwise, and "Add an appointment" contains
        # "Add". The composer's button is the one this test is about.
        self.page.get_by_role("button", name="Add", exact=True).click()

        expect(self.page.get_by_text("Kept as a note.")).to_be_visible()
        expect(self.page.get_by_role("link", name="See it")).to_have_attribute(
            "href", "/mind/"
        )
        # And it is where the link says it is.
        self.visit("/mind/")
        expect(self.page.get_by_text("A thought on the move")).to_be_visible()
