"""The capture surface.

Three of these exist because driving the pages in a browser found bugs the API tests
could not: they assert content is *present*, and what was wrong was content that should
not have been there at all. A template comment written with `{# … #}` across several
lines is not a comment — Django's is single-line — so four blocks of prose about the
design were rendering to the page. The guard against that is the first test below.
"""

import json
from datetime import datetime, timezone as dt_timezone

import pytest

from mind import services
from mind.models import ConnectionHypothesis, Edge, Node, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
JAN = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)

PAGES = ["/mind/", "/mind/review/", "/mind/search/", "/mind/numbers/", "/mind/concepts/"]


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def _hypothesis(owner):
    a = services.capture(
        owner, content="the scanner failed again", captured_at=JAN,
        source=NodeSource.WEB, actor="vince",
    )
    b = services.capture(
        owner, content="the scanner died halfway", captured_at=JAN,
        source=NodeSource.IMPORT, actor="vince", import_key="k",
    )
    return services.propose_hypothesis(
        owner,
        detector="dormant_thread",
        citations=[
            services.Citation(node=a, span=(4, 11), reason="the note just captured"),
            services.Citation(node=b, span=(4, 11), reason="written earlier"),
        ],
        confidence=0.7,
        label="shares: scanner",
        index_version="test",
        now=JAN,
    )


# ---------------------------------------------------------------------------
# What must not be on the page
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", PAGES)
def test_no_template_internals_leak_to_the_page(signed_in, owner, url):
    """Found by looking at the running page, not by a test.

    Multi-line `{# … #}` is not a Django comment, so four paragraphs of design prose
    were being served to the reader. Cheap to assert, and it catches the whole class.
    """
    _hypothesis(owner)
    content = signed_in.get(url).content.decode()

    assert "{#" not in content
    assert "{%" not in content, "an unrendered template tag reached the page"
    assert "{{" not in content


@pytest.mark.parametrize("url", PAGES)
def test_every_page_requires_signing_in(client, url):
    """One application, one login.

    This asserted the knowledge core's own `/login/` while it was its own
    project. That page deliberately did not come across in the merge -- two ways
    to sign in to one application is worse than either -- so the redirect now
    goes to the task core's, which is the only one.
    """
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def test_the_capture_page_offers_one_box_and_no_fields(signed_in):
    """Nothing requires classification at the moment of entry, so there is nothing
    on the form to classify with."""
    content = signed_in.get("/mind/").content.decode()

    assert content.count("<textarea") == 1
    assert "<select" not in content


def test_posting_the_form_keeps_the_thought(signed_in, owner):
    response = signed_in.post("/mind/", {"content": "a thought worth keeping"})

    assert response.status_code == 302, "redirect after post, so refresh cannot duplicate"
    assert Node.objects.filter(owner=owner).count() == 1
    assert Node.objects.get().source == NodeSource.WEB


def test_an_empty_submission_is_ignored_rather_than_erroring(signed_in, owner):
    """Nothing to explain to someone who pressed the button by accident."""
    signed_in.post("/mind/", {"content": "   "})
    assert Node.objects.count() == 0


def test_the_recent_list_shows_the_current_body_after_a_revision(signed_in, owner):
    node = services.capture(
        owner, content="as first written", captured_at=JAN,
        source=NodeSource.WEB, actor="vince",
    )
    services.revise(node, body="rewritten since", actor="vince", now=JAN)

    content = signed_in.get("/mind/").content.decode()
    assert "rewritten since" in content


def test_an_empty_corpus_says_so_honestly(signed_in):
    """The quiet start is inherent, so the page says that rather than looking broken."""
    assert "Connections need material" in signed_in.get("/mind/").content.decode()


# ---------------------------------------------------------------------------
# Getting onto a phone
# ---------------------------------------------------------------------------


def test_the_manifest_is_served_for_a_home_screen_install(client):
    """Unauthenticated on purpose: a browser fetches the manifest before anyone has
    signed in, and gating it means no install prompt and no icon."""
    response = client.get("/mind/manifest.webmanifest")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/manifest+json"
    manifest = json.loads(response.content)
    assert manifest["display"] == "standalone"
    assert manifest["icons"][0]["src"].endswith(".svg")


def test_the_manifest_declares_a_share_target(client):
    """The highest-value capture path there is: highlight anything, share, done."""
    share_target = json.loads(client.get("/mind/manifest.webmanifest").content)["share_target"]

    assert share_target["action"] == "/mind/share/"
    # GET, so no service worker is needed — which is what lets this work over a plain
    # LAN address and from an iOS Shortcut as well as an Android share sheet.
    assert share_target["method"] == "GET"


