from calendar import monthrange
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from clarice import life_log

from lists.models import (
    Account,
    MoneyCategory,
    AccountKind,
    BalanceReading,
    CadenceMode,
    Direction,
    ChecklistStep,
    Item,
    MoneyLine,
    List,
    Priority,
    Project,
    RecurringCommitment,
    Tag,
)


EMPTY_ITEM_ERROR = "You can't have an empty list item"
DUPLICATE_ITEM_ERROR = "You've already got this in your list"
ARCHIVED_DELETE_ERROR = "Only archived tasks can be permanently deleted"
CHECKLIST_STEP_ARCHIVED_ERROR = "Restore this task before editing its checklist"


class TaskServiceError(Exception):
    pass


class TaskConflict(TaskServiceError):
    pass


class InvalidTaskTransition(TaskServiceError):
    pass


def normalize_task_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_ITEM_ERROR)
    return normalized


def _duplicate_exists(for_list, text, excluding=None, owner=None):
    # An unfiled task is deduplicated against its owner's other unfiled tasks,
    # which reverses what this said an hour earlier. The argument then was that
    # unfiled tasks are not a list, so two thoughts sharing wording should both
    # be allowed through. What changed it is the retry: a phone re-sending a
    # share is the common case and a second identical commitment is the common
    # cost, while the thought itself is never at stake -- the node stays in the
    # knowledge core either way, and only the duplicate task is refused.
    if for_list is None:
        if owner is None:
            return False
        duplicates = Item.objects.filter(
            owner=owner, list__isnull=True, text=text
        ).exclude(status=Item.Status.ARCHIVED)
    else:
        duplicates = for_list.item_set.exclude(status=Item.Status.ARCHIVED).filter(
            text=text,
        )
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def create_list_with_item(owner, title, text):
    normalized_text = normalize_task_text(text)
    normalized_title = (title or "").strip() or normalized_text[:100]
    new_list = List.objects.create(owner=owner, title=normalized_title)
    Item.objects.create(list=new_list, text=normalized_text)
    return new_list


def create_area(owner, title, project=None):
    """An Area with no task in it -- Vince's call, August 10, 2026.

    create_list_with_item's first-task requirement was never a domain rule;
    it was the only creation path that existed before a Project needed its
    own way to grow an Area from nothing. The Agenda sidebar's "+ New area"
    form is unchanged and still asks for a first task -- this is a second,
    additive path, not a replacement.
    """
    normalized_title = (title or "").strip() or "Untitled list"
    if project is not None and project.owner_id != owner.id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    return List.objects.create(owner=owner, title=normalized_title, project=project)


def _next_position(for_list, owner=None):
    # Position orders a task within its Area. An unfiled task is ordered by the
    # agenda's own rules instead, so any value is unused -- but they still get
    # distinct ones, because a column full of zeroes makes a stable sort
    # impossible the day something does want to arrange them.
    if for_list is None:
        if owner is None:
            return 0
        highest = (
            Item.objects.filter(owner=owner, list__isnull=True)
            .exclude(status=Item.Status.ARCHIVED)
            .aggregate(Max("position"))["position__max"]
        )
        return 0 if highest is None else highest + 1
    highest = for_list.item_set.exclude(
        status=Item.Status.ARCHIVED,
    ).aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _clean_tag_names(tag_names):
    cleaned = []
    seen = set()
    for raw in tag_names or []:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def resolve_tags(owner, tag_names):
    """Public: capture.services reuses this rather than a second
    definition of what a tag is, per lists.Tag being the one owner-scoped
    tag vocabulary in the app.
    """
    return [
        Tag.objects.get_or_create(owner=owner, name=name)[0]
        for name in _clean_tag_names(tag_names)
    ]


def _anchor_commitment(item):
    """Give a repeating task the series identity it belongs to.

    Called on every path that can leave a root task repeating. Reuses an
    existing commitment rather than starting a second series, so a task that
    was paused and resumed stays one commitment with a gap in it.

    Always returns a commitment. It used to return None when the list had
    no owner, for anonymous-era rows; release D slice 6 made `List.owner`
    required and deleted those rows, so that branch became unreachable and
    went with them, exactly as this docstring used to promise it would.
    """
    if item.commitment_id is not None:
        commitment = item.commitment
        if commitment.ended_at is not None:
            commitment.ended_at = None
            commitment.save(update_fields=["ended_at"])
        return commitment
    # Seeded from the item at birth, not left empty. A commitment adopted at
    # completion (the legacy path, for rows predating this key) would
    # otherwise reach its first spawn with a blank template and produce a
    # blank task.
    commitment = RecurringCommitment.objects.create(
        owner=item.owner,
        text=item.text,
        list=item.list,
        cadence=item.recurrence,
        notes=item.notes,
    )
    item.commitment = commitment
    commitment.tags.set(item.tags.all())
    return commitment


def _end_commitment(item):
    """Stop a series accepting new occurrences, without disowning the old ones."""
    if item.commitment_id is None:
        return
    commitment = item.commitment
    if commitment.ended_at is None:
        commitment.ended_at = timezone.now()
        commitment.save(update_fields=["ended_at"])



def _write_through_to_commitment(item, **fields):
    """Editing an occurrence edits its commitment -- "this and future".

    Decided August 3, 2026; see recurring-commitment-vocabulary-plan.md 4.
    Renaming a recurring task means renaming the commitment, so the next
    occurrence carries the new name. Occurrences already completed keep their
    own text, notes and tags -- they are the snapshot of what actually ran,
    and nothing here touches them.

    A no-op for the ordinary one-off task, which has no commitment. That is
    the load-bearing part: inventing one here would turn every edited task
    into a series.
    """
    if item.commitment_id is None:
        return
    commitment = item.commitment
    tags = fields.pop("tags", None)
    if fields:
        for name, value in fields.items():
            setattr(commitment, name, value)
        commitment.save(update_fields=tuple(fields))
    if tags is not None:
        commitment.tags.set(tags)


