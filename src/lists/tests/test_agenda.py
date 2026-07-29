from datetime import timedelta

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

    def test_summary_counts_fold_overdue_into_this_week(self):
        self.make("Late", due_offset=-3)
        self.make("Also late", due_offset=-1)
        self.make("Now", due_offset=0)
        self.make("Soon", due_offset=2)
        self.make("Whenever")

        counts = agenda.summary_counts(
            agenda.bucketed(agenda.open_items_for(self.user), self.today)
        )

        self.assertEqual(counts["overdue"], 2)
        self.assertEqual(counts["today"], 1)
        # 2 overdue + 1 today + 1 later this week.
        self.assertEqual(counts["week"], 4)
        self.assertEqual(counts["open"], 5)

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

    def test_apply_filters_narrows_by_scope_list_and_tag(self):
        urgent = Tag.objects.create(owner=self.user, name="urgent")
        late = self.make("Late", due_offset=-1)
        late.tags.add(urgent)
        self.make("Later this week", due_offset=3)
        self.make("Chores", for_list=self.home)

        items = list(agenda.open_items_for(self.user))

        by_scope = agenda.apply_filters(items, self.today, scope=agenda.OVERDUE)
        self.assertEqual([i.text for i in by_scope], ["Late"])

        by_list = agenda.apply_filters(items, self.today, list=self.home.id)
        self.assertEqual([i.text for i in by_list], ["Chores"])

        by_tag = agenda.apply_filters(items, self.today, tag="urgent")
        self.assertEqual([i.text for i in by_tag], ["Late"])

    def test_week_scope_includes_overdue_tasks(self):
        self.make("Late", due_offset=-4)
        self.make("Soon", due_offset=1)
        self.make("Distant", due_offset=40)

        selected = agenda.apply_filters(
            list(agenda.open_items_for(self.user)), self.today, scope=agenda.WEEK
        )

        self.assertEqual([i.text for i in selected], ["Late", "Soon"])

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
