"""The nav can reach the other core.

The merger put the knowledge core in this application on August 14 and the
crossover has been moving work into it ever since -- and until now the only way
to open it was to type `/mind/` into the address bar. A surface nobody can reach
has been shipped twice in this project already, which is why `side-nav-mockup`'s
own comments keep saying so.

**The URL comes from the server, not the client.** `clarice/urls.py` records
that the `/mind/` prefix is temporary and appears in exactly one line, because
where those pages finally live is the decision that ends the crossover.
Hardcoding it in the nav would make that two lines, in two languages, and the
second one would be found late.
"""

from django.test import TestCase

from accounts.models import User


class NavReachesBothCoresTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.client.force_login(self.user)

    def test_the_nav_payload_carries_a_link_to_the_knowledge_core(self):
        response = self.client.get("/api/v1/nav")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mind_url"], "/mind/")

    def test_it_is_reversed_rather_than_written_out(self):
        """The prefix lives in one line of the project URLconf and moves when
        the crossover ends. Reversing means the nav follows it."""
        from django.urls import reverse

        response = self.client.get("/api/v1/nav")

        self.assertEqual(response.json()["mind_url"], reverse("capture"))
