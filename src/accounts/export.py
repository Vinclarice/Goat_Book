"""Everything one account owns, as a file they can take away.

The other half of `commercial-blueprint.md`'s legal blocker. Deletion without
export is a trap — the only way to leave would be to destroy everything.

**Two formats, answering different questions.** `clarice.json` is the complete
record, every row of every owned model across both cores including the activity
log, and is what could be read back by a machine. `notes.md` and `tasks.md` are
what a person can open, which is what "portable" has to mean if it means
anything.

**Hand-built rather than `dumpdata`.** That format is pk-keyed and
Django-internal, and it serialises every concrete field — the password hash and
the token hashes included. [SECRETS] names what must never leave, and
`accounts/tests/test_export.py` asserts each one by name against the whole
archive rather than trusting this list to be applied correctly.
"""

import json
import zipfile
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from accounts.models import PersonalAccessToken, User
from daily.models import DailyEntry, DailyFocus
from lists.models import ChecklistStep, Item, List, Project, RecurringCommitment, Tag
from mind import queries as mind_queries
from mind.models import (
    ActivityEvent,
    Attachment,
    ConceptCandidate,
    ConnectionHypothesis,
    Edge,
    Facet,
    HypothesisMember,
    Mention,
    Node,
    RetrievalMiss,
    Revision,
    SentenceEmbedding,
)
from review.models import (
    PlanningSession,
    WeeklyIntention,
    WeeklyOutcome,
    WeeklyReview,
)
from routines.models import Routine, RoutineOccurrence, RoutinePause

# Never leaves the database. Both are one-way hashes, so exporting them would
# hand somebody a credential-shaped string that is useless to them and useful to
# anyone who steals the file.
SECRETS = frozenset({"password", "token_hash"})


# Every model that can hold one account's data, and the key it travels under.
#
# This exists to be checked rather than to be read: `test_export.py` asserts
# that every owned model in the tree appears here and that every key here
# appears in the payload. D12 was three models nobody had noticed were missing
# -- HypothesisMember, Attachment and SentenceEmbedding -- against a docstring
# promising "every row of every owned model across both cores". The promise was
# not checkable, so it was not true, and the person who would find out is
# somebody who has already deleted their account.
EXPORT_KEYS = {
    User: "account",
    PersonalAccessToken: "tokens",
    List: "areas",
    Project: "projects",
    Item: "items",
    ChecklistStep: "checklist_steps",
    Tag: "tags",
    RecurringCommitment: "commitments",
    DailyEntry: "entries",
    DailyFocus: "focus",
    Routine: "routines",
    RoutineOccurrence: "occurrences",
    RoutinePause: "pauses",
    WeeklyReview: "reviews",
    WeeklyIntention: "week_intentions",
    PlanningSession: "planning_sessions",
    WeeklyOutcome: "week_outcomes",
    Node: "nodes",
    Revision: "revisions",
    Facet: "facets",
    Attachment: "attachments",
    ConceptCandidate: "concepts",
    Mention: "mentions",
    Edge: "edges",
    ConnectionHypothesis: "hypotheses",
    HypothesisMember: "hypothesis_members",
    SentenceEmbedding: "sentence_embeddings",
    RetrievalMiss: "retrieval_misses",
    ActivityEvent: "events",
}

# The apps whose rows belong to an account. `mind` and the task core both, which
# is the whole point of the promise -- an export that covered one core would be
# half a departure.
OWNED_APPS = ("accounts", "lists", "daily", "routines", "review", "mind")


def owned_models():
    """Every concrete model in this account's apps, minus what nobody owns.

    Auto-created many-to-many through tables are excluded: their contents leave
    as the `_ids` lists on either side, so exporting the join as well would say
    the same thing twice.
    """
    from django.apps import apps

    found = []
    for label in OWNED_APPS:
        for model in apps.get_app_config(label).get_models():
            if model._meta.auto_created:
                continue
            found.append(model)
    return found


def export_key(model):
    """The payload key this model's rows travel under."""
    return EXPORT_KEYS[model]