@transaction.atomic
def create_item(for_list, text, due_date=None, tags=None, recurrence=None, owner=None):
    """A task, in an Area or standing on its own.

    `owner` is only needed when `for_list` is None; with an Area, the Area's
    owner is the answer and passing a different one would be inventing a second
    opinion. Callers that already pass an Area are unchanged, which is what
    makes this a widening rather than a migration of every call site.
    """
    if for_list is None and owner is None:
        raise TaskConflict("A task with no Area still has to belong to somebody")
    owner = for_list.owner if for_list is not None else owner

    normalized = normalize_task_text(text)
    if _duplicate_exists(for_list, normalized, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    if recurrence and recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    try:
        item = Item.objects.create(
            list=for_list,
            owner=owner,
            text=normalized,
            due_date=due_date,
            position=_next_position(for_list, owner=owner),
            recurrence=recurrence or Item.Recurrence.NONE,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    if item.recurrence != Item.Recurrence.NONE:
        _anchor_commitment(item)
        item.save(update_fields=["commitment"])
    if tags:
        item.tags.set(resolve_tags(owner, tags))
    return item


@transaction.atomic
def edit_item(item, text):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")

    normalized = normalize_task_text(text)
    if _duplicate_exists(item.list, normalized, excluding=item):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)

    item.text = normalized
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    _write_through_to_commitment(item, text=normalized)
    return item


@transaction.atomic
def reorder_items(for_list, ordered_ids):
    # Set equality against the list's open tasks is what stops an id
    # belonging to another list from being smuggled in.
    items = list(
        Item.objects.select_for_update()
        .filter(list=for_list)
        .exclude(status=Item.Status.ARCHIVED)
    )
    by_id = {item.id: item for item in items}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This list changed since you last loaded it. Refresh and try again."
        )
    for position, item_id in enumerate(ordered_ids):
        item = by_id[item_id]
        if item.position != position:
            item.position = position
            item.save(update_fields=["position"])
    return [by_id[item_id] for item_id in ordered_ids]


@transaction.atomic
def set_item_tags(item, tag_names):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    resolved = resolve_tags(item.owner, tag_names)
    item.tags.set(resolved)
    _write_through_to_commitment(item, tags=resolved)
    return item


@transaction.atomic
def set_due_date(item, due_date):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.due_date = due_date or None
    item.save()
    return item


@transaction.atomic
def set_priority(item, priority):
    """Mark a commitment as more or less pressing than the rest.

    Writes through to the series for the same reason renaming does -- "this and
    future". A priority set on "pay rent" that came back unmarked next month
    would be the one attribute of a commitment that did not carry.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if priority not in Priority.values:
        raise TaskConflict("Choose a valid priority.")
    item.priority = priority
    item.save(update_fields=["priority"])
    _write_through_to_commitment(item, priority=priority)
    return item


@transaction.atomic
def set_lead_days(item, days):
    """How many days before its due date this should be mentioned.

    Written through to the series, like priority: a lead time on "pay rent"
    that came back zero next month would be the one attribute somebody had to
    set again forever.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if days < 0:
        raise TaskConflict("A lead time cannot be negative.")
    item.lead_days = days
    item.save(update_fields=["lead_days"])
    _write_through_to_commitment(item, lead_days=days)
    return item


@transaction.atomic
def set_bill(item, *, amount=None, currency="USD", payee=""):
    """Mark a task as a bill, or edit the one it already is.

    Upserts rather than accumulating: a task is one bill or none, which is what
    the one-to-one says and what "marking it twice" has to mean.

    Deliberately **not** written through to the commitment, unlike text, notes
    and the Area. What a bill comes to is a fact about *this* occurrence -- last
    quarter's was 500 and this one is 525 -- so carrying it forward would state
    an amount nobody has been told yet. The payee travels with the series only
    in the sense that the next occurrence is created from the same commitment
    and somebody fills it in again; inventing the number would be worse.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if amount is not None and amount < 0:
        raise TaskConflict("A bill is something owed, so it cannot be negative.")
    MoneyLine.objects.update_or_create(
        item=item,
        defaults={"amount": amount, "currency": currency, "payee": payee},
    )
    return item


@transaction.atomic
def create_bill(
    owner,
    *,
    payee,
    amount=None,
    currency="USD",
    due_date=None,
    repeats=True,
    recurrence=None,
    lead_days=0,
    direction=Direction.OUT,
):
    """A bill, made where bills are, without anybody saying "task".

    **The task and the sidecar in one transaction**, so the page named after
    the concept can produce one. Until August 27, 2026 the only route was to
    create a task elsewhere, open its detail page and fill in amount and payee
    -- `money-module-plan.md` has what that cost.

    **The name comes from the payee** and is not asked for: `Landlord` becomes
    *Pay Landlord*. Vince's call, and the point is that adding a bill should
    ask about money and dates and nothing else. Renaming afterwards works
    wherever tasks are renamed; what is removed is the obligation to name one
    up front.

    **No Area.** `create_item` gained a standing `owner` exactly so a task
    could exist without being filed, and *which Area does rent go in* is the
    filing question this surface exists to avoid.

    **Repeating by default**, because the canonical bill is rent and the
    vision document's canonical recurring task is "pay rent every month".
    `recurrence` names which cadence when it is not monthly; `repeats=False`
    is the one-off, and is the same thing as `recurrence=NONE`.

    **`lead_days` is how many days early it should start being mentioned**, and
    it is the reason the money module exists rather than a convenience on top
    of it: an annual subscription that only speaks on the day it renews has
    already charged you. Zero is off. The field lives on the task, which its own
    comment settled -- *a lead time is not a property of costing money* -- and
    `_spawn_next_occurrence` carries it, so it is set once rather than every
    renewal.
    """
    payee = (payee or "").strip()
    if not payee:
        # The name is derived from it, so an empty payee is not a blank field
        # to tolerate -- it is a task with no name.
        raise TaskConflict("A bill needs a payee, which is what it gets its name from.")
    if recurrence is None:
        recurrence = Item.Recurrence.MONTHLY if repeats else Item.Recurrence.NONE
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid cadence.")
    incoming = direction == Direction.IN
    try:
        item = create_item(
            None,
            f"{'From' if incoming else 'Pay'} {payee}",
            due_date=due_date,
            recurrence=recurrence,
            owner=owner,
        )
    except TaskConflict:
        # **Two lines from one payee collide**, because the name is derived from
        # the payee and `unique_active_arealess_item` is `(owner, text)` over
        # everything unfiled and not archived. Two Amazon subscriptions, or a
        # salary and a bonus from the same employer, are the real cases.
        #
        # **Accepted rather than designed around.** The alternative is putting
        # an amount or a number into every name to serve the rarer case, which
        # makes *Pay Landlord* worse for the common one. What is not acceptable
        # is `create_item`'s own message -- "You've already got this in your
        # list" is about a list, and there is no list here.
        kind = "income" if incoming else "bill"
        # **A way forward, not just a refusal.** Vince, August 27, 2026:
        # suggest renaming the second one with a notation of what it is. The
        # payee *is* the name, so adding the distinguishing word to it solves
        # the collision and makes the row more readable than it would have been
        # anyway -- "Amazon (Prime)" and "Amazon (Music)" tell you which is
        # which on a page where "Amazon" twice would not.
        raise TaskConflict(
            f"There is already an open {kind} from {payee}. "
            f"Add a word to tell them apart -- “{payee} (Prime)”, "
            f"say -- or edit the existing one."
        ) from None
    set_bill(item, amount=amount, currency=currency, payee=payee)
    if direction != Direction.OUT:
        MoneyLine.objects.filter(item=item).update(direction=direction)
    if lead_days:
        set_lead_days(item, lead_days)
    item.refresh_from_db()
    return item


_KEEP = object()


@transaction.atomic
def update_bill(item, *, payee=_KEEP, amount=_KEEP, currency=_KEEP, due_date=_KEEP,
                lead_days=_KEEP, recurrence=_KEEP, category=_KEEP,
                clear_amount=False):
    """Correct a bill where it is shown, across both records it lives in.

    **The four fields a bill actually has do not live in one place**: amount,
    payee and currency are the sidecar's, and the due date is the task's. One
    service rather than two calls from the page, so a caller cannot leave a bill
    half-corrected when the second write fails -- and so the page does not have
    to know which field is which, which is the whole point of
    `money-module-plan.md`.

    **Absent is not empty.** A field left out keeps its stored value, the same
    partial-write contract the day and the review already have. Clearing an
    amount back to unpriced is therefore an explicit act: `clear_amount=True`,
    because *"the water bill, whatever it comes to"* is a state somebody chooses
    rather than a field they forgot.

    **It does not rename the task**, and that is a decision rather than an
    omission. The name came from the payee when the bill was made; changing the
    payee later is usually a correction to who gets paid, and
    `RecurringCommitment.text` is what a series with history is called.
    Renaming stays where tasks are renamed.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    bill = MoneyLine.objects.filter(item=item).first()
    if bill is None:
        raise TaskConflict("That task is not a bill.")

    if payee is not _KEEP:
        payee = (payee or "").strip()
        if not payee:
            raise TaskConflict("A bill needs a payee.")
        bill.payee = payee
    if currency is not _KEEP:
        bill.currency = currency
    if category is not _KEEP:
        # None is a real value here -- it files the bill back under
        # Uncategorised, which somebody may well want.
        bill.category = category
    if clear_amount:
        bill.amount = None
    elif amount is not _KEEP:
        if amount is not None and amount < 0:
            raise TaskConflict("A bill is something owed, so it cannot be negative.")
        bill.amount = amount
    bill.save(update_fields=["payee", "currency", "amount", "category"])

    if due_date is not _KEEP:
        # Through the service, so the life log hears it the way every other
        # due-date change is heard rather than a second, quieter path.
        set_due_date(item, due_date)
        item.refresh_from_db()
    if lead_days is not _KEEP:
        # Thirty days turns out to be too late once, and then you want sixty.
        set_lead_days(item, lead_days)
        item.refresh_from_db()
    if recurrence is not _KEEP:
        set_recurrence(item, recurrence)
        item.refresh_from_db()
    return item


