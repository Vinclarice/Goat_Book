"""The agenda seen through two users' different days.

The design claim these protect: agenda.py, api_v1.py and services.py need
no per-user code at all, because every day boundary they compute reads the
zone the middleware activated. If that stops being true, these fail while
the unit tests around bucket_for keep passing.
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from accounts.models import User
from lists.models import Item, List


# 23:30 UTC on August 1st: already the 2nd in Makassar (+8), still the 1st
# in New York (-4). The twelve-hour spread is the real one between the two
# active users, and this is the moment it puts them on different dates.
SPLIT_MOMENT = datetime(2026, 8, 1, 23, 30, tzinfo=ZoneInfo("UTC"))

MAKASSAR_TODAY = "2026-08-02"
NEW_YORK_TODAY = "2026-08-01"


class AgendaTimeZoneTest(TestCase):
    def setUp(self):
        self.obi = User.objects.create_user(
            username="obi",
            email="obi@example.com",
            password="correct horse battery staple",
            time_zone="Asia/Makassar",
        )
        self.edith = User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="correct horse battery staple",
            time_zone="America/New_York",
        )

    def agenda_for(self, user):
        self.client.force_login(user)
        with patch("django.utils.timezone.now", return_value=SPLIT_MOMENT):
            return self.client.get("/api/v1/agenda").json()

    def test_each_user_gets_their_own_today(self):
        self.assertEqual(self.agenda_for(self.obi)["today"], MAKASSAR_TODAY)
        self.assertEqual(self.agenda_for(self.edith)["today"], NEW_YORK_TODAY)

    def test_the_same_due_date_buckets_differently_for_each_user(self):
        # A task due August 2nd is today's work in Makassar and still
        # tomorrow's in New York, at the very same instant.
        for user in (self.obi, self.edith):
            task_list = List.objects.create(owner=user, title="Work")
            Item.objects.create(
                list=task_list,
                text="Call the bank",
                due_date=datetime(2026, 8, 2).date(),
            )

        def bucket_of(payload):
            task = payload["items"][0]
            today = payload["today"]
            if task["due_date"] == today:
                return "today"
            return "later" if task["due_date"] > today else "overdue"

        self.assertEqual(bucket_of(self.agenda_for(self.obi)), "today")
        self.assertEqual(bucket_of(self.agenda_for(self.edith)), "later")

    def test_snooze_presets_resolve_against_the_requesting_users_date(self):
        obi_tomorrow = self.agenda_for(self.obi)["today"]
        edith_tomorrow = self.agenda_for(self.edith)["today"]

        # Not an assertion about snooze itself -- just that the base date
        # every preset is computed from already differs by a day here.
        self.assertEqual(
            datetime.fromisoformat(obi_tomorrow)
            - datetime.fromisoformat(edith_tomorrow),
            timedelta(days=1),
        )