def _value(value):
    """JSON for the field types this schema actually uses."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _rows(queryset, *, many_to_many=()):
    """Every concrete field of every row, minus the secrets.

    `attname` rather than `name`, so a foreign key exports as `owner_id` — a
    plain integer that survives leaving this application, rather than a nested
    object or a broken reference.

    **`concrete_fields` excludes many-to-many by definition**, which is why
    `many_to_many` is a separate argument rather than something this works out.
    Tags exported as a list of names with nothing recording which tag was on
    which task, and an export is the only thing standing before irreversible
    erasure — so an association missing here is not missing, it is destroyed.
    Named per call so adding a relation to a model is a decision about the
    export rather than a silent omission.
    """
    out = []
    for obj in queryset:
        row = {
            field.attname: _value(getattr(obj, field.attname))
            for field in obj._meta.concrete_fields
            if field.name not in SECRETS and field.attname not in SECRETS
        }
        for name in many_to_many:
            # Ids, matching the foreign-key convention above: the related rows
            # are exported in full under their own key, so repeating them here
            # would say the same thing twice and disagree the first time one
            # changed.
            row[f"{name[:-1]}_ids"] = sorted(
                getattr(obj, name).values_list("pk", flat=True)
            )
        out.append(row)
    return out


def _payload(user, *, now):
    """The whole account, grouped the way a person would look for it."""
    nodes = Node.objects.filter(owner=user)

    return {
        "exported_at": now.isoformat(),
        "account": _rows([user])[0]
        | {
            # Its own key rather than a bare table: a token is a device somebody
            # connected, which is a fact about the account rather than a
            # separate kind of record.
            "tokens": _rows(user.tokens.all()),
        },
        "tasks": {
            "areas": _rows(List.objects.filter(owner=user)),
            "projects": _rows(Project.objects.filter(owner=user)),
            "items": _rows(Item.objects.filter(owner=user), many_to_many=("tags",)),
            "checklist_steps": _rows(ChecklistStep.objects.filter(owner=user)),
            "tags": _rows(Tag.objects.filter(owner=user)),
            "commitments": _rows(
                RecurringCommitment.objects.filter(owner=user),
                many_to_many=("tags",),
            ),
        },
        "days": {
            "entries": _rows(DailyEntry.objects.filter(owner=user)),
            "focus": _rows(DailyFocus.objects.filter(owner=user)),
        },
        "routines": {
            "routines": _rows(Routine.objects.filter(owner=user)),
            "occurrences": _rows(RoutineOccurrence.objects.filter(owner=user)),
            "pauses": _rows(RoutinePause.objects.filter(owner=user)),
        },
        "reviews": _rows(WeeklyReview.objects.filter(owner=user)),
        "week_intentions": _rows(WeeklyIntention.objects.filter(owner=user)),
        # When somebody sat down to plan a week, and what they said about it.
        # Theirs like everything else here -- and the guard below caught this
        # being missing before a person could, which is the second time that
        # test has earned its place on a model added to the review app.
        "planning_sessions": _rows(PlanningSession.objects.filter(owner=user)),
        "week_outcomes": _rows(WeeklyOutcome.objects.filter(owner=user)),
        "knowledge": {
            "nodes": _rows(nodes),
            "revisions": _rows(Revision.objects.filter(node__owner=user)),
            "facets": _rows(Facet.objects.filter(node__owner=user)),
            "concepts": _rows(ConceptCandidate.objects.filter(owner=user)),
            "mentions": _rows(Mention.objects.filter(node__owner=user)),
            "edges": _rows(Edge.objects.filter(owner=user)),
            "hypotheses": _rows(ConnectionHypothesis.objects.filter(owner=user)),
            # The span citations, which are a hypothesis's entire evidence:
            # without them a proposal exports as a confidence score and a label
            # with nothing behind it.
            "hypothesis_members": _rows(
                HypothesisMember.objects.filter(hypothesis__owner=user)
            ),
            "attachments": _rows(Attachment.objects.filter(node__owner=user)),
            # Large and machine-only, and exported anyway: the promise is every
            # row of every owned model, and a vector somebody paid for with
            # their own material is theirs whether or not they can read it.
            "sentence_embeddings": _rows(
                SentenceEmbedding.objects.filter(node__owner=user)
            ),
            "retrieval_misses": _rows(RetrievalMiss.objects.filter(owner=user)),
            # Included deliberately. It is a record of what this person did,
            # which is theirs; and since erasure deletes it rather than keeping
            # it, an export is the only chance to take it.
            "events": _rows(ActivityEvent.objects.filter(owner=user)),
        },
    }


def _notes_markdown(user):
    """Thoughts, newest first, with the day and whatever they were named.

    Archived and deleted nodes are included — this is everything the account
    holds, not everything currently in front of somebody. The status is on the
    line so the difference is visible rather than silent.
    """
    lines = ["# Notes", ""]
    nodes = Node.objects.filter(owner=user).order_by("-captured_at")
    if not nodes:
        lines.append("_Nothing captured._")

    for node in nodes:
        labels = mind_queries.confirmed_concept_labels(node)
        state = []
        if node.archived_at:
            state.append("archived")
        if node.deleted_at:
            state.append("deleted")

        lines.append(f"## {node.captured_at:%Y-%m-%d %H:%M}")
        meta = [node.source] + state
        lines.append(f"_{' · '.join(meta)}_")
        lines.append("")
        lines.append(mind_queries.current_body(node))
        if labels:
            lines.append("")
            lines.append("Tags: " + ", ".join(sorted(labels)))
        lines.append("")

    return "\n".join(lines)


def _tasks_markdown(user):
    """Tasks under the area they live in, with unfiled ones named as such.

    Unfiled is a real state rather than a gap: `Item.list` is nullable precisely
    so a commitment accepted from a thought needs no filing decision, and a file
    that hid those would be missing the ones that arrived most recently.
    """
    lines = ["# Tasks", ""]
    areas = list(List.objects.filter(owner=user).order_by("title"))

    def block(title, items):
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("_Nothing here._")
        for item in items:
            bits = [item.get_status_display()]
            if item.due_date:
                bits.append(f"due {item.due_date.isoformat()}")
            if item.recurrence:
                bits.append(item.recurrence)
            lines.append(f"- {item.text}  ({', '.join(bits)})")
            if item.notes:
                lines.append(f"  > {item.notes}")
        lines.append("")

    for area in areas:
        block(area.title, list(Item.objects.filter(owner=user, list=area)))

    unfiled = list(Item.objects.filter(owner=user, list__isnull=True))
    if unfiled:
        block("Unfiled", unfiled)

    # An account with no areas and no unfiled tasks would otherwise produce a
    # file containing the word "Tasks" and nothing else -- found by opening a
    # real export rather than by any assertion, and worth fixing because
    # somebody reading it cannot tell an empty account from a broken export.
    if not areas and not unfiled:
        lines.append("_No tasks in this account._")

    return "\n".join(lines)


def build_archive(user, *, now) -> bytes:
    """The whole account as a zip. Bytes rather than a file, so the caller
    decides whether it becomes a response, a test fixture or something on
    disk."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "clarice.json",
            json.dumps(_payload(user, now=now), indent=2, ensure_ascii=False),
        )
        archive.writestr("notes.md", _notes_markdown(user))
        archive.writestr("tasks.md", _tasks_markdown(user))
    return buffer.getvalue()