#: What a fresh module starts with. Ordinary rows once written, so any of them
#: can be renamed or deleted -- these are a starting point, not a schema.
#:
#: Chosen to cover the bills a person actually has rather than to be complete:
#: an accountant's chart would be exhaustive and useless at eight entries.
SEED_CATEGORIES = (
    "Housing",
    "Utilities",
    "Subscriptions",
    "Insurance",
    "Debt",
    "Transport",
    "Health",
)


def categories_for(owner):
    """This owner's categories, seeded on first ask.

    **Seeding here rather than at signup** so that accounts predating the
    feature get their list the first time they look, and nothing has to
    backfill. `get_or_create` per name makes a second call a no-op rather than
    a duplicate — and a person who has deleted *Transport* does not find it
    back next time, because the seeding only runs when they have none at all.
    """
    existing = MoneyCategory.objects.filter(owner=owner)
    if not existing.exists():
        MoneyCategory.objects.bulk_create(
            [
                MoneyCategory(owner=owner, name=name, position=index)
                for index, name in enumerate(SEED_CATEGORIES)
            ]
        )
    return MoneyCategory.objects.filter(owner=owner)


@transaction.atomic
def add_category(owner, *, name):
    """One more, at the end of the list."""
    name = (name or "").strip()
    if not name:
        raise TaskConflict("A category needs a name.")
    last = (
        MoneyCategory.objects.filter(owner=owner)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    try:
        return MoneyCategory.objects.create(
            owner=owner, name=name, position=(last or 0) + 1
        )
    except IntegrityError as error:
        raise TaskConflict(f"There is already a category called {name}.") from error


@transaction.atomic
def rename_category(category, name):
    name = (name or "").strip()
    if not name:
        raise TaskConflict("A category needs a name.")
    category.name = name
    try:
        category.save(update_fields=["name"])
    except IntegrityError as error:
        raise TaskConflict(f"There is already a category called {name}.") from error
    return category


@transaction.atomic
def delete_category(category):
    """Remove a label. **The bills it labelled are untouched** -- the reference
    is `SET_NULL`, so they become uncategorised rather than disappearing with
    it. A category is a label and not a container."""
    category.delete()


@transaction.atomic
def create_account(owner, *, name, kind=None, currency="USD", owes=None):
    """Open something that carries a balance.

    **`owes` defaults from the kind**, because a card and a loan are money you
    owe and an investment or savings pot is money you have -- and making a
    person answer that for every account would be asking them to restate what
    they already said by choosing the kind.
    """
    name = (name or "").strip()
    if not name:
        raise TaskConflict("An account needs a name.")
    kind = kind or AccountKind.CARD
    if kind not in AccountKind.values:
        raise TaskConflict("Choose a valid kind of account.")
    if owes is None:
        owes = kind in (AccountKind.CARD, AccountKind.LOAN)
    try:
        return Account.objects.create(
            owner=owner,
            name=name,
            kind=kind,
            currency=currency,
            owes=owes,
        )
    except IntegrityError as error:
        raise TaskConflict(
            f"There is already an account called {name}."
        ) from error


@transaction.atomic
def record_balance(account, *, on_date, amount):
    """What this account came to, in the month ``on_date`` falls in.

    **Snapped to the first of the month**, because a balance is *what it came to
    in August* rather than what it read at 14:32 on the 31st -- and two readings
    a day apart would otherwise look like two months.

    **Saving a month twice corrects it.** The ritual is a monthly pass; somebody
    who mistypes and saves again means *that figure was wrong*, not *here is a
    second August*. `update_or_create` under the unique constraint, so two
    browser tabs cannot produce two rows either.
    """
    if amount is None:
        raise TaskConflict("A balance needs a figure.")
    if amount < 0:
        # Direction is `Account.owes`, not the sign of the number: a card at
        # 4,200 and an ISA at 4,200 are both four thousand two hundred.
        raise TaskConflict(
            "Enter the balance as a positive figure -- whether it is owed or "
            "held is the account's own setting."
        )
    reading, _ = BalanceReading.objects.update_or_create(
        account=account,
        on_date=on_date.replace(day=1),
        defaults={"amount": amount},
    )
    return reading


@transaction.atomic
# DARK: no production caller. Nothing on the balances screen closes an account,
# so a card somebody stops using stays in the monthly pass forever, asking for a
# figure that no longer exists. Trigger: a control for removing an account,
# which the balances screen is the obvious home for and was not part of what
# Vince asked for. Declared rather than deleted because the gap is real and
# one-sided -- accounts can be created and not removed, which is a worse end
# state than an uncalled function.
# Two things about where and how this is written, both learned by getting them
# wrong. It sits *below* the decorator because the guard reads the comment lines
# immediately preceding `def`, and a declaration above `@transaction.atomic` is
# invisible to it -- the same decorator-and-def adjacency CLAUDE.md records
# costing a lost `@transaction.atomic` once already. And it has no blank comment
# lines, because a bare `#` does not match `^# .*` and silently ends the block,
# so only the paragraph after it is read.
def close_account(account):
    """Remove an account and the readings that belong to it.

    Hard delete, per §4 rule 6: unlike a week somebody reviewed, an account's
    existence answers nothing about whether a practice happened, so there is
    nothing here that keeping the row would preserve.
    """
    account.delete()


@transaction.atomic
def create_income(owner, *, payer, amount=None, currency="USD", due_date=None,
                  repeats=True, recurrence=None, lead_days=0):
    """Money expected in, on a date, usually every month.

    **The same record as a bill, pointed the other way.** §4's test is a
    different life cycle, and income has a bill's exactly: it recurs, it has a
    date, it has an amount, it gets settled, it can be late. What differs is the
    sign and whether you act or observe -- neither of which is a life cycle.

    **The name comes from the payer**, so this asks no more for a task title
    than the bill form does: `Acme Ltd` becomes *From Acme Ltd*, against a
    bill's *Pay Landlord*.

    **It will not appear on the day or the agenda.** `agenda.open_items_for`
    excludes money coming in, because being paid is not something you do and a
    line you cannot act on is clutter on the surface you use most.
    """
    return create_bill(
        owner,
        payee=payer,
        amount=amount,
        currency=currency,
        due_date=due_date,
        repeats=repeats,
        recurrence=recurrence,
        lead_days=lead_days,
        direction=Direction.IN,
    )


@transaction.atomic
def pay_bill(item, *, amount=None, today=None):
    """Settle a money line, recording what actually moved.

    **Both directions, under the name the commoner one uses.** A `receive_income`
    alias stood beside this for an hour on August 27, 2026 and was deleted: it
    delegated here and added a word, the endpoint already settles either
    direction, and the page already says *Mark received* where it should. A
    wrapper whose only content is a synonym is a service nothing calls, which
    this project has a test for -- and that test is what found it.

    **Paying is completing**, and there is no second definition of done: this
    calls `complete_item`, so the day, the agenda and the review all hear it,
    and a repeating bill spawns its successor exactly as it would have. What
    this adds is the number.

    **`amount` defaults to what was expected**, so the ordinary case is one
    click and the number is still recorded rather than inferred later. Passing a
    different one is the case that decided the design: paying extra must not
    overwrite what the bill was *supposed* to be, or the month loses the
    difference and "this has been creeping up" stops being answerable.

    An unpriced bill can be paid with a real number, which is the moment
    *"whatever it comes to"* comes to something.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    bill = MoneyLine.objects.filter(item=item).first()
    if bill is None:
        raise TaskConflict("That task is not a bill.")
    if amount is not None and amount < 0:
        raise TaskConflict("A payment cannot be negative.")

    bill.paid_amount = bill.amount if amount is None else amount
    bill.save(update_fields=["paid_amount"])
    # After the amount, so a failure here leaves an unpaid bill with a stray
    # number rather than a paid one with none -- the recoverable direction.
    #
    # `today` is passed through rather than defaulted here: a bill's successor
    # date is the one thing about paying that depends on which day it is, and
    # every caller in production leaves it None for the real clock.
    complete_item(item, today=today)
    return item


@transaction.atomic
def delete_bill(item, *, whole_series=False):
    """Remove a bill, and say which bill is meant when it repeats.

    **From the person's side there is no task**, so this removes the whole
    thing rather than stripping the sidecar and leaving an orphan called
    "Pay Landlord" in their lists. Vince's decision, August 27, 2026.

    **`whole_series=False` means this month and not the habit.** A series
    continues only because completing an occurrence spawns the next one -- so
    deleting this one would end the series *silently*, with no next month and
    nothing to notice until a bill failed to arrive. The successor is therefore
    created before this occupant is removed. What somebody means by deleting
    August's rent is *not this one*; they would have said so if they meant stop
    paying rent.

    **`whole_series=True` stops it coming round** and leaves every month that
    already happened alone: the commitment ends, this occurrence goes, and past
    ones stay because §4 rule 6 keeps a row whose existence answers whether
    something happened.

    **Archive then delete**, because `delete_archived_item` refuses anything
    else and that rule is worth going through rather than around -- it is what
    makes the life log hear a removal the same way everywhere.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if not MoneyLine.objects.filter(item=item).exists():
        raise TaskConflict("That task is not a bill.")

    repeats = item.recurrence != Item.Recurrence.NONE
    if repeats and whole_series:
        # Ends the commitment; the link from this row stays, because it really
        # was an occurrence of that series.
        set_recurrence(item, Item.Recurrence.NONE)
        item.refresh_from_db()
        repeats = False

    # **Archive first, then spawn.** `unique_active_arealess_item` is
    # `(owner, text)` over everything not archived, so an unfiled successor
    # cannot exist beside a live predecessor -- which is exactly why
    # `complete_item` archives a recurring task rather than leaving it
    # `COMPLETED`. Ordering it the other way round raises an IntegrityError,
    # and did.
    archive_item(item)
    item.refresh_from_db()
    if repeats:
        _spawn_next_occurrence(item)
    delete_archived_item(item)


@transaction.atomic
def clear_bill(item):
    """Stop this task being a bill. The task itself is untouched."""
    MoneyLine.objects.filter(item=item).delete()
    return item


@transaction.atomic
def move_item(item, to_list):
    """File a task into a different Area, or out of every Area.

    `commercial-blueprint.md` Part 3 named the absence: `item_detail` PATCH
    took six fields and `list` was not one, so a misfiled task stayed
    misfiled.

    **Moving between Areas moves between Projects as a consequence, not as a
    second decision.** A `Project` hangs off `List`, so a task's project is
    whatever its area's is -- there is nothing here to keep consistent.

    **`position` is recomputed rather than carried.** It orders a task *within*
    its Area, so the number it held in the old one means nothing in the new
    one; appending is the only answer that does not interleave it silently
    into an order somebody arranged.

    **`to_list=None` is a destination, not a missing argument.** `Item.list`
    has been nullable since August 14 and `Item.owner` is what keeps an
    unfiled task a real one -- and `_derive_owner` only fires when there *is*
    an area, so unfiling leaves the owner where it was rather than stranding
    the row.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.list = to_list
    item.position = _next_position(to_list, owner=item.owner)
    item.save()
    # **Write through, or a series quietly stays where it was.** Spawning
    # reads `commitment.list`, not the occurrence's -- see `list=commitment.list`
    # in the spawn below -- so moving only the task would file this occurrence
    # in the new Area and its successor back in the old one. Same "this and
    # future" rule renaming already follows.
    _write_through_to_commitment(item, list=to_list)
    return item


@transaction.atomic
def set_recurrence(item, recurrence, cadence_mode=None):
    """Set how often this repeats, and optionally whether it is anchored.

    `cadence_mode=None` means "leave it as it is", not "reset to the default".
    Editing a cadence must not silently undo a mode somebody chose -- that is
    how a setting gets quietly reverted by an unrelated edit.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    if cadence_mode is not None and cadence_mode not in CadenceMode.values:
        raise TaskConflict("Choose a valid schedule mode.")
    # Read before the write, so the log can tell a change from a re-save.
    # **Only the cadence.** `cadence_mode` is deliberately not a life event in
    # slice 1: it decides where the *next* occurrence lands rather than whether
    # there is a series at all, and under-recording is recoverable where a
    # keystroke log is not.
    cadence_changed = item.recurrence != recurrence
    item.recurrence = recurrence
    if recurrence == Item.Recurrence.NONE:
        # The link stays. This task really was an occurrence of that series,
        # and clearing the key would rewrite history to say it never was --
        # only the series stops accepting new ones.
        _end_commitment(item)
    else:
        _anchor_commitment(item)
    item.save()
    # The cadence is the commitment's rule; `item.recurrence` above is this
    # occurrence's snapshot of it. Writing both keeps an *active* occurrence
    # in step with its series, which is why the API can keep reading the
    # item's own value -- see the plan file, slice 3.
    #
    # Deliberately also written when the cadence is NONE: a commitment that
    # was stopped should say so rather than keep advertising the rule it no
    # longer follows.
    _write_through_to_commitment(item, cadence=recurrence)
    if cadence_mode is not None:
        _write_through_to_commitment(item, cadence_mode=cadence_mode)
    if cadence_changed:
        life_log.record(
            item.owner,
            life_log.COMMITMENT_ENDED
            if recurrence == Item.Recurrence.NONE
            else life_log.COMMITMENT_CHANGED,
            task=item,
        )
    return item


@transaction.atomic
def set_item_notes(item, notes):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    # Normalised to "" rather than None so callers never have to handle both;
    # clearing notes and never having written any are the same state.
    item.notes = (notes or "").strip()
    item.save()
    _write_through_to_commitment(item, notes=item.notes)
    return item


def _next_step_position(task):
    highest = task.checklist_steps.aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _duplicate_step_exists(task, text, excluding=None):
    # Mirrors unique_open_checklist_step_text: open-scoped, not task-wide, so
    # a done step's text is free to reuse -- see design/release-d-plan.md 2.
    duplicates = task.checklist_steps.filter(is_done=False, text=text)
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def add_checklist_step(task, text, carries_forward=None):
    task = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=task.pk)
    if task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(task, normalized):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        step = ChecklistStep.objects.create(
            owner=task.owner,
            task=task,
            text=normalized,
            position=_next_step_position(task),
            carries_forward=True if carries_forward is None else carries_forward,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def set_checklist_step_done(step, is_done):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.is_done = bool(is_done)
    step.completed_at = timezone.now() if step.is_done else None
    step.save()
    return step


@transaction.atomic
def set_checklist_step_carries_forward(step, value):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.carries_forward = bool(value)
    step.save()
    return step


@transaction.atomic
def edit_checklist_step_text(step, text):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(step.task, normalized, excluding=step):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    step.text = normalized
    try:
        step.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def delete_checklist_step(step):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.delete()


@transaction.atomic
def reorder_checklist_steps(task, ordered_ids):
    steps = list(ChecklistStep.objects.select_for_update().filter(task=task))
    by_id = {step.id: step for step in steps}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This checklist changed since you last loaded it. Refresh and try again."
        )
    for position, step_id in enumerate(ordered_ids):
        step = by_id[step_id]
        if step.position != position:
            step.position = position
            step.save(update_fields=["position"])
    return [by_id[step_id] for step_id in ordered_ids]


