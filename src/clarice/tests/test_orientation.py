"""Explaining only what is there — Track D increment 15.

`commercial-blueprint.md` has carried *"explain the six invented concepts —
Area, Project, Checklist Step, Compass, Focus, 'call it enough' — somewhere in
the product, once"* as an open item, and there has been no onboarding, no help
and no in-product explanation of any of them.

**The obvious answer is a tour, and the plan refuses it.** Orientation is one
of two entrances — *quick start* beside *empty my head* — explaining **only the
concepts the person's own material demonstrates**, because *explaining a
Compass that is not there turns personalisation back into the tutorial it
replaced.*

Which makes this a read rather than a script, and gives it three properties a
tour cannot have: nothing is explained before it exists, it empties as it
succeeds, and every explanation names the thing of theirs it is about.
"""

import datetime

from clarice import orientation
from clarice.testing import CrossCoreTestCase, make_node
from daily import services as daily_services
from lists import services as list_services
from lists.models import Project
from review.models import WeeklyReview


MONDAY = datetime.date(2026, 5, 4)


class WhatIsDemonstratedTest(CrossCoreTestCase):
    def named(self):
        return [c.name for c in orientation.what_their_material_demonstrates(self.alice)]

    def test_an_area_is_explained_once_one_exists(self):
        assert "Area" in self.named()

    def test_a_project_is_not_explained_before_there_is_one(self):
        """**The refusal this increment turns on.** A word attached to nothing
        is the tour the two entrances exist to replace."""
        self.assertNotIn("Project", self.named())

    def test_a_project_is_explained_once_there_is_one(self):
        Project.objects.create(owner=self.alice, title="The book")

        self.assertIn("Project", self.named())

    def test_a_checklist_step_waits_for_one(self):
        task = self.a_task()

        self.assertNotIn("Checklist step", self.named())

        list_services.add_checklist_step(task, "the first bit")

        self.assertIn("Checklist step", self.named())

    def test_the_compass_waits_for_one(self):
        """The plan's own example, and it is not a model -- two fields on
        `User` -- so nothing but reading them can tell."""
        self.assertNotIn("Compass", self.named())

        self.alice.compass_purpose = "to finish the book"
        self.alice.save(update_fields=["compass_purpose"])

        self.assertIn("Compass", self.named())

    def test_focus_waits_for_a_day_that_was_planned(self):
        self.assertNotIn("Focus", self.named())

        daily_services.pin_task(self.alice, MONDAY, self.a_task())

        self.assertIn("Focus", self.named())

    def test_calling_it_enough_waits_for_a_week_that_was_ended(self):
        """And for a *finished* one. A review somebody opened and abandoned
        demonstrates nothing, which is the same distinction `completed_at`
        already draws for the brief."""
        WeeklyReview.objects.create(owner=self.alice, week_start=MONDAY)

        self.assertNotIn("Call it enough", self.named())

        WeeklyReview.objects.filter(owner=self.alice).update(
            completed_at=datetime.datetime(2026, 5, 10, tzinfo=datetime.timezone.utc)
        )

        self.assertIn("Call it enough", self.named())

    def test_each_explanation_names_something_of_theirs(self):
        """**The evidence is what makes it not a tour.** A concept explained
        without pointing at the person's own material is a definition, and
        definitions are what nobody reads."""
        for concept in orientation.what_their_material_demonstrates(self.alice):
            with self.subTest(concept=concept.name):
                self.assertTrue(concept.evidence.strip())

    def test_it_empties_as_it_succeeds(self):
        """Once everything is demonstrated there is nothing left to explain,
        which is the property a tour cannot have."""
        Project.objects.create(owner=self.alice, title="The book")
        list_services.add_checklist_step(self.a_task("with steps"), "a step")
        self.alice.compass_purpose = "to finish the book"
        self.alice.save(update_fields=["compass_purpose"])
        daily_services.pin_task(self.alice, MONDAY, self.a_task())
        WeeklyReview.objects.create(
            owner=self.alice,
            week_start=MONDAY,
            completed_at=datetime.datetime(2026, 5, 10, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(len(self.named()), 6)

    def test_it_does_not_read_another_persons_material(self):
        bob = self.someone_else()
        Project.objects.create(owner=bob, title="Theirs")

        self.assertNotIn("Project", self.named())


class NewHereTest(CrossCoreTestCase):
    def test_somebody_who_has_written_nothing_is_new(self):
        """Not a stored flag. A flag says *has been shown the tour*; this asks
        *has anything happened*, which is what the two entrances answer."""
        bob = self.someone_else()

        self.assertTrue(orientation.is_new_here(bob))

    def test_a_captured_thought_is_enough_to_stop_being_new(self):
        bob = self.someone_else()
        make_node(bob, "a thought")

        self.assertFalse(orientation.is_new_here(bob))

    def test_a_task_is_too(self):
        self.a_task()

        self.assertFalse(orientation.is_new_here(self.alice))


class TheStartPageTest(CrossCoreTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)

    def test_it_offers_both_entrances(self):
        """*Quick start* beside *empty my head*. Neither is better; the plan
        names them as two entrances rather than a path and a shortcut."""
        body = self.client.get("/mind/start/").content.decode()

        self.assertIn("/mind/", body)
        self.assertIn("/mind/dump/", body)

    def test_it_explains_a_word_their_material_uses(self):
        body = self.client.get("/mind/start/").content.decode()

        self.assertIn("Area", body)

    def test_it_does_not_explain_a_word_their_material_does_not(self):
        body = self.client.get("/mind/start/").content.decode()

        self.assertNotIn("Compass", body)

    def test_it_is_reachable_without_typing_a_url(self):
        body = self.client.get("/mind/").content.decode()

        self.assertIn("/mind/start/", body)

    def test_signing_in_is_required(self):
        self.client.logout()

        response = self.client.get("/mind/start/")

        self.assertEqual(response.status_code, 302)
