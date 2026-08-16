"""The nav can reach the other core.

The merger put the knowledge core in this application on August 14 and the
crossover has been moving work into it ever since -- and until now the only way
to open it was to type `/mind/` into the address bar. A surface nobody can reach
has been shipped twice in this project already, which is why `side-nav-mockup`'s
own comments keep saying so.

**The URL comes from the server, not the client.** That began as a hedge against
a temporary prefix; Heron step 5 made `/mind/` permanent, and it is still the
right shape — the server owns its own URLs, and a route spelled out in two
languages is one that can disagree with itself, with the second copy found late.
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
        """The prefix lives in one line of the project URLconf. Reversing means
        the nav follows it if it ever moves again -- which step 5 decided it
        will not, but the cost of being wrong about that is one line here and
        none anywhere else."""
        from django.urls import reverse

        response = self.client.get("/api/v1/nav")

        self.assertEqual(response.json()["mind_url"], reverse("capture"))