@transaction.atomic
def promote_checklist_step(step):
    """Turn a Checklist Step into its own Task -- design/release-d-plan.md 2.

    A state transition, not a copy: the step ceases to exist, so there is
    exactly one live record of the work either way. No due date, no tags, no
    recurrence -- the owner does whatever they were going to do with a new
    task next. Demotion (the reverse) is deliberately not built; see that
    document for why.
    """
    step = (
        ChecklistStep.objects.select_for_update(of=("self",))
        .select_related("task", "task__list")
        .get(pk=step.pk)
    )
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    task_list = step.task.list
    # From the task, not from its Area, which may not exist -- the same
    # correction as in _spawn_next_occurrence, and the same mistake: relying on
    # save() to derive an owner works for every filed task and leaves an
    # unfiled one violating NOT NULL. Passing it here also restores the
    # duplicate check, which followed the Area and so did nothing without one.
    owner = step.task.owner
    if _duplicate_exists(task_list, step.text, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        promoted = Item.objects.create(
            list=task_list,
            owner=owner,
            text=step.text,
            position=_next_position(task_list, owner=owner),
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    step.delete()
    return promoted


def _nth_occurrence_after(base, recurrence, n):
    """The nth scheduled date after `base`, counting in calendar units.

    Computed from the anchor each time rather than by stepping one interval
    off the last result, which matters for monthly: the 31st advanced through
    February and then carried forward would spend the rest of the year on the
    28th. Here February is the only month that clamps, and March is the 31st
    again.
    """
    if recurrence == Item.Recurrence.DAILY:
        return base + timedelta(days=n)
    if recurrence == Item.Recurrence.WEEKLY:
        return base + timedelta(weeks=n)
    if recurrence == Item.Recurrence.FORTNIGHTLY:
        return base + timedelta(weeks=2 * n)
    # Quarterly and annual are monthly with a multiplier, deliberately: the
    # anchor arithmetic below is the part that is easy to get wrong, and three
    # copies of it would be three chances to.
    months = {
        Item.Recurrence.MONTHLY: 1,
        Item.Recurrence.QUARTERLY: 3,
        Item.Recurrence.ANNUAL: 12,
    }.get(recurrence)
    if months is not None:
        n = n * months
        month_index = base.month - 1 + n
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        return base.replace(
            year=year, month=month, day=min(base.day, monthrange(year, month)[1])
        )
    return None


def _advance_due_date(due_date, recurrence, today=None, mode=CadenceMode.ANCHORED):
    """The next occurrence's due date, which is always strictly after today.

    **Strictly after, and the strictness is the decision** -- corrected here on
    August 28, 2026. This line read *"never already in the past"* for a month,
    which is a weaker claim than the code makes: today is not the past, so that
    wording promised an occurrence falling exactly on today would be kept, and
    `candidate > today` drops it. The code was right and the sentence was
    wrong.

    **Why dropping it is right: the completion is happening today.** Bins every
    Monday, last done June 1, done again today -- today's slot has just been
    satisfied by the act that triggered this call, so returning it would hand
    somebody a task due the day they did it. `>=` was measured rather than
    argued about: it breaks
    `test_a_very_late_weekly_commitment_skips_every_missed_week`, which spawns
    August 10 instead of August 17 on a Monday-anchored series. That test pins
    this boundary on purpose, and
    `test_a_series_never_spawns_overdue.test_the_slot_the_completion_lands_on_is_not_respawned`
    now says so by name rather than by coincidence.

    **What this does not decide** is whether *money* should skip a missed
    period at all -- a bill you did not pay is still owed in a way a bin round
    you missed is not. That is a product question about the doctrine below
    rather than about this comparison, and `roadmap.md` carries it.

    It used to be one interval past the *previous due date*, full stop. A
    monthly commitment due July 4 and completed August 10 therefore produced a
    successor due August 4 -- overdue at the instant it was created, on a task
    the person had just finished. `roadmap.md` carried this as "one defect to
    fix on the way in rather than port"; the way in happened and it was not.

    **Missed periods are skipped, not replayed.** The schedule keeps its anchor
    and moves forward until it clears today, so a filter changed on the 4th is
    still on the 4th afterwards, and five missed weeks produce one task rather
    than five. Occurrences that did not happen are not invented -- a fabricated
    history is worse than an absent one, and `principles.md` refuses it.

    All of that describes **anchored**, which is the default and was the only
    mode until August 15, 2026. **Floating** counts from the completion instead
    -- a furnace filter lasts a month from when it was changed, not from a date
    nobody acted on -- and needs no skipping, because it starts from today by
    construction.

    See `CadenceMode` for why anchored is the default rather than a coin toss.
    """
    if today is None:
        today = timezone.localdate()
    if mode == CadenceMode.FLOATING:
        # The old due date is deliberately ignored, including a future one:
        # floating means the clock restarts when the work is actually done.
        return _nth_occurrence_after(today, recurrence, 1)

    base = due_date or today

    # Bounded rather than `while True`: a corrupt cadence or a due date far in
    # the past should not spin. Two thousand steps clears five years of daily.
    for n in range(1, 2001):
        candidate = _nth_occurrence_after(base, recurrence, n)
        if candidate is None:
            return None
        if candidate > today:
            return candidate
    return None


def _spawn_next_occurrence(completed_item, carry_forward_steps=(), today=None):
    # Anchored here as well as on the paths that set a cadence, because rows
    # predating this key reach completion without one. Their earlier
    # occurrences can't be recovered -- that history is gone -- but adopting
    # the pair here means no path leaves the series unlinked from now on.
    was_linked = completed_item.commitment_id is not None
    commitment = _anchor_commitment(completed_item)
    if not was_linked:
        completed_item.save(update_fields=["commitment"])
    # Built from the template, not copied from the occurrence that just
    # finished. That is the whole point of the pair: the commitment says what
    # the next one starts as, and the completed row keeps what *it* was, so
    # renaming a commitment in September leaves June reading "Pay rent".
    #
    # `due_date` is the exception and always was -- computed per occurrence by
    # _advance_due_date rather than seeded, because it advances from the one
    # that just finished rather than being a property of the series.
    #
    # The template is the sole source now. It carried `or` fallbacks to the
    # completed occurrence through one deploy, as the compatibility window
    # for 0031's backfill; that window closed on August 3, 2026 when the
    # migration reported empty=0 against production -- every commitment has a
    # template, so there is nothing left for a fallback to cover.
    #
    # The cadence is not merely a label: it decides how far the next due date
    # moves, so reading the wrong one schedules the next occurrence on the
    # wrong day rather than just describing it wrongly.
    next_item = Item.objects.create(
        list=commitment.list,
        # From the series, not from the Area. `Item.save()` derives owner from
        # `list`, which works for every filed task and leaves an unfiled one
        # with nothing to derive from -- so this insert violated NOT NULL and
        # completing the task raised. The commitment is the durable identity
        # here and it knows whose it is, whether or not it has a place.
        owner=commitment.owner,
        text=commitment.text,
        # `today` rather than `timezone.localdate()` inline, so a caller can
        # say which day it is. Passing None means the real clock, which is
        # every production path -- `_advance_due_date` does the defaulting, so
        # there is still exactly one place that reads the system date.
        #
        # It was inline until August 28, 2026, and that made the boundary
        # untestable without mocking: a fortnightly item due the 14th whose
        # successor falls on the 28th produced a *different* successor once the
        # real date reached the 28th, because the schedule must clear today.
        # `test_the_next_one_lands_two_weeks_later` hard-coded the 28th and so
        # passed for fourteen days and then failed for good -- red on `main`,
        # not a flake. See `principles.md`, *inject the clock; do not freeze
        # it*: the sibling test two functions down had been doing this all
        # along, via `landing_for(..., today=AUGUST)`.
        due_date=_advance_due_date(
            completed_item.due_date,
            commitment.cadence,
            today=today,
            mode=commitment.cadence_mode,
        ),
        recurrence=commitment.cadence,
        position=_next_position(commitment.list, owner=commitment.owner),
        commitment=commitment,
        notes=commitment.notes,
        priority=commitment.priority,
        lead_days=commitment.lead_days,
    )
    next_item.tags.set(commitment.tags.all())

    # **A repeating bill stays a bill.** Added August 27, 2026: nothing here
    # touched `MoneyLine`, so paying rent produced a plain task for next month and
    # rent silently stopped appearing on the page that exists to show bills.
    # Recurrence was built for tasks and the sidecar was added beside it;
    # neither was wrong and nobody joined them.
    #
    # **The payee and the currency carry. The amount does not**, which is
    # `set_bill`'s own rule and the right one: what a bill comes to is a fact
    # about *this* occurrence -- last quarter's was 500 and this one is 525 --
    # so carrying the number forward would state something nobody has been
    # told. What lands is an unpriced bill from a known payee, which is
    # exactly what `MonthOfBills.unpriced` counts rather than totals.
    previous_bill = MoneyLine.objects.filter(item=completed_item).first()
    if previous_bill is not None:
        MoneyLine.objects.create(
            item=next_item,
            amount=None,
            currency=previous_bill.currency,
            payee=previous_bill.payee,
        )

    # **NOT CARRIED: Facet.** A facet records that a particular thought became
    # a particular task -- `mind.Facet.task`, whose invariant is that a
    # confirmed actionable facet has a live task. It is provenance about *one*
    # occurrence. Copying it would claim the same thought also became next
    # month's task, and the month after that, which is false and gets less true
    # every cycle. The original keeps its facet; completing a task does not
    # delete it, so nothing is orphaned.
    #
    # **NOT CARRIED: ActivityEvent.** The life log of what happened to *this*
    # occurrence. Copying rows forward would fabricate history -- events dated
    # before the task existed -- and the table is append-only by database
    # trigger, so it is not a thing to write casually in either direction.
    #
    # Both declared rather than left silent, and
    # `tests/test_a_spawn_accounts_for_everything_on_a_task.py` is why: `MoneyLine`
    # was correctly not mentioned here either, right up until it turned out to
    # be a defect that had been live since bills shipped.

    # Fresh copies, not carried state: a step that was already ticked off
    # this cycle starts the next one unchecked, the same way the parent
    # itself starts active rather than completed.
    for step in carry_forward_steps:
        ChecklistStep.objects.create(
            owner=step.owner,
            task=next_item,
            text=step.text,
            position=step.position,
            carries_forward=step.carries_forward,
        )
    return next_item


def _checklist_steps_to_carry_forward(item):
    """Every checklist step flagged carries_forward -- what clones onto the
    next occurrence. A step has no independent archived state to exclude: it
    dies with its task (release-d-plan.md 2) rather than being separately
    removed, so there's nothing else to filter here.
    """
    return list(
        item.checklist_steps.filter(carries_forward=True).order_by("position", "id")
    )


@transaction.atomic
# `of=("self",)` on every lock that also selects the Area.
#
# Item.list became nullable on August 14, 2026, which turned select_related("list")
# from an inner join into an outer one -- and Postgres refuses "FOR UPDATE cannot
# be applied to the nullable side of an outer join". Locking only the base row is
# what was meant anyway: nothing here mutates the Area, and locking it would take
# a lock on every task in it.
#
# Found by the suite rather than by reading: 95 errors from one column changing
# nullability, none of them in code that mentions the column.


# `transaction.atomic` here rather than nowhere, which is what it was.
# `temporal-substrate-plan.md` increment 2 records a completion to the
# append-only log, and Vince's answer to how that may fail is **both or
# neither** -- so the completion and its event have to be one transaction or
# the log becomes a sample with a silent hole in it. This function already did
# two saves and a spawn in autocommit, each committing alone; the log is what
# made that worth fixing rather than merely noting.
@transaction.atomic
def complete_item(item, *, today=None):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.COMPLETED:
        now = timezone.now()
        is_recurring = item.recurrence != Item.Recurrence.NONE
        # Read before the item moves: a recurring task archives itself below,
        # and reading this after would see its own steps as belonging to an
        # already-archived task rather than change what they answer.
        carry_forward_steps = (
            _checklist_steps_to_carry_forward(item) if is_recurring else []
        )
        item.status = Item.Status.COMPLETED
        item.completed_at = now
        item.archived_at = None
        if is_recurring:
            # Recurring tasks skip the "completed" resting state: archive
            # immediately (freeing up its text for the next occurrence,
            # which would otherwise collide with the unique-active-text
            # constraint) and spawn the next one right away.
            item.status = Item.Status.ARCHIVED
            item.archived_at = now
        item.save()
        if is_recurring:
            item._spawned = _spawn_next_occurrence(
                item, carry_forward_steps=carry_forward_steps, today=today,
            )
        # The completion, and not the archive above it. A recurring task is
        # archived immediately to free its text for the next occurrence --
        # mechanism, not a decision -- and logging that would put a retirement
        # in the record of a habit somebody is keeping.
        #
        # `now` rather than a fresh clock read: the log has to agree with
        # `completed_at`, or a reading joining the two sees one task finished
        # twice a millisecond apart.
        life_log.record(
            item.owner, life_log.TASK_COMPLETED, task=item, occurred_at=now
        )
    return item


@transaction.atomic
def reopen_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.ACTIVE:
        item.status = Item.Status.ACTIVE
        item.completed_at = None
        item.archived_at = None
        item.save()
        # Without this the log asserts a completion it can never retract, and
        # any projection folded over it drifts the first time somebody ticks
        # the wrong row.
        life_log.record(item.owner, life_log.TASK_REOPENED, task=item)
    return item


@transaction.atomic
def archive_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        item.status = Item.Status.ARCHIVED
        item.archived_at = timezone.now()
        item.save()
        life_log.record(
            item.owner,
            life_log.TASK_ARCHIVED,
            task=item,
            occurred_at=item.archived_at,
        )
    return item


def _restore_status_for(item):
    # A null completed_at means the task was active when it was archived, so
    # that is where it goes back to; anything else was genuinely completed.
    if item.completed_at is None:
        return Item.Status.ACTIVE
    return Item.Status.COMPLETED


@transaction.atomic
def restore_item(item):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Only archived tasks can be restored")
    if _duplicate_exists(item.list, item.text, excluding=item):
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        )

    item.status = _restore_status_for(item)
    item.archived_at = None
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        ) from error
    return item


