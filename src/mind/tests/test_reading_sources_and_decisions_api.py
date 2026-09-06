"""Reading what you read, and what you chose — app-overhaul-plan.md increment 2a.

The second and third pairs, after Concepts. Same shape and same rules: session
only, mirroring `views.sources`/`views.source` and `views.decisions`/
`views.decision` rather than improving on them, and **pure addition** — both
pages keep their templates and keep working, and nothing consumes these until
2b.

**Only the reads.** Both of those views are `GET`-and-`POST` on one route, and
recording a source or a decision stays where it is. 2a is the half a panel
needs to *show* something; the writes move with the panel in 2b, together, so
there is never a moment where a surface can read but not write.

**The two orderings are load-bearing and are not the model's default.**
`Source.Meta` orders newest-first and `Decision.Meta` does too, but the
decisions page leads with the *due* ones — `views.decisions` is explicit that
sorting by date buries the third of S11's done-means, *find decisions past
their reconsideration trigger without hunting for them*. So `due` is its own
list here rather than a flag on the rows, exactly as the page has it.
"""

from datetime import date, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from mind import services
from mind.models import NodeSource, Source

PASSWORD = "a secure password"


@pytest.fixture
def alice():
    return User.objects.create_user("alice", "alice@example.com", PASSWORD)


@pytest.fixture
def bob():
    return User.objects.create_user("bob", "bob@example.com", PASSWORD)


@pytest.fixture
def client():
    return Client()


def a_source(owner, title="Thinking, Fast and Slow", url=""):
    return services.record_source(
        owner, title=title, url=url, author="Kahneman", now=timezone.now()
    )


def a_decision(owner, question="Which database?", chose="Postgres", after=None):
    return services.record_decision(
        owner,
        question=question,
        chose=chose,
        considered="SQLite",
        revisit_when="if the write volume changes",
        revisit_after=after,
        now=timezone.now(),
    )


# --- what you read ---------------------------------------------------------


@pytest.mark.django_db
def test_the_sources_index_lists_what_this_owner_read(client, alice, bob):
    a_source(alice, "Thinking, Fast and Slow")
    a_source(bob, "Something Bob read", url="https://example.com/bob")
    client.force_login(alice)

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    titles = [each["title"] for each in response.json()["sources"]]
    assert titles == ["Thinking, Fast and Slow"]


@pytest.mark.django_db
def test_a_source_carries_what_grew_out_of_it(client, alice):
    """S15's whole point, and `what_grew_from`'s: the chain is walked rather
    than stored, so this cannot disagree with the task core about what came of
    anything."""
    source = a_source(alice)
    services.capture(
        alice,
        content="Anchoring is worse than I thought.",
        captured_at=timezone.now(),
        source=NodeSource.WEB,
        actor=alice.get_username(),
        came_from=source,
    )
    client.force_login(alice)

    response = client.get(f"/api/v1/sources/{source.public_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["title"] == "Thinking, Fast and Slow"
    assert any("Anchoring" in note["body"] for note in body["grew"]["notes"])


@pytest.mark.django_db
def test_another_owners_source_is_not_found(client, alice, bob):
    source = a_source(bob, "Bob's book", url="https://example.com/bob")
    client.force_login(alice)

    assert (
        client.get(f"/api/v1/sources/{source.public_id}").status_code == 404
    )


# --- what you chose --------------------------------------------------------


@pytest.mark.django_db
def test_the_decisions_index_leads_with_the_ones_that_have_come_back(
    client, alice
):
    """A separate list rather than an ordering, because that is what the page
    does and why: *find decisions past their reconsideration trigger without
    hunting for them* is a third of S11, and a date sort buries it."""
    due = a_decision(
        alice,
        question="Which database?",
        after=date.today() - timedelta(days=1),
    )
    a_decision(alice, question="Which host?", chose="Hetzner", after=None)
    client.force_login(alice)

    response = client.get("/api/v1/decisions")

    assert response.status_code == 200
    body = response.json()
    assert [each["question"] for each in body["due"]["past_their_date"]] == [
        "Which database?"
    ]
    assert str(due.public_id) in [each["public_id"] for each in body["all"]]
    assert len(body["all"]) == 2


@pytest.mark.django_db
def test_the_undatable_ones_are_counted_rather_than_dropped(client, alice):
    """`decisions_to_revisit` returns two halves and only one is a list.

    A decision whose trigger is a condition in words cannot be found by a
    query, and the service is explicit that counting them rather than ignoring
    them "is the difference between a read that is incomplete and one that is
    misleading". This endpoint first modelled `due` as a bare list, which
    passed the test above while dropping that half entirely.
    """
    a_decision(alice, question="Which host?", chose="Hetzner", after=None)
    client.force_login(alice)

    response = client.get("/api/v1/decisions")

    due = response.json()["due"]
    assert due["past_their_date"] == []
    assert due["waiting_on_a_condition"] == 1


@pytest.mark.django_db
def test_a_decision_keeps_what_it_was_standing_on(client, alice):
    """`considered` is the half a note cannot keep: six weeks later the
    alternatives are the part you have forgotten."""
    decision = a_decision(alice)
    client.force_login(alice)

    response = client.get(f"/api/v1/decisions/{decision.public_id}")

    assert response.status_code == 200
    body = response.json()["decision"]
    assert body["chose"] == "Postgres"
    assert body["considered"] == "SQLite"
    assert body["revisit_when"] == "if the write volume changes"


@pytest.mark.django_db
def test_another_owners_decision_is_not_found(client, alice, bob):
    decision = a_decision(bob)
    client.force_login(alice)

    assert (
        client.get(f"/api/v1/decisions/{decision.public_id}").status_code == 404
    )


@pytest.mark.django_db
def test_both_reads_need_a_session(client, alice):
    source = a_source(alice)
    decision = a_decision(alice)

    assert client.get("/api/v1/sources").status_code == 401
    assert client.get(f"/api/v1/sources/{source.public_id}").status_code == 401
    assert client.get("/api/v1/decisions").status_code == 401
    assert (
        client.get(f"/api/v1/decisions/{decision.public_id}").status_code == 401
    )
