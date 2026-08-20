"""The one navigation, and the things about it that must not drift back.

Rendered through the three templates that include it rather than on its own,
because "identical on every surface" is the property being bought and a test
that renders the partial directly cannot see whether a template forgot to
include it. `/mind/` is the one that matters most: it had no way back to the
task core at all, and both other navigations linked into it.
"""

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User


class AppBarRendering:
    """Rendering helpers, shared without also sharing tests.

    A mixin rather than a base class carrying tests. Subclassing a `TestCase`
    to reuse a helper silently re-runs every test on the parent under the
    child's name -- six more passing tests that prove nothing, and a total
    nobody can reconcile. Found on August 20, 2026 when adding four tests moved
    the suite by ten.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def _request(self, user, path="/"):
        request = self.factory.get(path)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _bar(self, user=None, core="tasks"):
        return render_to_string(
            "_app_bar.html",
            {"core": core, "user": user or self.user},
            request=self._request(user or self.user),
        )


class AppBarTest(AppBarRendering, TestCase):

    def test_offers_both_cores_when_signed_in(self):
        html = self._bar()

        self.assertIn(reverse("dashboard"), html)
        self.assertIn(reverse("capture"), html)

    def test_marks_the_core_you_are_in(self):
        tasks = self._bar(core="tasks")
        mind = self._bar(core="mind")

        # aria-current appears exactly once either way: two current pages is
        # the same as none to anything reading the page aloud.
        self.assertEqual(tasks.count('aria-current="page"'), 1)
        self.assertEqual(mind.count('aria-current="page"'), 1)
        self.assertNotEqual(
            tasks.index('aria-current="page"'), mind.index('aria-current="page"')
        )

    def test_the_knowledge_core_entry_never_carries_a_count(self):
        """CLAUDE.md's rule, moved to where the entry now lives.

        The Inbox's number measured a backlog and this core is quiet by
        design, so a number here would turn resurfacing into precisely the
        thing the attention policy refuses to be. It was guarded in
        SideNav.test.tsx until the entry moved into this bar.
        """
        html = self._bar()

        start = html.index("Second Mind")
        entry = html[start : html.index("</a>", start)]

        self.assertNotIn("badge", entry)
        self.assertFalse(any(character.isdigit() for character in entry))

    def test_signed_out_visitors_get_a_way_in_and_a_way_to_ask(self):
        html = self._bar(user=AnonymousUser())

        self.assertIn(reverse("login"), html)
        self.assertIn(reverse("signup"), html)
        # Outside the authenticated branch on purpose: somebody locked out
        # needs support most and is by definition not signed in.
        self.assertIn(reverse("contact"), html)
        self.assertNotIn('id="id_logout"', html)

    def test_signed_out_visitors_are_not_offered_a_core(self):
        html = self._bar(user=AnonymousUser())

        self.assertNotIn(reverse("capture"), html)

    def test_there_is_exactly_one_logout_and_it_is_a_form_post(self):
        """Two of them, with different mechanics, is what this replaced.

        base.html posted this form and SideNav.tsx posted to
        /api/v1/me/logout. A control that ends a session is the last one that
        should have two implementations, and the form is the one that needs no
        client code to work on all three surfaces.
        """
        html = self._bar()

        self.assertEqual(html.count('id="id_logout"'), 1)
        self.assertIn(f'action="{reverse("logout")}"', html)
        self.assertIn("csrfmiddlewaretoken", html)


class AppBarReachesEverySurfaceTest(TestCase):
    """The bar is only worth having if it is genuinely on all three."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.user)

    def test_the_django_account_pages_carry_it(self):
        response = self.client.get(reverse("contact"))

        self.assertContains(response, 'aria-label="Cores"')

    def test_the_react_shell_carries_it_before_any_javascript_runs(self):
        """Server-rendered, so it is in the first paint rather than after the
        bundle parses -- and so it is the same markup as the other two."""
        response = self.client.get(reverse("app_shell"))

        self.assertContains(response, 'aria-label="Cores"')

    def test_the_knowledge_core_carries_it(self):
        """The one-way door. Both other navigations linked into /mind/ and its
        own nav had no link out, so the only ways back were the browser's back
        button and typing a URL."""
        response = self.client.get(reverse("capture"))

        self.assertContains(response, 'aria-label="Cores"')
        self.assertContains(response, reverse("dashboard"))


class KnowledgeCoreSubNavTest(TestCase):
    """Two renames, both removing a collision rather than improving a word."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.user)

    def test_the_pending_queue_no_longer_shares_a_name_with_the_weekly_review(self):
        """The sharpest defect of the three navigations: the task core's
        Review is a weekly view of the work, and this one is a queue of
        proposals waiting on a decision. One application, one word, two
        unrelated things."""
        response = self.client.get(reverse("capture"))

        self.assertContains(response, "Pending")
        self.assertNotContains(response, ">Review<")

    def test_concepts_is_called_what_its_url_and_view_have_always_called_it(self):
        response = self.client.get(reverse("capture"))

        self.assertContains(response, "Concepts")
        self.assertNotContains(response, ">Things<")


class SearchIsReachableFromEitherCoreTest(AppBarRendering, TestCase):
    """`search-plan.md` D4, August 20, 2026.

    Search shipped into `/mind/search/` and the shared bar did not mention it,
    so reaching it from the task core meant opening the *other core's* capture
    page and using its sub-nav — two hops through somewhere you did not want to
    go. That is B3's shape again: a path built for one audience and never given
    to the people most likely to need it.

    D4 asked whether shipping search promoted the command palette. It does not
    — a cleared precondition is not a trigger — and this is what the question
    was really pointing at.
    """

    def test_search_is_one_click_from_the_task_core(self):
        html = self._bar(core="tasks")

        self.assertIn(reverse("search"), html)

    def test_search_is_one_click_from_the_knowledge_core_too(self):
        """It has its own sub-nav entry there already. The bar carries it as
        well because the bar is what is identical on every surface, and a person
        should not have to learn that search is reachable two different ways
        depending on which half of the application they are standing in."""
        html = self._bar(core="mind")

        self.assertIn(reverse("search"), html)

    def test_search_is_not_offered_as_a_core(self):
        """The Cores nav means "this goes to a core"; its own comment says so.
        Search belongs to neither -- it reads `Item`, `DailyEntry` and `Node` --
        and putting it beside Tasks and Second Mind would say it is a third
        one.
        """
        html = self._bar(core="tasks")

        cores_nav = html.split('aria-label="Cores"')[1].split("</nav>")[0]

        self.assertNotIn(reverse("search"), cores_nav)

    def test_a_signed_out_visitor_is_not_offered_search(self):
        """There is nothing to search, and the link would go to a login form
        that says nothing about why."""
        html = self._bar(user=AnonymousUser())

        self.assertNotIn(reverse("search"), html)