@transaction.atomic
def delete_archived_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition(ARCHIVED_DELETE_ERROR)
    item.delete()


@transaction.atomic
def delete_list(list_):
    list_ = List.objects.select_for_update().get(pk=list_.pk)
    list_.delete()


EMPTY_PROJECT_TITLE_ERROR = "Give the project a name"
FOREIGN_PROJECT_ERROR = "That project isn't yours"


@transaction.atomic
def set_desired_outcome(project, text):
    """What done looks like.

    A service rather than a line in the API handler, which is where this field
    has been written since August 20. **Not a refactor for its own sake**: it
    is `abandon_if`'s twin, that one needs a service for `brief_for` to read
    against, and one of a pair living in the API while the other lives here is
    how two fields that must stay distinguishable start drifting apart.
    """
    project.desired_outcome = (text or "").strip()
    project.save(update_fields=["desired_outcome"])
    return project


def set_abandonment_condition(project, text):
    """What would tell him it went wrong -- S10, and D4's answer.

    Separate from `desired_outcome` because **a tripwire you cannot tell from
    an ambition can never be checked**. See `Project.abandon_if`.
    """
    project.abandon_if = (text or "").strip()
    project.save(update_fields=["abandon_if"])
    return project


def set_project_notes(project, text):
    """Working notes on a project. Optional, like everything else here."""
    project.notes = (text or "").strip()
    project.save(update_fields=["notes"])
    return project