def test_a_shared_link_prefills_the_box_without_saving_it(signed_in):
    """Sharing is a gesture toward capture. Writing the note unasked would take the
    decision away for no benefit."""
    response = signed_in.get(
        "/mind/share/", {"title": "A title", "text": "Some highlighted text", "url": "https://e.test/a"}
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Some highlighted text" in content
    assert "https://e.test/a" in content
    assert Node.objects.count() == 0, "nothing saved until the person presses Keep"


def test_a_share_does_not_repeat_the_title_already_in_the_text(signed_in):
    """Android hands over the title inside the text constantly."""
    content = signed_in.get(
        "/mind/share/", {"title": "Obey the Testing Goat", "text": "Obey the Testing Goat"}
    ).content.decode()

    start = content.find("<textarea")
    box = content[start : content.find("</textarea>", start)]
    assert box.count("Obey the Testing Goat") == 1


def test_sharing_requires_signing_in(client):
    assert client.get("/mind/share/", {"text": "x"}).status_code == 302


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def test_loading_the_review_page_marks_its_proposals_shown(signed_in, owner):
    """There is no page that displays a proposal without starting its clock."""
    hypothesis = _hypothesis(owner)
    signed_in.get("/mind/review/")

    hypothesis.refresh_from_db()
    assert hypothesis.first_surfaced_at is not None
    assert hypothesis.review_window_expires_at is not None


def test_the_review_quotes_the_cited_span_not_the_whole_note(signed_in, owner):
    _hypothesis(owner)
    content = signed_in.get("/mind/review/").content.decode()

    assert "scanner" in content
    assert "the scanner failed again" not in content, "cited the whole note"


def test_what_is_on_screen_is_not_reported_as_still_waiting(signed_in, owner):
    """The count is taken after surfacing, and surfacing resolves nothing — so a plain
    pending count reported the proposals already on screen as waiting."""
    _hypothesis(owner)
    content = signed_in.get("/mind/review/").content.decode()
    assert "more waiting" not in content


def test_extra_proposals_are_reported_as_waiting(signed_in, owner):
    for _ in range(7):
        _hypothesis(owner)
    content = signed_in.get("/mind/review/").content.decode()
    assert "more waiting" in content


def test_confirming_from_the_page_creates_the_edge(signed_in, owner):
    hypothesis = _hypothesis(owner)
    response = signed_in.post(
        f"/mind/review/{hypothesis.public_id}/", {"action": "confirm"}
    )

    assert response.status_code == 302
    hypothesis.refresh_from_db()
    assert hypothesis.resolution == "confirmed"
    assert Edge.objects.count() == 1


def test_dismissing_from_the_page_promotes_nothing(signed_in, owner):
    hypothesis = _hypothesis(owner)
    signed_in.post(f"/mind/review/{hypothesis.public_id}/", {"action": "dismiss"})

    hypothesis.refresh_from_db()
    assert hypothesis.resolution == "dismissed"
    assert Edge.objects.count() == 0


def test_resolving_twice_does_not_error(signed_in, owner):
    """A double submit is a person tapping twice, not something to explain."""
    hypothesis = _hypothesis(owner)
    signed_in.post(f"/mind/review/{hypothesis.public_id}/", {"action": "confirm"})
    again = signed_in.post(f"/mind/review/{hypothesis.public_id}/", {"action": "confirm"})

    assert again.status_code == 302
    assert Edge.objects.count() == 1


def test_another_persons_proposal_cannot_be_resolved(signed_in, other_owner):
    theirs = _hypothesis(other_owner)
    signed_in.post(f"/mind/review/{theirs.public_id}/", {"action": "confirm"})

    theirs.refresh_from_db()
    assert theirs.resolved_at is None
    assert Edge.objects.count() == 0


def test_an_empty_review_reads_as_normal_not_broken(signed_in):
    assert "usual state" in signed_in.get("/mind/review/").content.decode()


# ---------------------------------------------------------------------------
# Search, and admitting it failed
# ---------------------------------------------------------------------------


def test_search_finds_a_note(signed_in, owner):
    services.capture(
        owner, content="the furnace filter needs changing", captured_at=JAN,
        source=NodeSource.WEB, actor="vince",
    )
    content = signed_in.get("/mind/search/?q=furnace").content.decode()
    assert "furnace filter" in content


def test_a_failed_search_offers_to_record_the_miss(signed_in):
    """The point of the page as much as the results: a miss is the one retrieval
    signal where the right answer is already known."""
    content = signed_in.get("/mind/search/?q=nothing-matches-this").content.decode()
    assert "can’t find it" in content


def test_recording_a_miss_stores_the_query(signed_in, owner):
    signed_in.post("/mind/search/miss/", {"q": "that thing about delay"})

    miss = owner.misses.get()
    assert miss.query_text == "that thing about delay"


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------


def _table(content: str) -> str:
    """Just the accept-rate table, so a percentage elsewhere cannot fool a test.

    Found by its heading rather than by being the first table on the page. It
    was the first until the readiness table landed above it, at which point
    these tests started reading the wrong one -- a positional assumption that
    held right up until the page changed, which is exactly when a test should
    not quietly start measuring something else.
    """
    heading = content.find("Detectors</h1>")
    start = content.find("<table", heading if heading != -1 else 0)
    return content[start : content.find("</table>", start)] if start != -1 else ""


def test_no_decisions_reads_differently_from_a_zero_rate(signed_in, owner):
    """"No evidence yet" and "wrong every time" must not render the same."""
    _hypothesis(owner)
    table = _table(signed_in.get("/mind/numbers/").content.decode())

    assert "no decisions yet" in table
    assert "%" not in table, "an undecided detector must not show a rate at all"


def test_an_accept_rate_renders_as_a_percentage(signed_in, owner):
    hypothesis = _hypothesis(owner)
    services.confirm_hypothesis(hypothesis, now=JAN, actor="vince")

    assert "100%" in _table(signed_in.get("/mind/numbers/").content.decode())


def test_the_gate_conditions_are_all_shown(signed_in):
    content = signed_in.get("/mind/numbers/").content.decode()
    for name in ("the moment recurs", "accept rates hold", "retrieval misses fall"):
        assert name in content

# ---------------------------------------------------------------------------
# The concept surface
# ---------------------------------------------------------------------------


def _mentioned(owner, label, days):
    """A name recurring across several days, which is what earns a question."""
    from datetime import timedelta

    for offset in days:
        node = services.capture(
            owner,
            content=f"Practised {label} that evening",
            captured_at=JAN + timedelta(days=offset),
            source=NodeSource.WEB,
            actor="vince",
        )
        services.extract_and_record_concepts(node, now=JAN, actor="vince")
    from mind.models import ConceptCandidate

    return ConceptCandidate.objects.get(owner=owner, label=label)


def test_a_name_that_recurs_is_offered_with_its_evidence(signed_in, owner):
    """The count alone asks somebody to take the system's word for it. The
    sentences are what make the answer checkable, which is the same rule the
    review's span citations follow."""
    _mentioned(owner, "Indonesian", [0, 3, 8])

    body = signed_in.get("/mind/concepts/").content.decode()

    assert "Indonesian" in body
    assert "Practised Indonesian that evening" in body


def test_a_name_seen_once_is_not_offered(signed_in, owner):
    """The gate that keeps this from being a second inbox, seen from the page."""
    _mentioned(owner, "Reykjavik", [0])

    assert "Reykjavik" not in signed_in.get("/mind/concepts/").content.decode()


def test_an_empty_surface_says_why_rather_than_looking_broken(signed_in):
    body = signed_in.get("/mind/concepts/").content.decode()

    assert "Nothing to name yet" in body


def test_confirming_moves_a_candidate_to_the_named_list(signed_in, owner):
    concept = _mentioned(owner, "Indonesian", [0, 3, 8])

    signed_in.post(f"/mind/concepts/{concept.public_id}/decide/", {"action": "confirm"})

    concept.refresh_from_db()
    assert concept.confirmed_at is not None
    assert "Yes, that is a thing" not in signed_in.get("/mind/concepts/").content.decode()


def test_rejecting_takes_a_name_off_the_page_for_good(signed_in, owner):
    """And stays off after the next extraction run, which is the whole point --
    otherwise answering the question would be worthless."""
    concept = _mentioned(owner, "Reykjavik", [0, 3, 8])

    signed_in.post(f"/mind/concepts/{concept.public_id}/decide/", {"action": "retire"})

    assert "Reykjavik" not in signed_in.get("/mind/concepts/").content.decode()


def test_a_topic_page_gathers_everything_that_names_one_thing(signed_in, owner):
    """The payoff the layer exists for: not a search result, but the material
    itself, gathered without anybody having filed a note anywhere."""
    concept = _mentioned(owner, "Indonesian", [0, 3, 8])

    body = signed_in.get(f"/mind/concepts/{concept.public_id}/").content.decode()

    assert body.count("Practised Indonesian that evening") == 3


def test_another_persons_concept_is_not_reachable_by_id(client, owner, other_owner):
    """Owner-scoped in the lookup rather than checked afterwards, like every
    other id-taking surface here."""
    theirs = _mentioned(other_owner, "Indonesian", [0, 3, 8])
    client.force_login(owner)

    response = client.get(f"/mind/concepts/{theirs.public_id}/")

    assert response.status_code == 302
    assert "Indonesian" not in client.get("/mind/concepts/").content.decode()


def test_another_person_cannot_decide_your_candidate(client, owner, other_owner):
    theirs = _mentioned(other_owner, "Indonesian", [0, 3, 8])
    client.force_login(owner)

    client.post(f"/mind/concepts/{theirs.public_id}/decide/", {"action": "confirm"})

    theirs.refresh_from_db()
    assert theirs.confirmed_at is None


def test_the_nav_marks_the_page_you_are_on(signed_in):
    """It never did. `page == 'capture'` was compared against a variable no view
    set and no context processor supplied, so the marker had not applied once
    since the nav was written -- the same silent-nothing as an undefined CSS
    class. Read from the resolved route now, which a new view cannot forget to
    pass."""
    assert 'class="here"' in signed_in.get("/mind/concepts/").content.decode()
    assert 'class="here"' in signed_in.get("/mind/").content.decode()
