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

from dataclasses import replace
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from clarice import orientation, recall
from clarice.search import to_query
from daily import reads as daily_reads
from lists import search as lists_search
from lists.services import TaskConflict

from . import ask, instrumentation, queries, reflection, retrieval, services
from .models import (
    Attachment,
    ConceptCandidate,
    MissContext,
    ConceptType,
    ConnectionHypothesis,
    Facet,
    FacetKind,
    Node,
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
                # Shown so a tagged note is distinguishable from an untagged
                # one, and so two spellings of one thing are visible as two.
                "labels": queries.confirmed_concept_labels(node),
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
            # Track D increment 16. `None` when the file is too large or of a
            # kind nobody offers, and the note is kept either way -- *capture
            # is durable before it is clever*, and losing a thought because its
            # photo was oversized is the worst reading of a size limit.
            spec = services.attachment_from_upload(request.FILES.get("attachment"))
            node = services.capture(
                request.user,
                content=content,
                captured_at=now,
                source=NodeSource.WEB,
                actor=request.user.get_username(),
                attachments=[spec] if spec is not None else (),
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
def tag_node(request, public_id):
    """Name a note that already exists.

    The capture-page box only helps notes written from now on, which left the
    case that produced it unsolved: four notes about films, already captured,
    and no way to say "these are films". A thought is often only recognisable
    as part of something once the something exists.

    **Expected use, from Vince, August 15, 2026:** obvious categories — movies,
    books, a particular project — and not much else. Most capture is random and
    stays untagged, which is the design rather than a shortfall. That is why
    this is one line on a card and not a tag manager: it should cost nothing to
    ignore thirty times and be there the once it is wanted.

    Owner-scoped in the lookup, so somebody else's note is not found rather
    than found and refused.
    """
    node = queries.live_nodes(request.user).filter(public_id=public_id).first()
    if node is None:
        return redirect("capture")

    labels = request.POST.get("tags", "").split(",")
    if any(label.strip() for label in labels):
        services.record_typed_tags(
            node, labels, now=timezone.now(), actor=request.user.get_username()
        )
    return redirect("capture")


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
    # Read once, so the proposals and the questions describe the same instant.
    # Two clocks on one page is how "12 days" and "13 days" appear together.
    now = timezone.now()
    hypotheses = services.open_review(
        request.user,
        now=now,
        actor=request.user.get_username(),
        limit=REVIEW_LIMIT,
    )

    # Track C increment 12. On the review surface because that is where a
    # reflection belongs -- and shown only when there is enough to compare,
    # because a rate over one night is a number that will be believed and
    # should not be.
    #
    # The reading carries its own denominator and its own absence sentence, and
    # the template prints all three together: a number that can be separated
    # from its denominator is a number somebody reads as *of all mornings*.
    comparison = reflection.after_a_recorded_night(
        request.user,
        "alcohol.consumed",
        "energy.low",
        since=(now - timedelta(days=90)).date(),
        until=now.date(),
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
    # Loose ends above proposals, and that is not a layout preference. A
    # proposal asks *is this connection real?* -- the system claiming
    # something. A question asks *did you settle this?* -- a fact about the
    # person's own corpus with no claim in it. The second is cheaper to answer
    # and more often worth answering, and burying it under a queue of guesses
    # is how it goes unread.
    #
    # **Reading these surfaces nothing.** The call above stamps
    # `first_surfaced_at` on every proposal it returns, because a proposal
    # shown without starting its window makes silence meaningless. A question
    # has no window: nothing expires, nothing ripens, and leaving it alone is a
    # permanent and costless answer. The two mechanics share this page and must
    # not share that behaviour.
    questions = queries.unresolved_questions_in_context(request.user, now=now)

    return render(
        request,
        "mind/review.html",
        {
            "proposals": proposals,
            "remaining": remaining,
            "questions": questions,
            "comparison": comparison,
        },
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


def _own_question_or_none(request, public_id):
    """Owner-scoped in the query, so a caller cannot forget the second half."""
    return Node.objects.filter(
        public_id=public_id, owner=request.user, deleted_at__isnull=True
    ).first()


@login_required
@require_http_methods(["POST"])
def resolve_question(request, public_id):
    """"Settled", with nothing to point at.

    The better answer, where it exists, is an `answers` edge naming *what*
    settled it. This is for the case where nothing can be named — and refusing
    that case is how a loose end stays on a list forever.
    """
    node = _own_question_or_none(request, public_id)
    if node is not None:
        services.resolve_question(
            node, now=timezone.now(), actor=request.user.get_username()
        )
    return redirect("review")


@login_required
@require_http_methods(["POST"])
def dismiss_question(request, public_id):
    """"This was never a question."

    The correction signal for `looks_like_a_question`, which is three text
    signals and reads a rhetorical question as a real one by construction.
    Kept distinct from resolving: collapsing the two would spend the only
    feedback that heuristic will ever get.
    """
    node = _own_question_or_none(request, public_id)
    if node is not None:
        services.dismiss_as_question(
            node, now=timezone.now(), actor=request.user.get_username()
        )
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
            # Every value, not a curated few. The set is small and closed, and
            # offering four of seven would leave three unreachable in exactly
            # the way all seven have been until now.
            "kinds": ConceptType.choices,
            "is_a_person": canonical.concept_type == ConceptType.PERSON,
        },
    )


# What each event reads as on a page a person looks at.
#
# **The log's vocabulary is not a person's**, and the first render of the note
# page proved it by putting `facet_confirmed`, `mention_confirmed` and
# `task_completed` on screen. Those names are chosen for what a *reading* can
# filter on, which is a different job from what somebody can read -- and
# `principles.md` calls the gap between them a bend.
#
# **Past tense and no subject**, so the same phrase works under both headings:
# "what came of it" wants *became a task*, and "what else was going on" wants
# the same words about a different note.
EVENT_PHRASES = {
    "captured": "written",
    "revised": "corrected",
    "imported": "imported",
    "reviewed": "reviewed",
    "archived": "put away",
    "concept_confirmed": "a name confirmed",
    "concept_retired": "a name retired",
    "facet_confirmed": "became a task",
    "facet_dismissed": "an offer declined",
    "mention_confirmed": "tagged",
    "edge_created": "linked to another note",
    "edge_removed": "a link removed",
    "alias_merged": "two names merged into one",
    "hypothesis_resolved": "a suggested connection answered",
    "thread_articulated": "a thread named",
    "task_completed": "the task finished",
    "task_reopened": "the task reopened",
    "task_archived": "the task put away",
    "commitment_changed": "the commitment changed shape",
    "commitment_ended": "the commitment ended",
    "focus_pinned": "chosen for a day",
    "focus_released": "put down again",
    "week_reviewed": "the week reviewed",
    "intention_set": "an intention set",
    "outcome_chosen": "an outcome chosen",
    "deleted": "deleted",
    "purged": "erased",
}

# How two notes relate, in words. Small enough to spell out, and spelled out
# for the same reason as the phrases above.
RELATION_PHRASES = {
    "relates_to": "related",
    "answers": "answers this",
}


def phrase_for(event_type):
    """A person's words for one event, falling back to the log's.

    **The fallback is the part that matters.** `EventType` is open by design --
    new kinds are new values, not new tables -- so a mapping that returned
    nothing for an unmapped one would render a blank row. Degrading to the raw
    name is ugly and truthful, which is the right order.
    """
    return EVENT_PHRASES.get(event_type) or event_type.replace("_", " ")


def relation_phrase_for(relation):
    return RELATION_PHRASES.get(relation) or relation.replace("_", " ")


def _phrased(development_chain):
    """The same chain, with each development's phrase chosen."""
    return replace(
        development_chain,
        developments=[_readable(d) for d in development_chain.developments],
    )


def _occasion(occasion):
    """One occasion, with its withheld subjects counted rather than listed.

    R5 withholds a deleted or archived note's content and keeps its event,
    which is right -- capturing it was a real act. Rendering each one as *a
    note that is no longer shown* is not: on a real page it produced dozens of
    identical rows that buried everything else.

    **Counted, not dropped.** Dropping them would quietly shrink a morning, and
    the reason the events are kept at all is that they happened.
    """
    shown = [n for n in occasion.neighbours if not n.subject_withheld]
    withheld = len(occasion.neighbours) - len(shown)

    # Rows that name something keep their own line. Rows that cannot -- an
    # event with no note and no task renders as its phrase alone -- are grouped
    # by phrase, because seven names confirmed in one sitting is seven
    # identical lines and a page cannot be read through repetition. The same
    # defect as the withheld count above, one variant over, and found the same
    # way: by looking at the page.
    named = [_readable(n) for n in shown if n.node is not None or n.task is not None]
    bare = {}
    for neighbour in shown:
        if neighbour.node is None and neighbour.task is None:
            phrase = phrase_for(neighbour.event_type)
            bare[phrase] = bare.get(phrase, 0) + 1

    return {
        "began": occasion.began,
        "ended": occasion.ended,
        "moments": [_readable(m) for m in occasion.moments],
        "neighbours": named,
        "also": sorted(bare.items()),
        "withheld": withheld,
        "omitted": occasion.omitted,
    }


def _readable(neighbour):
    """One `Neighbour`, with its phrase already chosen.

    Resolved here rather than in the template, because a Django template cannot
    call a function with an argument -- and a filter registered to do it would
    put the mapping somewhere a test cannot reach it by name. The fallback is
    the part worth testing, so it stays importable.
    """
    return {
        "phrase": phrase_for(neighbour.event_type),
        "occurred_at": neighbour.occurred_at,
        "origin": neighbour.origin,
        "node": neighbour.node,
        "task": neighbour.task,
        # So the page can say *a note you cannot see* rather than a bare verb.
        "subject_withheld": neighbour.subject_withheld,
    }


@login_required
def note(request, public_id):
    """One note, and everything the graph has accreted around it.

    **Track E increment 19, and the first caller either of Track A's reads has
    ever had.** Five increments built a time axis and two reads over it, and
    nothing used them — which by `principles.md` made the whole track a
    deferral wearing a completion's clothes. The two questions a person asks
    about an old note are exactly the two those reads answer: *what else was
    going on when I wrote this*, and *what came of it*.

    **Read-only on purpose.** Nine dark services are waiting on this page —
    `revise`, `delete_node`, `archive_node`, `unlink`, `reopen_question` — and
    they stay dark. `temporal-substrate-plan.md` puts the correction surface at
    increment 21 and person-anchoring at 20; hanging five affordances on a page
    nobody has looked at yet is how a surface gets designed twice.

    **`live_nodes` rather than a bare lookup**, which is R5's rule reaching its
    door: a deleted or archived note is a 404 here, and `clarice/recall.py`
    already withholds their content from both reads. The rule was written and
    tested before the surface existed, which is the only reason this increment
    does not have to invent it.

    **D19 is not answered here.** The neighbourhood is anchored on one instant
    — when the note was captured — because that is what `around()` takes. The
    plural version, unioning the neighbourhoods of a subject's whole life, is
    that decision's to make, and guessing at it in a template would settle it
    by accident.
    """
    found = queries.live_nodes(request.user).filter(public_id=public_id).first()
    if found is None:
        # 404 rather than a redirect, and rather than 403 for someone else's:
        # whether a note exists is itself the person's.
        raise Http404("no such note")

    held_roles = set(
        Facet.objects.filter(
            node=found, retired_at__isnull=True, kind__in=services.MEMORY_ROLES
        ).values_list("kind", flat=True)
    )
    return render(
        request,
        "mind/note.html",
        {
            "node": found,
            "body": queries.current_body(found),
            "labels": queries.confirmed_concept_labels(found),
            # Track B increment 6. Offered as checkboxes because roles are
            # multi-valued by design -- a memory is several things at once,
            # which is exactly what D6's answer had to preserve.
            "roles": [
                {
                    "value": role,
                    "label": FacetKind(role).label,
                    "held": role in held_roles,
                }
                for role in services.MEMORY_ROLES
            ],
            # Earlier wordings, oldest first. Shown rather than hidden: a
            # surface that concealed what it corrected would be an edit box,
            # and the reason revisions are kept at all is being able to see
            # them. `original_content` is the first entry and is never a
            # `Revision` row -- it is what the note said before any of them.
            "earlier": [
                revision.body
                for revision in found.revisions.order_by("seq")[
                    : found.revisions.count() - 1
                ]
            ]
            if found.revisions.exists()
            else [],
            "first_said": found.original_content,
            "was_corrected": found.revisions.exists(),
            "connections": [
                {"relation": relation_phrase_for(relation), "node": other}
                for relation, other in queries.connections_of(found)
            ],
            # **"Else" means else.** Anything whose subject is this note is
            # filtered out -- its own capture first of all, which the first
            # render listed as something else that was going on. Its later
            # events belong under "what came of it", where they are the answer
            # rather than the background.
            # **D19, and this page was the caller it names.** It anchored on
            # `captured_at` alone, which answered about the morning the note was
            # written and dropped the rest of its life -- a note turned into a
            # task two months later had a second moment that nothing here could
            # see. `context_of` unions the neighbourhoods of the subject's own
            # moments and merges the ones close enough to be one sitting, which
            # is exactly the resolution the decision says no caller should
            # re-derive.
            "occasions": [_occasion(occasion) for occasion in
                          recall.context_of(request.user, found).occasions],
            "what_came_of_it": _phrased(recall.since(request.user, found)),
            # S14's done-means, and v3's *Unify*: the day it belongs to, the
            # project it was inside, and what was committed to that week.
            #
            # **A read, where the plan asks for typed links** -- Part 1 says
            # facts, not derivations, and all three are derivable: the day from
            # `captured_at`, the project along the chain the merger already
            # records, the week's commitments from that week's rows. Storing
            # them would be three copies free to disagree with their sources.
            "surrounding": recall.what_surrounded(request.user, found),
            # **This page declares itself a Recollection** -- Track B increment
            # 7. It was already doing one ad hoc: the fragment, what was
            # nearby, what came of it, with no name for the kind of
            # remembering that is. What naming it adds is the material the
            # other sections cannot reach -- a note a year away that a person
            # confirmed is about the same thing, which no temporal window will
            # ever find. The failure that matters here is context too thin to
            # resume, so nothing is filtered for length or dormancy.
            "related": retrieval.retrieve(
                retrieval.Moment(
                    owner=request.user,
                    mode=retrieval.Mode.RECOLLECTION,
                    anchor=found,
                )
            ),
        },
    )


def _open_sitting(user, *, now):
    """This person's open sitting, opened if there is not one.

    A refresh mid-dump is ordinary, and two sittings for one would split the
    budget the sitting was given.
    """
    session = user.capture_sessions.filter(processed_at__isnull=True).first()
    if session is None:
        session = services.begin_capture_session(user, now=now)
    return session


@login_required
@require_http_methods(["GET", "POST"])
def dump(request):
    """Empty your head -- Track D increment 14.

    **Safe only because increment 13 exists.** Without session-aware budgeting
    the first dump is the one that teaches somebody to skim past the review
    surface, and the plan calls that unrecoverable -- which is why the ordering
    is the feature's safety rather than a preference.

    **A fragment is a submission, not a sentence.** One *keep and continue*,
    one `Node`, and the person draws the boundaries. Nothing here segments
    anything: `services._SENTENCE` splits a `DailyEntry` so the journal parser
    can cite a line, and it has never created a node.

    **A multiline paste gets a preview and a question, never a guess.** This is
    the surface where somebody is least able to predict what was done with what
    they typed.
    """
    now = timezone.now()
    session = _open_sitting(request.user, now=now)
    pending = None

    if request.method == "POST":
        content = request.POST.get("content", "")
        split = request.POST.get("split")
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        if not content.strip():
            pass
        elif len(lines) > 1 and split is None:
            # Asked, not guessed. Nothing is written until the question is
            # answered -- a preview that had already saved something would be
            # a notification rather than a question.
            pending = {"content": content, "lines": lines}
        elif split == "yes":
            for index, line in enumerate(lines):
                services.capture(
                    request.user,
                    content=line,
                    captured_at=now + timedelta(seconds=index),
                    source=NodeSource.WEB,
                    actor=request.user.get_username(),
                    session=session,
                )
        else:
            services.capture(
                request.user,
                content=content.strip(),
                captured_at=now,
                source=NodeSource.WEB,
                actor=request.user.get_username(),
                session=session,
            )

    return render(
        request,
        "mind/dump.html",
        {
            "session": session,
            "pending": pending,
            "kept": session.fragments.count(),
        },
    )


@login_required
@require_http_methods(["POST"])
def finish_dump(request):
    """End the sitting, which is the only moment anything comes back.

    Rules 3 to 7 in one call: the producers run once over the whole sitting,
    aggregated and capped, and the session is marked processed so the nightly
    pass cannot reach its fragments one at a time and walk around the budget.
    """
    session = request.user.capture_sessions.filter(processed_at__isnull=True).first()
    shown = (
        services.end_capture_session(session, now=timezone.now(), owner=request.user)
        if session is not None
        else []
    )
    return render(
        request,
        "mind/dump_done.html",
        {"shown": shown, "kept": session.fragments.count() if session else 0},
    )


@login_required
@require_http_methods(["GET"])
def start(request):
    """Two entrances, and only the words their own material has earned.

    Track D increment 15, and the answer to `commercial-blueprint.md`'s
    long-open *explain the six invented concepts somewhere in the product,
    once*. A tour was the obvious answer and the plan refuses it: a concept
    explained before it exists is a word attached to nothing.
    """
    return render(
        request,
        "mind/start.html",
        {
            "new_here": orientation.is_new_here(request.user),
            "concepts": orientation.what_their_material_demonstrates(request.user),
        },
    )


@login_required
@require_http_methods(["GET"])
def attachment(request, public_id):
    """Hand back one file -- Track D increment 16.

    Owner-scoped through `live_nodes`, so somebody else's file is *not found*
    rather than found and refused, and a deleted note's file is not served: a
    file is part of the note, and `delete_node`'s promise covers both.
    """
    found = Attachment.objects.filter(
        public_id=public_id,
        deleted_at__isnull=True,
        node__in=queries.live_nodes(request.user),
    ).first()
    if found is None:
        raise Http404("no such file")

    # `Content-Disposition: attachment` rather than inline. A PDF rendered in
    # the page is a document with a script engine behind it, on a same-origin
    # response -- and the allowlist that keeps SVG out is worth nothing if the
    # types that are allowed get to execute.
    response = HttpResponse(bytes(found.content), content_type=found.mime_type)
    response["Content-Disposition"] = f'attachment; filename="{found.public_id}"'
    return response


@login_required
@require_http_methods(["GET"])
def ask_page(request):
    """A question box over the retrieval pipeline -- Track E increment 22.

    **Extractive, cited, per-mode**, and every one of the three is a refusal of
    something easier. Extractive rather than generated, because a second mind
    that writes new prose about your life is one you have to fact-check.
    Cited, because without it a person can only distrust an answer rather than
    argue with it. Per-mode by an enumerable rule rather than a classifier,
    because a rule can be read and disagreed with.

    **Declined earlier the same day and built once the pipeline existed.** On
    nothing beneath it this is `search_ranked` with a prompt in front, failing
    silently -- which is what made the thin version worth refusing.
    """
    question = (request.GET.get("q") or "").strip()
    return render(
        request,
        "mind/ask.html",
        {"q": question, "answer": ask.answer(request.user, question) if question else None},
    )


@login_required
@require_http_methods(["POST"])
def say_concept_kind(request, public_id):
    """Say what kind of thing this is -- Track E increment 20.

    `ConceptType` has had seven values and one writer since the first slice.
    Production holds eleven concepts and every one is `unknown`, which is not a
    judgement anybody made -- it is the absence of a control.
    """
    found = ConceptCandidate.objects.filter(
        public_id=public_id, owner=request.user, retired_at__isnull=True
    ).first()
    if found is None:
        return redirect("concepts")

    try:
        services.say_what_kind(found, kind=request.POST.get("concept_type", ""))
    except services.MindError:
        # Refused rather than coerced to `UNKNOWN`, which would be
        # indistinguishable from the state this exists to end.
        pass
    return redirect("concept", public_id=public_id)


@login_required
def person(request, public_id):
    """One person, across everything you have written -- Track E increment 20.

    **What this adds over the concept page** are the two joins the plan names.
    A concept page lists the notes that mention something; neither the
    commitments that grew out of those notes nor the shape of a name across
    time is reachable from that list, and both are what makes a person more
    than a tag.

    **Not a person, not this page.** A page called *people* rendering a motif
    would mean nothing, so it redirects to the concept page -- the concept is
    real and there is somewhere right for it to be.
    """
    found = ConceptCandidate.objects.filter(
        public_id=public_id, owner=request.user, retired_at__isnull=True
    ).first()
    if found is None:
        return redirect("concepts")

    canonical = queries.canonical_concept(found)
    if canonical.concept_type != ConceptType.PERSON:
        return redirect("concept", public_id=public_id)

    return render(
        request,
        "mind/person.html",
        {
            "person": canonical,
            "nodes": queries.nodes_mentioning(request.user, canonical),
            "commitments": queries.commitments_involving(request.user, canonical),
            "months": queries.when_they_came_up(request.user, canonical),
        },
    )


@login_required
@require_http_methods(["POST"])
def recollection_was_thin(request, public_id):
    """*There was more to that morning* -- Track B increment 10.

    The search page's miss button, borrowed verbatim, which is the source D8
    registered rather than a new mechanism. It is the strongest instrument in
    this project for the same reason there: **the person knows something is
    missing**, so the failure is loud and recordable where a plausible metric
    would be neither.

    It gives Recollection the only other honest signal retrieval has. Planning
    has none yet and Resurfacing cannot have one, and `/numbers/` says both
    rather than reporting a zero.
    """
    node = queries.live_nodes(request.user).filter(public_id=public_id).first()
    if node is None:
        raise Http404("no such note")

    services.record_retrieval_miss(
        request.user,
        # The note, not a phrase. What was missed here is context around
        # something, and the something is the only part that can be named.
        query_text=f"recollection around {node.public_id}",
        context=MissContext.RECOLLECTION,
        now=timezone.now(),
    )
    return redirect("note", public_id=public_id)


@login_required
@require_http_methods(["POST"])
def say_what_note_is(request, public_id):
    """Say what kinds of memory this note holds -- Track B increment 6.

    **Never asked at capture**, which is the product's first principle and the
    reason this lives here rather than on the box. A note is written without
    answering anything; what it *is* becomes answerable later, when the answer
    exists.
    """
    node = queries.live_nodes(request.user).filter(public_id=public_id).first()
    if node is None:
        raise Http404("no such note")

    try:
        services.say_what_this_is(
            node,
            roles=request.POST.getlist("roles"),
            now=timezone.now(),
            actor=request.user.get_username(),
        )
    except services.MindError:
        # Refused rather than partly applied. A role nobody offers arriving in
        # a POST is a client sending something the form never rendered.
        pass
    return redirect("note", public_id=public_id)


@login_required
@require_http_methods(["POST"])
def revise_note(request, public_id):
    """Correct what a note says — Track E increment 21.

    **The door `revise` never had.** The service, the model and the search
    integration have been complete and tested since the first slice, and
    `Revision` is empty in production because nothing could write one — one of
    the two dark symbols the August 21 inventory found reading most
    convincingly as working.

    **`original_content` is untouched, which is the design and not a
    limitation.** What was first written survives every correction, and search
    finding a word somebody edited out is that working rather than a bug —
    which is why the page shows the earlier wording rather than hiding it.

    **`/privacy/` leans on this.** *"You can see what is held, correct it, take
    a copy, or have it deleted"*, with anything the interface does not cover
    done by hand. Correction has been the hand-done one; now it is not.
    """
    node = queries.live_nodes(request.user).filter(public_id=public_id).first()
    if node is None:
        raise Http404("no such note")

    body = request.POST.get("body", "")
    if body.strip():
        # Refused rather than silently emptying a note: `EmptyNode` is the rule
        # at capture, and a correction that emptied one would walk round it.
        services.revise(
            node,
            body=body.strip(),
            now=timezone.now(),
            actor=request.user.get_username(),
        )
    return redirect("note", public_id=public_id)


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

    **Three sections since August 20, 2026** — notes, tasks and days —
    `design/search-plan.md` increment 3, and D2's answer: this page rather than a
    new one. It lives under `/mind/` while searching both cores, which is the
    prefix naming the smaller half again; taken deliberately, because the
    alternative was splitting search from the miss button, and the button is the
    only instrument this project has for judging whether search works at all.

    **Sectioned, and ranked within each section, never merged.** `SearchRank`
    compares documents within one set and means nothing across two, so one
    combined list would be ordered by a number that does not exist. Each section
    also carries its own total, for the reason the notes section already did.
    """
    q = (request.GET.get("q") or "").strip()
    results = []
    total = 0
    tasks = []
    tasks_total = 0
    days = []
    days_total = 0
    # One parse for every section. Three sections that disagree about whether a
    # second word narrows would look like a ranking bug and would not be one --
    # see `clarice/search.py`, which exists for exactly this.
    query = to_query(q)
    if query is not None:
        matching_tasks = lists_search.search_tasks(request.user, q)
        tasks_total = matching_tasks.count()
        tasks = list(matching_tasks[:RECENT_LIMIT])

        matching_days = daily_reads.search_entries(request.user, q)
        days_total = matching_days.count()
        days = list(matching_days[:RECENT_LIMIT])

        # **This page declares itself a Lookup** -- Track B increment 7. The
        # mode is not decoration: it is what admits a note the Discovery floors
        # would refuse, and "Mum's birthday, 14 March" is twenty-four
        # characters against a `MIN_LENGTH` of 120. The failure that matters
        # here is a miss, and every floor is a way to produce one.
        found = retrieval.retrieve(
            retrieval.Moment(
                owner=request.user, mode=retrieval.Mode.LOOKUP, text=q
            ),
            limit=RECENT_LIMIT,
        )
        # Counted before slicing, because the count is the point: a page that
        # returns thirty of thirty-five and says nothing is a page that invites
        # the miss button below it to be pressed for a note it simply did not
        # show. That records a truncation as a retrieval failure, in the one
        # signal where the right answer is known.
        total = queries.search_ranked(request.user, query).count()
        nodes = [result.node for result in found]
        current = queries.current_text_matches(nodes, query)
        results = [
            {
                "node": result.node,
                "body": queries.current_body(result.node),
                # Increment 9. Not decoration: it is the only thing that lets
                # somebody argue with an eligibility rule rather than learning
                # to distrust the page -- and the concept generator can return
                # a note without the typed word in it at all, which is baffling
                # unless the page says why.
                "why": result.why,
                # Matched only in text since edited away. Kept as a result --
                # the original is preserved on purpose -- and labelled, so the
                # word somebody typed not being in the note they are shown is
                # explained rather than baffling.
                "superseded": result.node.pk not in current,
            }
            for result in found
        ]
    return render(
        request,
        "mind/search.html",
        {
            "q": q,
            "results": results,
            "total": total,
            "truncated": total > len(results),
            "tasks": tasks,
            "tasks_total": tasks_total,
            "tasks_truncated": tasks_total > len(tasks),
            "days": days,
            "days_total": days_total,
            "days_truncated": days_total > len(days),
            # Said once, when every section is empty. Three stacked empty-states
            # would announce failure three times for a search that found
            # something -- and noise directly above the miss button is how that
            # button stops being read.
            "nothing_anywhere": bool(q) and not (results or tasks or days),
            "limit": RECENT_LIMIT,
        },
    )


@login_required
@require_http_methods(["POST"])
def record_miss(request):
    """"I know I wrote this and can't find it", with what the search had shown.

    The counts are **recomputed from the query rather than posted by the form**.
    Hidden inputs would be cheaper and would make the one signal a decision is
    measured against forgeable by the page that submits it; three counts on an
    action somebody takes a handful of times a year is the better trade.
    """
    q = (request.POST.get("q") or "").strip()
    query = to_query(q)
    services.record_retrieval_miss(
        request.user,
        query_text=request.POST.get("q", ""),
        now=timezone.now(),
        notes_found=(
            queries.search_ranked(request.user, query).count()
            if query is not None
            else 0
        ),
        tasks_found=(
            lists_search.search_tasks(request.user, q).count() if query is not None else 0
        ),
        days_found=(
            daily_reads.search_entries(request.user, q).count()
            if query is not None
            else 0
        ),
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