def create_project(owner, title, due_date=None, purpose=""):
    """A new, standalone project -- project-workspace-plan.md 2.

    Owner is passed directly rather than derived: a Project has no parent
    record left to borrow it from, the same shape create_list_with_item
    already uses.

    `purpose` is stripped like the title and, unlike it, may end up empty --
    it is optional by design (see the field). Whitespace-only collapses to
    "" so that "the person typed spaces" and "the person wrote nothing"
    are one state rather than two, which is the same reason the field is
    blank rather than null.
    """
    normalized = (title or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_PROJECT_TITLE_ERROR)
    return Project.objects.create(
        owner=owner,
        title=normalized,
        due_date=due_date,
        purpose=(purpose or "").strip(),
    )


def record_what_was_learned(project, text):
    """What he would do differently — **S12's fourth clause**.

    Its own verb rather than a field on the completion call, because the two
    happen at different moments: a project is marked done when the work stops,
    and the lesson arrives while looking at what the retrospective shows. Making
    one write both would mean closing a project demanded a sentence nobody has
    thought of yet, which is the toll `confirm_actionable` refuses to charge for
    filing.

    **Editable and never cleared by anything else.** A learning lost at the next
    state change is worse than none, because he would stop writing them.

    **No `@transaction.atomic`**, matching `set_abandonment_condition` and unlike
    `set_desired_outcome`: one `save()` is already atomic. It briefly had one --
    `complete_project`'s, taken by accident when this was inserted above it --
    and keeping a decorator acquired that way would be making a decision out of
    a slip.
    """
    project.learned = (text or "").strip()
    project.save(update_fields=["learned"])
    return project


