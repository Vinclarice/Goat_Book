"""The capture surface.

Server-rendered on purpose. The binding constraint on this whole project is capture
volume, and volume comes from a phone — so what matters is a page that loads instantly
in a mobile browser, works offline-ish via the API, and can be added to a home screen.
A build step and a client framework would buy structure this does not need yet and cost
the thing it does need, which is being usable today.

Two surfaces, matching the two halves of the loop:

* **Capture** — one textarea. Nothing to classify, nothing to file, no fields. The first
  principle of the product is that nothing requires a decision at the moment of entry,
  and a form with a dropdown on it would break that before anything else got a chance to.
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

from . import instrumentation, queries, services
from .models import ConceptCandidate, ConnectionHypothesis, NodeSource

RECENT_LIMIT = 30
REVIEW_LIMIT = 5
# A handful at a time, for the same reason the review shows five. The queue
# being finite is the point; a screenful of questions is the inbox this
# design exists to avoid, even when every one of them is a fair question.
CANDIDATE_LIMIT = 8


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
        "pending": queries.pending_hypotheses(request.user).count(),
        "total": queries.live_nodes(request.user).count(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def capture(request):
    """One box. Type, submit, done."""
    if request.method == "POST":
        content = request.POST.get("content", "")
        if content.strip():
            services.capture(
                request.user,
                content=content,
                captured_at=timezone.now(),
                source=NodeSource.WEB,
                actor=request.user.get_username(),
            )
        # Redirect after post, so a refresh cannot duplicate a thought.
        return redirect("capture")

    return render(request, "mind/capture.html", _capture_context(request))


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
