"""The capture surface.

Server-rendered on purpose. The binding constraint on this whole project is capture
volume, and volume comes from a phone — so what matters is a page that loads instantly
in a mobile browser, works offline-ish via the API, and can be added to a home screen.
A build step and a client framework would buy structure this does not need yet and cost
the thing it does need, which is being usable today.

Two surfaces, matching the two halves of the loop:

* **Capture** — one textarea, and since August 15 one optional tags box beside it.
  Nothing to classify, nothing to file, nothing required. The first principle of the
  product is that nothing demands a decision at the moment of entry, and a form with a
  dropdown on it would break that before anything else got a chance to — a closed set
  asks which one, and leaving it alone still reads as an answer withheld. An empty text
  box asks nothing. See `capture()` for why the exception was worth making.
* **Review** — the few proposals worth considering, each quoting its evidence, with
  accept and dismiss. Opening the page marks them shown, because showing and surfacing
  are one operation.

Everything routes through `services`; these views parse a form and redirect.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery
from django.db.models import Q
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from lists.services import TaskConflict

from . import instrumentation, queries, services
from .models import (
    ConceptCandidate,
    ConnectionHypothesis,
    Facet,
    FacetKind,
    NodeSource,
)

RECENT_LIMIT = 30
REVIEW_LIMIT = 5
# A handful at a time, for the same reason the review shows five. The queue
# being finite is the point; a screenful of questions is the inbox this
# design exists to avoid, even when every one of them is a fair question.
CANDIDATE_LIMIT = 8
# Fewer still. A commitment proposal is the one kind that asks for a decision
# rather than offering a label, so a screenful of them would be an inbox --
# which is the thing this design exists to avoid.
COMMITMENT_LIMIT = 3


def manifest(request):
    """The web app manifest, rendered so the icon URL survives static hashing."""
    return render(
        request,
        "mind/manifest.json",
        {"icon_url": static("mind/icon.svg")},
        content_type="application/manifest+json",
    )


@login_required
@require_http_methods(["GET"])
def share(request):
    """Android's share sheet, and anything else that can open a URL.

    Arrives as a GET with the shared text in the query string, which is what lets this
    work with no service worker at all. The text is *pre-filled, not saved* — sharing is
    a gesture toward capture, and silently writing a note from a link tap would take the
    decision away from the person for no benefit.

    iOS has no share-target support, but a Shortcut that opens `/share/?text=...` reaches
    exactly the same place — which is why this takes plain query parameters rather than
    anything PWA-specific.
    """
    parts = [
        (request.GET.get("title") or "").strip(),
        (request.GET.get("text") or "").strip(),
        (request.GET.get("url") or "").strip(),
    ]
    # A share often repeats the title inside the text, and the URL inside it too.
    prefill = ""
    for part in parts:
        if part and part not in prefill:
            prefill = f"{prefill}\n\n{part}".strip() if prefill else part
    return render(request, "mind/capture.html", _capture_context(request, prefill=prefill))


def _capture_context(request, *, prefill: str = "") -> dict:
    now = timezone.now()
    nodes = list(
        queries.live_nodes(request.user).prefetch_related("revisions")[:RECENT_LIMIT]
    )
    return {
        "prefill": prefill,
        "nodes": [
            {
                "node": node,
                "body": queries.current_body(node),
                "tier": queries.attention_tier(node, now=now),
            }
            for node in nodes
        ],
        # Unaccepted commitments the parser has offered. Shown on the way back
        # from capture rather than during it, which is what keeps the box one
        # box: nothing is asked at the moment of entry, and ignoring these
        # costs nothing.
        "commitments": [
            {"facet": facet, "body": queries.current_body(facet.node)}
            for facet in Facet.objects.filter(
                node__owner=request.user,
                node__deleted_at__isnull=True,
                kind=FacetKind.ACTIONABLE,
                retired_at__isnull=True,
                confirmed_at__isnull=True,
            ).select_related("node")[:COMMITMENT_LIMIT]
        ],
        "pending": queries.pending_hypotheses(request.user).count(),
        "total": queries.live_nodes(request.user).count(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def capture(request):
    """One box, and one optional field beside it. Type, submit, done.

    **The tags field is a considered exception to "no fields", not a drift from
    it.** This surface refuses to ask anything at the moment of entry, and a
    dropdown would break that — it presents a closed set, and leaving it alone
    still feels like an answer withheld. An empty text box asks nothing, and
    somebody who never touches it captures exactly as before.

    What it buys is the other half of a decision already made: a typed tag
    becomes a confirmed concept (`services.record_typed_tags`), and until now
    the only surface that could type one was the phone.

    The evidence for wanting it is concrete. The first real detector run, over
    18 notes on August 15, proposed nothing — and the six candidates extraction
    found were `Gravity`, `MOT`, `Oct`, `YT` and two phrases, each seen once.
    What actually recurred across four notes and twelve days was *movie*,
    lowercase, which a capitalisation-based extractor cannot see. The gravity
    gate exists to filter the system's guesses; a person who knows "movie" is a
    thing should not have to wait behind it.
    """
    if request.method == "POST":
        content = request.POST.get("content", "")
        if content.strip():
            now = timezone.now()
            node = services.capture(
                request.user,
                content=content,
                captured_at=now,
                source=NodeSource.WEB,
                actor=request.user.get_username(),
            )
            # Split here rather than in the service, which takes labels: how a
            # surface spells a list is the surface's business, and the phone
            # sends a JSON array for the same call.
            labels = request.POST.get("tags", "").split(",")
            if any(label.strip() for label in labels):
                services.record_typed_tags(
                    node, labels, now=now, actor=request.user.get_username()
                )
        # Redirect after post, so a refresh cannot duplicate a thought.
        return redirect("capture")

    return render(request, "mind/capture.html", _capture_context(request))


@login_required
@require_http_methods(["POST"])
def accept_commitment(request, public_id):
    """One tap: yes that is a task, or no it is not.

    No Area is asked for, and that omission is the feature. A person tapping
    this has already made the only decision that matters; sending them to a form
    to choose where to file it would replace one tap with a filing question at
    exactly the moment this design refuses to ask one. `Item.owner` is what
    makes the resulting task a real task rather than an orphan, and filing stays
    available later for anyone who wants it.

    Owner-scoped in the lookup, so somebody else's proposal is simply not found
    rather than found and refused.
    """
    facet = Facet.objects.filter(
        node__public_id=public_id,
        node__owner=request.user,
        kind=FacetKind.ACTIONABLE,
        retired_at__isnull=True,
    ).first()
    if facet is None:
        return redirect("capture")

    now = timezone.now()
    actor = request.user.get_username()
    try:
        if request.POST.get("action") == "dismiss":
            services.dismiss_facet(facet, now=now, actor=actor)
        else:
            services.confirm_actionable(facet, now=now, actor=actor)
    except (services.MindError, TaskConflict):
        # Already accepted elsewhere, or the same task already exists. Either
        # way the commitment is recorded, so this returns to capture rather
        # than presenting an error for something already settled.
        pass
    return redirect("capture")


@login_required
@require_http_methods(["GET"])
def review(request):
    """The review surface. Loading this page marks its proposals as shown.

    That is the whole design of it — a page that displayed proposals without starting
    their review window would make silence meaningless, so there is no such page.
    """
    hypotheses = services.open_review(
        request.user,
        now=timezone.now(),
        actor=request.user.get_username(),
        limit=REVIEW_LIMIT,
    )

    proposals = []
    for hypothesis in hypotheses:
        members = sorted(
            hypothesis.members.all(),
            key=lambda m: m.node.captured_at,
            reverse=True,
        )
        proposals.append(
            {
                "hypothesis": hypothesis,
                "citations": [
                    {
                        "node": member.node,
                        # The cited span, never the whole note: a claim has to be
                        # checkable against the passage that supports it.
                        "quote": (
                            member.node.original_content[
                                member.span_start : member.span_end
                            ]
                            if member.span_start is not None
                            else member.node.original_content
                        ),
                        "reason": member.contribution_reason,
                        "is_source": position == 0,
                    }
                    for position, member in enumerate(members)
                ],
            }
        )

    # Excluding what was just shown. Surfacing does not resolve anything, so a plain
    # pending count here reports the proposals already on screen as "still waiting".
    remaining = (
        queries.pending_hypotheses(request.user)
        .exclude(pk__in=[h.pk for h in hypotheses])
        .count()
    )
    return render(
        request,
        "mind/review.html",
        {"proposals": proposals, "remaining": remaining},
    )


@login_required
@require_http_methods(["POST"])
def resolve(request, public_id):
    """Accept or dismiss, then back to the review."""
    hypothesis = ConnectionHypothesis.objects.filter(
        public_id=public_id, owner=request.user
    ).first()
    if hypothesis is None:
        return redirect("review")

    now = timezone.now()
    actor = request.user.get_username()
    try:
        if request.POST.get("action") == "confirm":
            services.confirm_hypothesis(hypothesis, now=now, actor=actor)
        else:
            services.dismiss_hypothesis(hypothesis, now=now, actor=actor)
    except services.MindError:
        # Already resolved elsewhere, or its evidence has gone. Either way the review
        # continues rather than presenting an error for something already settled.
        pass
    return redirect("review")


@login_required
@require_http_methods(["GET"])
def concepts(request):
    """The things a person keeps mentioning, and the few worth naming.

    Reading this page changes nothing, deliberately — unlike the review, whose
    whole design is that showing and surfacing are one act. Nothing here starts a
    clock: a candidate that is never confirmed simply stays a candidate, and the
    gravity gate keeps that from costing anything.
    """
    candidates = list(queries.concept_candidates(request.user)[:CANDIDATE_LIMIT])

    # The evidence, not just the count. "Indonesian, 4 mentions" asks somebody to
    # take the system's word for it; the sentences let them check, which is the
    # same rule the review's span citations follow.
    for candidate in candidates:
        candidate.evidence = list(
            queries.nodes_mentioning(request.user, candidate)[:3]
        )

    return render(
        request,
        "mind/concepts.html",
        {
            "candidates": candidates,
            "confirmed": queries.confirmed_concepts(request.user).order_by("label"),
        },
    )


@login_required
@require_http_methods(["GET"])
def concept(request, public_id):
    """Everything about one thing.

    The payoff the whole concept layer exists for: not a search result, but the
    material itself, gathered without anybody having filed it anywhere.
    """
    found = ConceptCandidate.objects.filter(
        public_id=public_id, owner=request.user, retired_at__isnull=True
    ).first()
    if found is None:
        return redirect("concepts")

    canonical = queries.canonical_concept(found)
    return render(
        request,
        "mind/concept.html",
        {
            "concept": canonical,
            "nodes": queries.nodes_mentioning(request.user, canonical),
            "aliases": canonical.aliases.filter(retired_at__isnull=True),
        },
    )


@login_required
@require_http_methods(["POST"])
def decide_concept(request, public_id):
    """Yes this is a thing, or no it is not. Then back to the list."""
    found = ConceptCandidate.objects.filter(
        public_id=public_id, owner=request.user
    ).first()
    if found is None:
        return redirect("concepts")

    now = timezone.now()
    actor = request.user.get_username()
    try:
        if request.POST.get("action") == "confirm":
            services.confirm_concept(found, now=now, actor=actor)
        else:
            services.retire_concept(found, now=now, actor=actor)
    except services.MindError:
        # Already decided, here or in another tab. Nothing to correct and nothing
        # worth an error page for something already settled.
        pass
    return redirect("concepts")


@login_required
@require_http_methods(["GET"])
def search(request):
    """Search, with a way to say the search failed.

    The "I know I wrote this" button is the point of this page as much as the results
    are: a recorded miss is the strongest evidence available about retrieval, because
    the correct answer is known.
    """
    q = (request.GET.get("q") or "").strip()
    results = []
    if q:
        query = SearchQuery(q, config="english")
        nodes = (
            queries.live_nodes(request.user)
            .filter(Q(search_original=query) | Q(revisions__search_body=query))
            .distinct()[:RECENT_LIMIT]
        )
        results = [{"node": node, "body": queries.current_body(node)} for node in nodes]
    return render(request, "mind/search.html", {"q": q, "results": results})


@login_required
@require_http_methods(["POST"])
def record_miss(request):
    services.record_retrieval_miss(
        request.user,
        query_text=request.POST.get("q", ""),
        now=timezone.now(),
    )
    return redirect("search")


@login_required
@require_http_methods(["GET"])
def summary(request):
    """Is any of this working? The numbers, not an impression."""
    return render(
        request,
        "mind/summary.html",
        instrumentation.lab_summary(request.user, now=timezone.now()),
    )