@transaction.atomic
def complete_project(project):
    """Mark a project done, without touching a single one of its tasks.

    **The decorator went missing for four hours on August 23, 2026, and it was
    stolen rather than forgotten.** S12 inserted `record_what_was_learned`
    immediately above this function by anchoring a text replacement on
    `def complete_project(project):` -- which put the new function *between this
    decorator and its def*, so `record_what_was_learned` silently acquired it
    and this lost it. `select_for_update()` below needs a transaction, so
    `PATCH /api/v1/projects/{id}` with `is_completed` began returning a 500.

    **Anchoring an insertion on a `def` line is unsafe whenever a decorator can
    sit above it**, and nothing about the edit looked wrong afterwards: both
    functions read correctly in isolation and the diff showed an addition, not a
    move.

    **Every unit test covering it still passed**, because Django's `TestCase`
    wraps each test in a transaction and so supplied exactly the thing the code
    had lost. A test that provides the conditions production code depends on
    cannot discover that it depends on them. CI's browser job caught it within
    the hour; `tests/test_completing_a_project_outside_a_transaction.py` now
    holds it in a second rather than the minute that suite costs.

    Charter rule 5 -- a project references its tasks, it does not own their
    status. Someone finishing a project has said the *grouping* is done; if
    tasks are still open underneath, that is information worth seeing rather
    than something to tidy away silently. principles.md: automations propose,
    people decide.

    Completing an already-completed project keeps the original stamp, so a
    double-click cannot rewrite when the work actually finished.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.is_completed:
        return project
    project.is_completed = True
    project.completed_at = timezone.now()
    # Finishing a paused project is finishing it. Clearing the pause here is
    # what keeps "completed wins" a property of the data rather than a rule
    # every reader has to remember -- no row is ever both.
    project.paused_at = None
    project.save(update_fields=("is_completed", "completed_at", "paused_at"))
    return project


@transaction.atomic
def reopen_project(project):
    """Un-finish it. It comes back open, never paused.

    Reopening says the work is not done; it does not say it was parked. A
    project that should be parked is paused explicitly, which keeps that a
    decision somebody made rather than one this function guessed at.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    project.is_completed = False
    project.completed_at = None
    project.save(update_fields=("is_completed", "completed_at"))
    return project


