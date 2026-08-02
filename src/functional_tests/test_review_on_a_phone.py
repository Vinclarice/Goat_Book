"""Crane 3 slice 10 — the assembled weekly review, at a phone's width.

The same instrument Crane 1 slice 7 established, pointed at the surface most
likely to defeat it. The Daily Page is mostly prose in a single column; a
review is figures beside labels, seven marks in a row, and a table-shaped
trend -- all of which are the things that push a page sideways.

**It measures rather than eyeballs.** Horizontal overflow is asserted as a
number, and when it is not zero the failure names the elements responsible.
"Looks fine on my phone" is not a test, and a screenshot at the wrong scroll
position hides exactly the defect this is for.

375x812 is a small modern phone, as in slice 7 -- the width real use will
meet rather than the narrowest device ever made.

**All five passed on their first run**, which this project treats as a
signal rather than a result. The overflow assertion was made to fail once
before being left alone: a 900px element appended to the page, caught as
"Page scrolls 525px sideways" with the offending div named. Same figure as
slice 7's, because it is the same arithmetic -- 900 less a 375px viewport.
"""
from datetime import timedelta

from django.utils import timezone
from playwright.sync_api import expect

from capture import services as capture_services
from capture.models import Idea
from daily import services as daily_services
from functional_tests.base import BrowserTest
from lists import services as list_services
from lists.models import Item, List
from routines import services as routine_services
from routines.models import Routine


PHONE = {"width": 375, "height": 812}


class ReviewOnAPhoneTest(BrowserTest):
    viewport = PHONE

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.today = timezone.localdate()
        self.monday = self.today - timedelta(days=self.today.weekday())

    def instant_on(self, day, hour=9):
        from datetime import datetime

        return timezone.make_aware(
            datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
        )

    def a_full_week(self):
        """A week with something in every section.

        Long text on purpose: an empty page cannot overflow and would prove
        nothing, and the realistic failure is a long task title beside a
        figure rather than a short one.
        """
        finished = list_services.create_item(
            self.list_, "Pay the rent before the landlord emails again"
        )
        daily_services.pin_task(self.user, self.monday, finished)
        list_services.complete_item(finished)
        Item.objects.filter(pk=finished.pk).update(
            completed_at=self.instant_on(self.monday + timedelta(days=2))
        )

        unfinished = list_services.create_item(
            self.list_,
            "Call the plumber about the upstairs leak",
            due_date=self.monday + timedelta(days=1),
        )
        daily_services.pin_task(self.user, self.monday, unfinished)
        Item.objects.filter(pk=unfinished.pk).update(
            created_at=self.instant_on(self.monday - timedelta(days=30))
        )

        dropped = list_services.create_item(
            self.list_, "Reorganise the shed, which can wait another month"
        )
        daily_services.pin_task(self.user, self.monday, dropped)
        daily_services.unpin_task(self.user, self.monday, dropped)

        routine = routine_services.create_routine(
            self.user, title="Practice Spanish", target_quantity=5, unit="lessons"
        )
        Routine.objects.filter(pk=routine.pk).update(
            created_at=self.instant_on(self.monday - timedelta(days=30), 8)
        )
        routine.refresh_from_db()
        for offset in range(3):
            routine_services.log_progress(
                self.user, routine, self.monday + timedelta(days=offset), amount=5
            )
        routine_services.skip_period(
            self.user, routine, self.monday + timedelta(days=3)
        )

        daily_services.write_entry(
            self.user,
            self.monday + timedelta(days=1),
            gratitude="A test suite that tells the truth",
            happenings="Wrote the slice down before writing the code",
        )
        # Three weeks back, so the trend has history rather than five rows
        # of "nothing recorded yet".
        daily_services.write_entry(
            self.user,
            self.monday - timedelta(days=21),
            happenings="Started keeping this",
        )

        capture_services.create_capture(
            self.user, "Ask the landlord about the lease renewal terms"
        )
        Idea.objects.create(
            owner=self.user,
            text="A quieter inbox, sorted once a week rather than daily",
        )

    def test_the_whole_review_fits_the_width_of_a_phone(self):
        """The acceptance condition, as a number rather than an opinion."""
        self.a_full_week()
        self.log_in(self.user)
        self.visit("/app/review")
        expect(
            self.page.get_by_role("heading", level=2, name="What you planned")
        ).to_be_visible()

        overflow = self.horizontal_overflow()

        self.assertEqual(
            overflow,
            0,
            f"Page scrolls {overflow}px sideways. Widest offenders: "
            f"{self.overflowing_elements()}",
        )

    def test_every_section_of_the_review_is_actually_on_screen(self):
        self.a_full_week()
        self.log_in(self.user)
        self.visit("/app/review")

        for heading in (
            "What you planned",
            "Finished",
            "Habits",
            "Recent weeks",
            "In your own words",
            "Ideas you added",
            "Still in your inbox",
        ):
            expect(
                self.page.get_by_role("heading", level=2, name=heading)
            ).to_be_visible()
        expect(self.page.get_by_label("Reflections")).to_be_visible()
        expect(self.page.get_by_label("Next week")).to_be_visible()

    def test_no_control_is_clipped_off_the_right_edge(self):
        """Visible is not the same as reachable: an element can be visible
        to Playwright while sitting past the right edge of a viewport that
        does not scroll, which is a button nobody can press."""
        self.a_full_week()
        self.log_in(self.user)
        self.visit("/app/review")
        expect(
            self.page.get_by_role("button", name="Save the review")
        ).to_be_visible()

        width = self.page.evaluate("document.documentElement.clientWidth")
        clipped = []
        for control in self.page.get_by_role("button").all():
            box = control.bounding_box()
            if box and box["x"] + box["width"] > width + 1:
                clipped.append((control.inner_text(), round(box["x"] + box["width"])))

        self.assertEqual(clipped, [], f"Controls past the {width}px edge: {clipped}")

    def test_the_coming_week_can_be_planned_on_a_phone(self):
        """Fits is necessary and not sufficient -- the point is using it."""
        self.a_full_week()
        self.log_in(self.user)
        self.visit("/app/review")

        self.page.get_by_label("Next week").fill("Two mornings on the review")
        self.page.get_by_role("button", name="Save the review").click()

        expect(self.page.get_by_text("Saved.")).to_be_visible()

    def test_the_review_is_reachable_from_the_phone_menu(self):
        """The gap this sequence has shipped twice, checked at the width
        where a nav link is hidden behind a disclosure rather than simply
        present in the DOM."""
        self.log_in(self.user)
        self.visit("/app/day")
        nav = self.page.get_by_role("navigation", name="Main")
        review = nav.get_by_role("link", name="Review")

        expect(review).not_to_be_visible()
        self.page.get_by_label("Menu").click()
        expect(review).to_be_visible()

        review.click()

        expect(self.page).to_have_url(f"{self.live_server_url}/app/review")
