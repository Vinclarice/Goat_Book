from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import agenda
from lists.models import Item, List, Tag


class BucketForTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()

    def test_no_due_date_is_someday(self):
        self.assertEqual(agenda.bucket_for(None, self.today), agenda.SOMEDAY)

    def test_yesterday_is_overdue(self):
        yesterday = self.today - timedelta(days=1)
        self.assertEqual(agenda.bucket_for(yesterday, self.today), agenda.OVERDUE)

    def test_today_is_today(self):
        self.assertEqual(agenda.bucket_for(self.today, self.today), agenda.TODAY)

    def test_tomorrow_is_this_week(self):
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(agenda.bucket_for(tomorrow, self.today), agenda.WEEK)

    def test_the_horizon_itself_is_still_this_week(self):
        edge = self.today + timedelta(days=agenda.WEEK_HORIZON_DAYS)
        self.assertEqual(agenda.bucket_for(edge, self.today), agenda.WEEK)

    def test_the_day_after_the_horizon_is_later(self):
        past_edge = self.today + timedelta(days=agenda.WEEK_HORIZON_DAYS + 1)
        self.assertEqual(agenda.bucket_for(past_edge, self.today), agenda.LATER)


class SnoozePresetsTest(TestCase):
    # Fixed weekdays, because presets that pivot on Saturday and Monday
    # would otherwise only be wrong one day a week.
    TUESDAY = date(2026, 7, 28)
    FRIDAY = date(2026, 7, 31)
    SATURDAY = date(2026, 8, 1)
    SUNDAY = date(2026, 8, 2)
    MONDAY = date(2026, 8, 3)

    def due_date(self, today, key):
        presets = agenda.snooze_presets(today)
        return next(each["due_date"] for each in presets if each["key"] == key)

    def test_the_menu_offers_four_labelled_options_in_order(self):
        presets = agenda.snooze_presets(self.TUESDAY)

        self.assertEqual(
            [(each["key"], each["label"]) for each in presets],
            [
                (agenda.SNOOZE_TOMORROW, "Tomorrow"),
                (agenda.SNOOZE_WEEKEND, "This weekend"),
                (agenda.SNOOZE_NEXT_WEEK, "Next week"),
                (agenda.SNOOZE_CLEAR, "Clear"),
            ],
        )

    def test_tomorrow_is_the_day_after_today(self):
        self.assertEqual(
            self.due_date(self.TUESDAY, agenda.SNOOZE_TOMORROW),
            date(2026, 7, 29),
        )

    def test_this_weekend_is_the_coming_saturday(self):
        self.assertEqual(
            self.due_date(self.TUESDAY, agenda.SNOOZE_WEEKEND),
            self.SATURDAY,
        )

    def test_on_a_saturday_this_weekend_is_the_sunday_still_to_come(self):
        self.assertEqual(
            self.due_date(self.SATURDAY, agenda.SNOOZE_WEEKEND),
            self.SUNDAY,
        )

    def test_on_a_sunday_this_weekend_rolls_on_to_the_next_saturday(self):
        self.assertEqual(
            self.due_date(self.SUNDAY, agenda.SNOOZE_WEEKEND),
            date(2026, 8, 8),
        )

    def test_next_week_is_the_coming_monday(self):
        self.assertEqual(
            self.due_date(self.TUESDAY, agenda.SNOOZE_NEXT_WEEK),
            self.MONDAY,
        )

    def test_on_a_sunday_next_week_starts_tomorrow(self):
        self.assertEqual(
            self.due_date(self.SUNDAY, agenda.SNOOZE_NEXT_WEEK),
            self.MONDAY,
        )

    def test_on_a_monday_next_week_is_a_full_week_ahead(self):
        self.assertEqual(
            self.due_date(self.MONDAY, agenda.SNOOZE_NEXT_WEEK),
            date(2026, 8, 10),
        )

    def test_on_a_friday_the_weekend_is_tomorrow_and_next_week_is_the_monday(self):
        # The day Tomorrow and This weekend collide -- worth pinning, because
        # a menu offering the same date twice reads as a bug to the user.
        self.assertEqual(
            self.due_date(self.FRIDAY, agenda.SNOOZE_TOMORROW),
            self.SATURDAY,
        )
        self.assertEqual(
            self.due_date(self.FRIDAY, agenda.SNOOZE_WEEKEND),
            self.SATURDAY,
        )
        self.assertEqual(
            self.due_date(self.FRIDAY, agenda.SNOOZE_NEXT_WEEK),
            self.MONDAY,
        )

    def test_clear_offers_no_date_at_all(self):
        self.assertIsNone(self.due_date(self.TUESDAY, agenda.SNOOZE_CLEAR))

    def test_every_dated_option_lands_in_the_future(self):
        for today in (
            self.TUESDAY,
            self.FRIDAY,
            self.SATURDAY,
            self.SUNDAY,
            self.MONDAY,
        ):
            for preset in agenda.snooze_presets(today):
                if preset["due_date"] is not None:
                    with self.subTest(today=today, key=preset["key"]):
                        self.assertGreater(preset["due_date"], today)


class AgendaQueryTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        self.work = List.objects.create(owner=self.user, title="Work")
        self.home = List.objects.create(owner=self.user, title="Home")

    def make(self, text, due_offset=None, for_list=None, status=None):
        due = (
            None
            if due_offset is None
            else self.today + timedelta(days=due_offset)
        )
        item = Item.objects.create(
            list=for_list or self.work,
            text=text,
            due_date=due,
        )
        if status == Item.Status.COMPLETED:
            item.status = status
            item.completed_at = timezone.now()
            item.save()
        return item

    def test_open_items_exclude_other_peoples_lists(self):
        theirs = List.objects.create(owner=self.other, title="Theirs")
        Item.objects.create(list=theirs, text="Not mine")
        self.make("Mine")

        texts = [item.text for item in agenda.open_items_for(self.user)]

        self.assertEqual(texts, ["Mine"])

    def test_open_items_exclude_completed_and_archived(self):
        self.make("Still open")
        self.make("Ticked off", status=Item.Status.COMPLETED)
        archived = self.make("Filed away")
        archived.status = Item.Status.ARCHIVED
        archived.completed_at = timezone.now()
        archived.archived_at = timezone.now()
        archived.save()

        texts = [item.text for item in agenda.open_items_for(self.user)]

        self.assertEqual(texts, ["Still open"])

    def test_open_items_sort_undated_tasks_last(self):
        self.make("No deadline")
        self.make("Due soon", due_offset=1)
        self.make("Due later", due_offset=5)

        texts = [item.text for item in agenda.open_items_for(self.user)]

        self.assertEqual(texts, ["Due soon", "Due later", "No deadline"])

    def test_bucketed_groups_by_due_date(self):
        self.make("Late", due_offset=-3)
        self.make("Now", due_offset=0)
        self.make("Soon", due_offset=2)
        self.make("Distant", due_offset=30)
        self.make("Whenever")

        groups = agenda.bucketed(
            agenda.open_items_for(self.user), self.today
        )

        self.assertEqual([i.text for i in groups[agenda.OVERDUE]], ["Late"])
        self.assertEqual([i.text for i in groups[agenda.TODAY]], ["Now"])
        self.assertEqual([i.text for i in groups[agenda.WEEK]], ["Soon"])
        self.assertEqual([i.text for i in groups[agenda.LATER]], ["Distant"])
        self.assertEqual([i.text for i in groups[agenda.SOMEDAY]], ["Whenever"])

    def test_list_summaries_count_open_and_overdue_separately(self):
        self.make("Late", due_offset=-2)
        self.make("Fine", due_offset=3)
        self.make("Chores", for_list=self.home)
        self.make("Done", status=Item.Status.COMPLETED)

        by_title = {each.title: each for each in agenda.list_summaries(self.user)}

        self.assertEqual(by_title["Work"].open_count, 2)
        self.assertEqual(by_title["Work"].overdue_count, 1)
        self.assertEqual(by_title["Home"].open_count, 1)
        self.assertEqual(by_title["Home"].overdue_count, 0)

    def test_tag_summaries_only_count_open_tasks(self):
        errand = Tag.objects.create(owner=self.user, name="errand")
        self.make("Post office").tags.add(errand)
        self.make("Bank").tags.add(errand)
        self.make("Filed", status=Item.Status.COMPLETED).tags.add(errand)

        summaries = agenda.tag_summaries(agenda.open_items_for(self.user))

        self.assertEqual(summaries, [{"name": "errand", "count": 2}])

    def test_completed_today_ignores_older_completions(self):
        fresh = self.make("Ticked today", status=Item.Status.COMPLETED)
        stale = self.make("Ticked last week", status=Item.Status.COMPLETED)
        Item.objects.filter(pk=stale.pk).update(
            completed_at=timezone.now() - timedelta(days=7)
        )

        texts = [
            item.text for item in agenda.completed_today_for(self.user, self.today)
        ]

        self.assertEqual(texts, [fresh.text])

    def test_digest_items_are_overdue_then_due_today(self):
        self.make("Soon", due_offset=2)
        self.make("Now", due_offset=0)
        self.make("Late", due_offset=-2)
        self.make("Whenever")

        texts = [
            item.text for item in agenda.digest_items_for(self.user, self.today)
        ]

        self.assertEqual(texts, ["Late", "Now"])

    def test_annotate_for_display_adds_overdue_days_and_colour(self):
        item = self.make("Late", due_offset=-3)

        [annotated] = agenda.annotate_for_display([item], self.today)

        self.assertEqual(annotated.days_overdue, 3)
        self.assertEqual(
            annotated.list_color, agenda.color_for_list(self.work.id)
        )

    def test_annotate_for_display_leaves_future_tasks_at_zero_days(self):
        item = self.make("Later", due_offset=4)

        [annotated] = agenda.annotate_for_display([item], self.today)

        self.assertEqual(annotated.days_overdue, 0)