@transaction.atomic
def pause_project(project):
    """Park it: not finished, and not being worked on either.

    **Idempotent, and the date is why.** How long something has been sitting is
    the only thing this timestamp is for, so a second pause must not re-stamp
    it -- the same call `complete_project` makes above for the same reason.

    Touches no task. A decision about a container is not a decision about the
    work inside it, and a pause that quietly unpinned or re-dated things would
    be a destructive action wearing a soft word.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.paused_at is not None:
        return project
    project.paused_at = timezone.now()
    project.save(update_fields=("paused_at",))
    return project


@transaction.atomic
def resume_project(project):
    """Pick it back up. Clears the pause and nothing else."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    project.paused_at = None
    project.save(update_fields=("paused_at",))
    return project


@transaction.atomic
def add_area_to_project(area, project):
    """Put an Area into a Project, or move it from one Project to another.

    project-workspace-plan.md 2. The guard below is a cross-row check a
    plain ForeignKey can't express on its own -- same "two owned records,
    guard they share an owner" shape as capture.services.link_ideas.
    Checked here rather than only at the API, so the invariant holds
    regardless of caller. principles.md: guards fail closed.
    """
    area = List.objects.select_for_update().get(pk=area.pk)
    if project.owner_id != area.owner_id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    area.project = project
    area.save(update_fields=("project",))
    return area


@transaction.atomic
def remove_area_from_project(area):
    """Take an Area out of its Project. A no-op if it has none."""
    area = List.objects.select_for_update().get(pk=area.pk)
    area.project = None
    area.save(update_fields=("project",))
    return area


def delete_project(project):
    """Hard delete -- charter rule 6, stated in the model too.

    Its areas survive: `List.project` is SET_NULL, so deleting a project
    says the grouping was wrong, not that the work is gone. No tombstone,
    because rule 2 does not apply -- nothing creates or holds a Project
    offline.
    """
    project.delete()
