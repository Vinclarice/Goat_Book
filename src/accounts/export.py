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

from accounts.models import Invitation, PersonalAccessToken, User
from daily.models import DailyEntry, DailyFocus
from lists.models import (
    ChecklistStep,
    Item,
    List,
    Project,
    RecurringCommitment,
    Tag,
)
from money.models import (
    Account,
    BalanceReading,
    Bill,
    BillSeries,
    MoneyCategory,
)
from mind import queries as mind_queries
from mind.models import (
    CaptureSession,
    Decision,
    Source,
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
    # Who this person invited, and whether they came -- S1. Exported rather
    # than withheld even though `public_id` is the credential: an invitation is
    # a single-use, expiring link to an account with nothing in it, the export
    # goes to the person who minted it, and the same id is already on their own
    # admin page. Withholding it would make *who have I invited* one of the few
    # questions their archive could not answer.
    Invitation: "invitations",
    List: "areas",
    Project: "projects",
    Item: "items",
    ChecklistStep: "checklist_steps",
    # **`MoneyLine: "bills"` was here until September 1, 2026.** It was owned
    # through its task rather than directly -- a sidecar has no owner of its
    # own, which is exactly the shape that goes missing from a list like this,
    # and the test above is what caught it the first time. Increment 8 of
    # bill-as-a-model-plan.md deleted the model; the two keys below carry every
    # bill a person has, owned directly.
    # **Dark tables, exported anyway** -- increment 1 of
    # bill-as-a-model-plan.md. Nothing writes them yet, so both keys are empty
    # lists today; naming them now is what stops the export silently missing a
    # person's whole financial history the day increment 4 starts writing them,
    # which is precisely the class of gap the test above exists to catch.
    BillSeries: "bill_series",
    Bill: "bill_occurrences",
    Account: "accounts_with_balances",
    MoneyCategory: "money_categories",
    BalanceReading: "balances",
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
    # What somebody read -- S15. An archive that lost it would keep every
    # note and forget where any of them came from.
    Source: "sources",
    # What was chosen over what -- S11. An archive that kept every note and
    # forgot every decision would lose the part that took the longest.
    Decision: "decisions",
    # A sitting's own record -- Track D increment 13. Provenance rather than
    # content, and exported for exactly that reason: without it a person's
    # archive says when each fragment was written and not that forty of them
    # were one evening of emptying their head.
    CaptureSession: "capture_sessions",
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


# DARK: no production caller. **Deliberately so -- this one holds a published
# promise from the test suite rather than from the export.**
# `_payload` hand-enumerates every model; this enumerates every model that
# *exists*, and `test_export.py` asserts the second is a subset of the first.
# That is what makes `/privacy/`'s "everything" true, and the privacy template
# cites this function by name for exactly that reason.
# Decision registered: production-dark on purpose, permanently. Deleting it
# would not break the export -- it would unhold the promise, silently, and the
# next model added to an owned app would go unexported with nothing failing.
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


# DARK: no production caller. The other half of the guard above -- the
# completeness test needs to know which key each model should have arrived
# under, and `EXPORT_KEYS` is the only place that says.
# Decision registered: production-dark on purpose, permanently, for the reason
# `owned_models` gives in full.
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
            "invitations": _rows(user.invitations_sent.all()),
        },
        "tasks": {
            "areas": _rows(List.objects.filter(owner=user)),
            "projects": _rows(Project.objects.filter(owner=user)),
            "items": _rows(Item.objects.filter(owner=user), many_to_many=("tags",)),
            "checklist_steps": _rows(ChecklistStep.objects.filter(owner=user)),
            # **Owned directly**, which is the point of the split: a bill
            # stops being reached through a task. A `bills` key sat above these
            # until September 1, 2026 and reached a sidecar through its task's
            # owner; these two carry a person's whole financial history now.
            "bill_series": _rows(BillSeries.objects.filter(owner=user)),
            "bill_occurrences": _rows(Bill.objects.filter(owner=user)),
            # **Named `accounts_with_balances`, not `accounts`.** The archive
            # already has an `account` key for the person's own login details,
            # and two things called account in one payload is how somebody
            # reading their own export learns the wrong thing about it.
            "accounts_with_balances": _rows(Account.objects.filter(owner=user)),
            # A person's own vocabulary for their money, which is theirs to
            # take with them like anything else they typed.
            "money_categories": _rows(MoneyCategory.objects.filter(owner=user)),
            # Reached through the account rather than by an owner of their own:
            # a reading belongs to an account and the account belongs to a
            # person, which is the same shape `bills` uses through its item.
            "balances": _rows(BalanceReading.objects.filter(account__owner=user)),
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
            "sources": _rows(Source.objects.filter(owner=user)),
            "decisions": _rows(Decision.objects.filter(owner=user)),
            "capture_sessions": _rows(
                CaptureSession.objects.filter(owner=user)
            ),
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
