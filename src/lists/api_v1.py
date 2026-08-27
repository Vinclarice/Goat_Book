"""Ninja router registered onto clarice.api's /api/v1/ contract.

Item mutations (create/complete/reorder/tags/due-date) stay on the
hand-rolled lists.api endpoints -- they already work and are tested, so
a route's migration PR only moves what doesn't already have a JSON
path. Area rename/delete never had one (the Django views redirect on
success, which doesn't suit a fetch-based caller), so those are genuinely
new here rather than moved.

**Vocabulary.** This boundary says Area; the ORM says `List`. Release D
slice 5 moved the words and nothing else, per `architecture-trajectory.md`
§7's refusal to rename the model or the app for a cosmetic reason -- the
same split `Item`/"task" already lives with. Python locals below still read
`our_list`, because renaming them would be churn no client can observe.
See `lists/tests/test_area_vocabulary.py` for the guard.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from typing import Literal

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts import services as account_services
from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_AGENDA_READ
from clarice.clocks import today_for
from lists import agenda as agenda_reader
from lists import money as money_reader
from lists import projects as project_reader
from lists import services
from lists.forms import ListTitleForm
from lists.models import Account, CadenceMode, Item, List
from lists.serializers import (
    archive_workspace_data_for,
    area_ref_for,
    area_workspace_data_for,
    task_detail_data_for,
)

router = Router()

TaskStatus = Literal["active", "completed", "archived"]
TaskRecurrence = Literal[
    "none", "daily", "weekly", "monthly", "quarterly", "annual"
]
#: No "medium": an unmarked task already means ordinary. See lists.models.Priority.
TaskPriority = Literal["none", "high", "low"]
BucketKey = Literal["overdue", "today", "week", "later", "someday"]
AreaColorKey = Literal[
    "sky", "sage", "amber", "lilac", "coral", "azure", "blush", "straw"
]


class ChecklistStepOut(Schema):
    id: int
    text: str
    position: int
    is_done: bool
    completed_at: str | None
    carries_forward: bool
    task_id: int
    url: str
    promote_url: str


class BillOut(Schema):
    """What a task costs, when it is a bill. Null on the task when it is not.

    `amount` is a string, not a float: this column exists to avoid binary
    rounding and sending it as a JSON number would put it straight back.
    """

    amount: str | None
    currency: str
    payee: str


class TaskOut(Schema):
    id: int
    text: str
    status: TaskStatus
    created_at: str
    updated_at: str
    completed_at: str | None
    archived_at: str | None
    due_date: str | None
    position: int
    tags: list[str]
    recurrence: TaskRecurrence
    priority: TaskPriority
    #: Days before the due date this should be mentioned. Zero is off.
    lead_days: int
    #: Null when the task is not a bill -- a different fact from a bill with
    #: nothing filled in, which is reachable on purpose.
    bill: BillOut | None
    notes: str
    # Nullable since August 14, 2026 -- a task may stand on its own, so this is
    # the boundary admitting a state the database already allowed. Ninja
    # validates responses, so leaving it `int` turned every unfiled task into a
    # 500 that no amount of care in the serializer could avoid.
    area_id: int | None
    project_id: int | None
    url: str
    edit_url: str


class AgendaBucketOut(Schema):
    key: BucketKey
    label: str
    collapsed: bool


class AgendaAreaSummaryOut(Schema):
    id: int
    title: str
    url: str
    create_item_url: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class AgendaProjectSummaryOut(Schema):
    id: int
    title: str
    # A project has no page of its own yet, so this is its area's --
    # ui-second-pass-plan.md F2/F3, the second half still open.
    url: str


class AgendaOut(Schema):
    today: str
    username: str
    archive_url: str
    archived_count: int
    new_area_url: str
    settings_url: str
    daily_digest: bool
    buckets: list[AgendaBucketOut]
    items: list[TaskOut]
    completed_today: list[TaskOut]
    areas: list[AgendaAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]


class AreaRefOut(Schema):
    id: int
    title: str
    create_item_url: str
    reorder_url: str


class AreaDetailOut(Schema):
    area: AreaRefOut
    items: list[TaskOut]
    # Singular and optional -- an Area belongs to at most one Project.
    project: AgendaProjectSummaryOut | None
    archived_count: int
    archive_url: str


class AreaRenameIn(Schema):
    title: str


class TaskAreaSummaryOut(Schema):
    id: int
    title: str
    url: str


class ArchiveOut(Schema):
    items: list[TaskOut]
    areas: list[TaskAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]


class TaskDetailOut(Schema):
    task: TaskOut
    # Whether a repeating task is fixed to the calendar or counts from when it
    # was last done -- see lists.models.CadenceMode. Null when it does not
    # repeat, which is the honest answer rather than a default nobody chose.
    cadence_mode: CadenceMode | None
    # Optional since August 14, 2026: a task may stand on its own. Declared
    # nullable here rather than only handled in the serializer, because Ninja
    # validates the response -- a non-optional schema turns an unfiled task
    # into a 500 no matter how carefully the dict was built.
    area: TaskAreaSummaryOut | None
    checklist_steps: list[ChecklistStepOut]
    create_checklist_step_url: str
    reorder_checklist_steps_url: str


class NavAreaOut(Schema):
    id: int
    title: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class NavProjectOut(Schema):
    id: int
    title: str
    open_task_count: int


class NavOut(Schema):
    areas: list[NavAreaOut]
    # ui-second-pass-plan.md F3, Vince's call: a top-level group, flat
    # across areas, the same weight as `areas` rather than nested under it.
    # Completed projects are left out -- this group is ongoing work, the
    # same reason the Agenda excludes completed tasks, and unlike an Area a
    # project actually has a completion state to filter on.
    projects: list[NavProjectOut]
    archived_count: int
    settings_url: str
    # The knowledge core, and since Heron 4b the only place a thought lives.
    # `inbox_count`, `inbox_url` and `ideas_url` sat beside this until the Inbox
    # was deleted; the count was the one number here that measured a backlog,
    # and it went with the thing that had one.
    #
    # Served rather than written into the client. That was originally because
    # the prefix was temporary; step 5 made `/mind/` permanent, and it is still
    # served -- the server owns its own URLs, and a route spelled out in two
    # languages is one that can disagree with itself.
    mind_url: str
    # So the SPA's own index route sends /app/ where the server would send
    # a login, rather than hard-coding a second answer that could drift
    # from lists.views.dashboard's.
    landing_surface: str
    # Null unless this account is leaving. On the nav rather than only on
    # Preferences because the banner it drives has to appear on every route: a
    # scheduled erasure that is only visible on the page you asked to schedule
    # it from is one somebody can forget they started.
    deletion_purge_at: datetime | None


class MonthBillOut(Schema):
    task_id: int
    text: str
    due_date: date
    #: A string, like `BillOut.amount`, and null for a bill nobody has priced.
    amount: str | None
    currency: str
    payee: str
    url: str
    #: Whether it is settled. Derived rather than stored -- there is one
    #: definition of paid and the day and the agenda already read it.
    paid: bool
    #: Whether this comes round again. The page needs it to know whether
    #: deleting has one meaning or two: removing August's rent is not the same
    #: act as stopping rent.
    repeats: bool
    #: Which way the money goes -- "out" for a bill, "in" for income. The page
    #: needs it for the verb: you *pay* a bill and you *receive* income, and a
    #: button saying Pay beside a salary would be nonsense.
    direction: str
    #: Which cadence, so the page can say *every year* rather than *repeats*.
    recurrence: str
    #: Days of warning, and null when there is none.
    lead_days: int
    #: What actually went out, once paid. Null while unpaid -- and different
    #: from `amount` whenever somebody paid something other than the figure
    #: the bill carried.
    paid_amount: str | None
    #: Unpaid and past its due date. Derived here rather than in the browser so
    #: that "late" is decided against the owner's own clock -- `clarice.clocks`
    #: is the rule, and a date computed in a browser is a second opinion.
    overdue: bool


class MonthOfBillsOut(Schema):
    month_start: date
    previous_month: date
    next_month: date
    bills: list[MonthBillOut]
    #: Per currency, keyed by code. **Never one number**: adding 500 USD to 40
    #: GBP produces 540 of nothing. Empty when nothing is due, because
    #: "nothing" and "0.00" are different and only one deserves a total.
    #:
    #: **Two figures since August 27, 2026**, replacing a single `totals` that
    #: held what was outstanding and was rendered under the word *total* -- so a
    #: month that cost 1264.99 reported 64.99. Renamed rather than added to, so
    #: that every caller had to say which question it was asking.
    due_totals: dict[str, str]
    #: What has already gone out this month, per currency.
    paid_totals: dict[str, str]
    #: What is expected in and has not arrived, per currency.
    expected_in_totals: dict[str, str]
    #: What has already arrived, per currency. Apart from what is expected for
    #: the same reason paid is apart from due: a figure mixing the two cannot
    #: say whether a month balanced or merely looks as though it will.
    received_totals: dict[str, str]
    #: How many are counted but not totalled, so the figure above cannot
    #: quietly understate the month.
    unpriced: int


class NewBillIn(Schema):
    """What adding a bill asks for, and what it deliberately does not.

    **No task title.** The name is derived from the payee -- `Landlord` becomes
    *Pay Landlord* -- so this surface never asks the person to name a task or to
    know that a bill is one. Vince's call, August 27, 2026.

    **No Area either.** A bill is not filed; `create_bill` makes a standing
    task, which is what `create_item`'s owner argument exists for.
    """

    payee: str
    #: A string like `BillOut.amount`, and null for a bill nobody has priced --
    #: "the water bill, whatever it comes to" is a real bill and the month
    #: already counts unpriced ones rather than totalling them.
    amount: str | None = None
    currency: str = "USD"
    due_date: date
    #: On by default, because the canonical bill is rent. A repeating bill
    #: keeps its payee and currency across occurrences and gets a fresh amount
    #: each time -- see `_spawn_next_occurrence`.
    repeats: bool = True
    #: Which cadence, when it is not monthly. The model has always had weekly,
    #: quarterly and annual; the form offered a checkbox, which is why an
    #: annual subscription could not be expressed at all.
    recurrence: str | None = None
    #: Days of warning before it lands. **The reason this module exists**: an
    #: annual subscription that speaks on the day it renews has already
    #: charged you. Zero is off, and `agenda.py` already surfaces anything
    #: inside its lead time.
    lead_days: int = 0


@router.post("/money/bills", response={201: MonthBillOut}, auth=SessionAuthIfLoggedIn())
def add_bill(request, payload: NewBillIn):
    """Create a bill where bills are.

    Session-only for the same reason the month read is: a surface the phone
    does not have, and widening the token surface for one it cannot show is the
    un-switched-on seam this project keeps finding.
    """
    amount = None
    if payload.amount not in (None, ""):
        try:
            amount = Decimal(payload.amount)
        except InvalidOperation:
            # 409 like every other refusal on this router, and a sentence
            # rather than a field error: the form has one amount box and the
            # message is what it will show beside it.
            raise HttpError(409, "That amount is not a number.")
    try:
        item = services.create_bill(
            request.user,
            payee=payload.payee,
            amount=amount,
            currency=payload.currency,
            due_date=payload.due_date,
            repeats=payload.repeats,
        )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    bill = item.money_line
    return 201, {
        "task_id": item.id,
        "text": item.text,
        "due_date": item.due_date,
        "amount": str(bill.amount) if bill.amount is not None else None,
        "currency": bill.currency,
        "payee": bill.payee,
        "url": reverse("api_item_detail", args=[item.id]),
        "paid": False,
        "repeats": item.recurrence != Item.Recurrence.NONE,
        "direction": item.money_line.direction,
        "recurrence": item.recurrence,
        "lead_days": item.lead_days,
        "paid_amount": None,
        "overdue": False,
    }


class EditBillIn(Schema):
    """Every field optional, and absent is not empty.

    The same partial-write contract the day and the review already have: a field
    left out keeps its stored value. **Clearing an amount is explicit** --
    `amount: null` with `clear_amount: true` -- because "the water bill,
    whatever it comes to" is a state somebody chooses rather than a field they
    forgot to fill in.
    """

    payee: str | None = None
    amount: str | None = None
    clear_amount: bool = False
    currency: str | None = None
    due_date: date | None = None
    lead_days: int | None = None
    recurrence: str | None = None


def _bill_row_out(item):
    """One bill, shaped like a row of the month it belongs to."""
    bill = item.money_line
    return {
        "task_id": item.id,
        "text": item.text,
        "due_date": item.due_date,
        "amount": str(bill.amount) if bill.amount is not None else None,
        "currency": bill.currency,
        "payee": bill.payee,
        "url": reverse("api_item_detail", args=[item.id]),
        # `completed_at`, not the status: a paid *recurring* occurrence is
        # ARCHIVED rather than COMPLETED, so reading the status would report
        # every paid rent as unpaid. Same rule as `BillRow.paid`.
        "paid": item.completed_at is not None,
        "repeats": item.recurrence != Item.Recurrence.NONE,
        "direction": item.money_line.direction,
        "recurrence": item.recurrence,
        "lead_days": item.lead_days,
        "paid_amount": (
            str(item.money_line.paid_amount) if item.money_line.paid_amount is not None else None
        ),
        "overdue": (
            item.completed_at is None
            and item.due_date is not None
            and item.due_date < today_for(item.owner)
        ),
    }


@router.patch(
    "/money/bills/entry/{task_id}", response=MonthBillOut, auth=SessionAuthIfLoggedIn()
)
def edit_bill(request, task_id: int, payload: EditBillIn):
    """Correct a bill without leaving the page it is shown on.

    **`entry/{id}` rather than `{id}`**, because `/money/bills/{day}` already
    takes a date in that position and two routes differing only by the type of
    one segment is a collision waiting for the first numeric-looking date. The
    read keeps the shorter path; the writes take the longer one.

    **Under `/money/` since August 27, 2026.** The resources are still bills --
    a bill is one kind of money thing and income will be its sibling, not the
    same record -- so what moved is the namespace, not the noun. `MoneyLine` keeps
    its name for exactly that reason: a model named after the module would have
    to hold both.
    """
    item = Item.objects.filter(pk=task_id, owner=request.user).first()
    if item is None:
        raise HttpError(404, "No such bill.")
    fields = {}
    if payload.payee is not None:
        fields["payee"] = payload.payee
    if payload.currency is not None:
        fields["currency"] = payload.currency
    if payload.due_date is not None:
        fields["due_date"] = payload.due_date
    if payload.lead_days is not None:
        fields["lead_days"] = payload.lead_days
    if payload.recurrence is not None:
        fields["recurrence"] = payload.recurrence
    if payload.clear_amount:
        fields["clear_amount"] = True
    elif payload.amount not in (None, ""):
        try:
            fields["amount"] = Decimal(payload.amount)
        except InvalidOperation:
            raise HttpError(409, "That amount is not a number.")
    try:
        item = services.update_bill(item, **fields)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    except services.InvalidTaskTransition as error:
        raise HttpError(409, str(error))
    return _bill_row_out(item)


class PayBillIn(Schema):
    """What went out, when it is not what was expected.

    Null means *what the bill said*, so the ordinary case is one click and the
    figure is still recorded rather than reconstructed later.
    """

    amount: str | None = None


class NewIncomeIn(Schema):
    """What adding income asks for. The mirror of `NewBillIn`, one word apart.

    `payer` rather than `payee`, because that is what a person calls the other
    end of money coming toward them -- and the name is derived from it the same
    way: `Acme Ltd` becomes *From Acme Ltd*.
    """

    payer: str
    amount: str | None = None
    currency: str = "USD"
    due_date: date
    repeats: bool = True
    recurrence: str | None = None
    lead_days: int = 0


@router.post(
    "/money/income", response={201: MonthBillOut}, auth=SessionAuthIfLoggedIn()
)
def add_income(request, payload: NewIncomeIn):
    """Record money expected in.

    **Beside bills under `/money/`, not a second top-level noun** -- which is
    what makes Money a module rather than a longer word for one page.
    """
    amount = None
    if payload.amount not in (None, ""):
        try:
            amount = Decimal(payload.amount)
        except InvalidOperation:
            raise HttpError(409, "That amount is not a number.")
    try:
        item = services.create_income(
            request.user,
            payer=payload.payer,
            amount=amount,
            currency=payload.currency,
            due_date=payload.due_date,
            repeats=payload.repeats,
            recurrence=payload.recurrence,
            lead_days=payload.lead_days,
        )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return 201, _bill_row_out(item)


@router.post(
    "/money/bills/entry/{task_id}/pay", response=MonthBillOut, auth=SessionAuthIfLoggedIn()
)
def pay_bill(request, task_id: int, payload: PayBillIn):
    """Pay a bill from the page it is shown on.

    **The action this page was missing entirely.** It could add a bill and
    delete a bill and not pay one, which is the thing a person does twelve
    times more often than both put together.
    """
    item = Item.objects.filter(pk=task_id, owner=request.user).first()
    if item is None:
        raise HttpError(404, "No such bill.")
    amount = None
    if payload.amount not in (None, ""):
        try:
            amount = Decimal(payload.amount)
        except InvalidOperation:
            raise HttpError(409, "That amount is not a number.")
    try:
        item = services.pay_bill(item, amount=amount)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    item.refresh_from_db()
    return _bill_row_out(item)


@router.delete(
    "/money/bills/entry/{task_id}", response={204: None}, auth=SessionAuthIfLoggedIn()
)
def remove_bill(request, task_id: int, whole_series: bool = False):
    """Remove a bill, and say which one is meant when it repeats.

    **`whole_series` as a query parameter** rather than a body: a DELETE with a
    payload is legal and poorly supported, and this is one boolean the caller
    already knows before it asks.

    The default is the narrow act. Deleting August's rent means *not this one*;
    somebody who meant *stop paying rent* has to say so, because the wider
    answer is the one that cannot be undone by adding a bill back.
    """
    item = Item.objects.filter(pk=task_id, owner=request.user).first()
    if item is None:
        raise HttpError(404, "No such bill.")
    try:
        services.delete_bill(item, whole_series=whole_series)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return 204, None


class AccountOut(Schema):
    id: int
    name: str
    kind: str
    currency: str
    #: Whether the figure is money owed or money held. **Named, not signed** --
    #: a card at 4,200 and an ISA at 4,200 are both four thousand two hundred,
    #: and a negative number would make every reader carry a convention.
    owes: bool
    #: This month's figure, if one has been recorded. Null is *not entered yet*,
    #: which is different from zero and is the state the update screen exists to
    #: clear.
    balance: str | None
    #: The month before's, so the page can say which way it moved without a
    #: second request.
    previous: str | None


class AccountsOut(Schema):
    month_start: date
    accounts: list[AccountOut]
    #: Per currency, and **owed and held apart**: subtracting one from the other
    #: is a net worth, which is a different claim from either and not one this
    #: page makes.
    owed_totals: dict[str, str]
    held_totals: dict[str, str]


class NewAccountIn(Schema):
    name: str
    kind: str = "card"
    currency: str = "USD"
    #: Null lets the kind decide -- a card and a loan owe, savings and
    #: investments hold -- so the common case is two fields rather than four.
    owes: bool | None = None


class BalanceIn(Schema):
    """One month's figure for one account."""

    account_id: int
    #: Null means *leave this one alone*, which is what an untouched box on the
    #: update screen means. Blanking a figure already recorded is not offered:
    #: nothing is served by being able to un-know what a balance was.
    amount: str | None = None


class BalancesIn(Schema):
    """The monthly pass, as one request.

    **A batch because the ritual is a batch.** Vince described sitting down at
    month end and updating every balance; six separate requests would make that
    six chances to be half-done, and a page that is half-saved is worse than one
    that is not saved.
    """

    on_date: date
    readings: list[BalanceIn]


class LandingLineOut(Schema):
    """One money line, as the landing page needs it -- shorter than a month row
    because a dashboard names things rather than offering every verb."""

    task_id: int
    text: str
    payee: str
    due_date: date
    amount: str | None
    currency: str
    #: Days from today. Negative is overdue, and the page words it rather than
    #: the reader doing the arithmetic.
    days: int


class MoneyLandingOut(Schema):
    today: date
    overdue: list[LandingLineOut]
    due_soon: list[LandingLineOut]
    renewing_soon: list[LandingLineOut]
    yearly_totals: dict[str, str]
    owed_totals: dict[str, str]
    held_totals: dict[str, str]
    #: The move since last month. Negative is down; what that *means* depends
    #: on which side it is, and the page says so rather than this.
    owed_change: dict[str, str]
    held_change: dict[str, str]
    unread_accounts: int


@router.get("/money", response=MoneyLandingOut, auth=SessionAuthIfLoggedIn())
def money_landing(request):
    """How the money stands, today.

    **No date in the path.** Every other read here takes one because it is about
    a month; this one is about *now*, and a landing page addressed by date would
    invite the question of what last Tuesday's dashboard looked like.
    """
    today = today_for(request.user)
    found = money_reader.landing_for(request.user, today=today)

    def line(row):
        return {
            "task_id": row.task.id,
            "text": row.task.text,
            "payee": row.bill.payee,
            "due_date": row.task.due_date,
            "amount": (
                str(row.bill.amount) if row.bill.amount is not None else None
            ),
            "currency": row.bill.currency,
            "days": (row.task.due_date - today).days,
        }

    def money(totals):
        return {code: str(total) for code, total in totals.items()}

    return {
        "today": today,
        "overdue": [line(row) for row in found.overdue],
        "due_soon": [line(row) for row in found.due_soon],
        "renewing_soon": [line(row) for row in found.renewing_soon],
        "yearly_totals": money(found.yearly_totals),
        "owed_totals": money(found.owed_totals),
        "held_totals": money(found.held_totals),
        "owed_change": money(found.owed_change),
        "held_change": money(found.held_change),
        "unread_accounts": found.unread_accounts,
    }


@router.get("/money/accounts/{day}", response=AccountsOut, auth=SessionAuthIfLoggedIn())
def months_accounts(request, day: date):
    """Every account, with the month's figure and the one before it."""
    first = day.replace(day=1)
    previous = (first - timedelta(days=1)).replace(day=1)
    accounts = list(
        Account.objects.filter(owner=request.user).prefetch_related("readings")
    )
    owed = defaultdict(Decimal)
    held = defaultdict(Decimal)
    rows = []
    for account in accounts:
        by_month = {r.on_date: r.amount for r in account.readings.all()}
        current = by_month.get(first)
        if current is not None:
            (owed if account.owes else held)[account.currency] += current
        rows.append(
            {
                "id": account.id,
                "name": account.name,
                "kind": account.kind,
                "currency": account.currency,
                "owes": account.owes,
                "balance": str(current) if current is not None else None,
                "previous": (
                    str(by_month[previous]) if previous in by_month else None
                ),
            }
        )
    return {
        "month_start": first,
        "accounts": rows,
        "owed_totals": {code: str(total) for code, total in owed.items()},
        "held_totals": {code: str(total) for code, total in held.items()},
    }


@router.post("/money/accounts", response={201: AccountOut}, auth=SessionAuthIfLoggedIn())
def add_account(request, payload: NewAccountIn):
    try:
        account = services.create_account(
            request.user,
            name=payload.name,
            kind=payload.kind,
            currency=payload.currency,
            owes=payload.owes,
        )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return 201, {
        "id": account.id,
        "name": account.name,
        "kind": account.kind,
        "currency": account.currency,
        "owes": account.owes,
        "balance": None,
        "previous": None,
    }


@router.post("/money/balances", response={200: AccountsOut}, auth=SessionAuthIfLoggedIn())
def record_balances(request, payload: BalancesIn):
    """The monthly pass, saved in one go.

    **One transaction**, so a bad figure in the fifth box does not leave four
    saved and two not -- which is the failure a batch exists to prevent and
    would otherwise quietly introduce.
    """
    owned = {
        account.id: account
        for account in Account.objects.filter(owner=request.user)
    }
    with transaction.atomic():
        for reading in payload.readings:
            # An untouched box means leave it alone, not blank it. Nothing is
            # served by being able to un-know what a balance was.
            if reading.amount in (None, ""):
                continue
            account = owned.get(reading.account_id)
            if account is None:
                # Not 404: a batch naming somebody else's account is a bad
                # request about this batch, and answering per-row would leak
                # which ids exist.
                raise HttpError(400, "That is not one of your accounts.")
            try:
                services.record_balance(
                    account,
                    on_date=payload.on_date,
                    amount=Decimal(reading.amount),
                )
            except InvalidOperation:
                raise HttpError(409, f"{account.name}: that is not a number.")
            except services.TaskConflict as error:
                raise HttpError(409, f"{account.name}: {error}")
    return months_accounts(request, payload.on_date)


@router.get("/money/bills/{day}", response=MonthOfBillsOut, auth=SessionAuthIfLoggedIn())
def months_bills(request, day: date):
    """What is due this month and what it comes to.

    Session-only, like the calendar: a new surface the phone does not have,
    and widening the token surface for one it cannot show would be the
    un-switched-on seam this project keeps finding.
    """
    found = money_reader.bills_for(request.user, day)
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])
    return {
        "month_start": first,
        "previous_month": (first - timedelta(days=1)).replace(day=1),
        "next_month": last + timedelta(days=1),
        "bills": [
            {
                "task_id": row.task.id,
                "text": row.task.text,
                "due_date": row.task.due_date,
                "amount": (
                    str(row.bill.amount) if row.bill.amount is not None else None
                ),
                "currency": row.bill.currency,
                "payee": row.bill.payee,
                "url": reverse("api_item_detail", args=[row.task.id]),
                "paid": row.paid,
                "repeats": row.task.recurrence != Item.Recurrence.NONE,
                "direction": row.bill.direction,
                "recurrence": row.task.recurrence,
                "lead_days": row.task.lead_days,
                "paid_amount": (
                    str(row.bill.paid_amount)
                    if row.bill.paid_amount is not None
                    else None
                ),
                "overdue": row.overdue_on(today_for(request.user)),
            }
            for row in found.bills
        ],
        "due_totals": {
            code: str(total) for code, total in found.due_totals.items()
        },
        "expected_in_totals": {
            code: str(total) for code, total in found.expected_in_totals.items()
        },
        "received_totals": {
            code: str(total) for code, total in found.received_totals.items()
        },
        "paid_totals": {
            code: str(total) for code, total in found.paid_totals.items()
        },
        "unpriced": found.unpriced,
    }


@router.get("/nav", response=NavOut)
def navigation(request):
    """Everything the persistent side nav needs, on every page.

    A single endpoint rather than three payloads each growing the same
    fields: the agenda already carried area summaries, but the area page and
    archive didn't, and duplicating them into both schemas would mean three
    places to keep in step.
    """
    user = request.user
    return {
        "areas": agenda_reader.list_summaries(user),
        "projects": [
            {
                "id": each.id,
                "title": each.title,
                "open_task_count": each.open_task_count,
            }
            for each in project_reader.projects_for(user).filter(is_completed=False)
        ],
        "archived_count": Item.objects.filter(
            owner=user, status=Item.Status.ARCHIVED
        ).count(),
        "settings_url": reverse("account_settings"),
        # Django pages, not SPA routes: these links leave the app shell.
        "mind_url": reverse("capture"),
        "landing_surface": user.landing_surface,
        "deletion_purge_at": account_services.purge_at(user),
    }


@router.get(
    "/agenda",
    response=AgendaOut,
    # Token auth as well as session -- android-full-client-plan.md's slice
    # 2. Read-only: the write actions the Agenda page performs live on the
    # hand-rolled lists.api views, which get their own token support via
    # token_or_session_required (see accounts/auth.py and
    # token-scopes-plan.md §7) since they were never on this Ninja router.
    auth=[TokenAuth(SCOPE_AGENDA_READ), SessionAuthIfLoggedIn()],
)
def agenda(request):
    user = request.user
    today = timezone.localdate()
    all_open = agenda_reader.annotate_for_display(
        list(agenda_reader.open_items_for(user)), today
    )
    completed_today = agenda_reader.annotate_for_display(
        list(agenda_reader.completed_today_for(user, today)), today
    )
    lists = agenda_reader.list_summaries(user)
    archived_count = Item.objects.filter(
        owner=user,
        status=Item.Status.ARCHIVED,
    ).count()
    projects = project_reader.projects_for(user)

    return agenda_reader.workspace_data_for(
        user,
        today=today,
        all_open=all_open,
        completed_today=completed_today,
        lists=lists,
        archived_count=archived_count,
        projects=projects,
    )


def _parse_date(value):
    """YYYY-MM-DD or nothing. The server owns date meaning, per
    principles.md -- a client sends the string it was given and this decides
    what it means.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HttpError(400, "Use a valid date (YYYY-MM-DD).")


def _owned_area(request, area_id):
    return get_object_or_404(List, id=area_id, owner=request.user)


@router.get("/areas/{area_id}", response=AreaDetailOut)
def area_detail(request, area_id: int):
    our_list = _owned_area(request, area_id)
    items = list(
        our_list.item_set.exclude(status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
    )
    return {
        **area_workspace_data_for(our_list, items),
        "archived_count": our_list.item_set.filter(
            status=Item.Status.ARCHIVED,
        ).count(),
        "archive_url": reverse("archive"),
    }


@router.patch("/areas/{area_id}", response=AreaRefOut)
def rename_area(request, area_id: int, payload: AreaRenameIn):
    our_list = _owned_area(request, area_id)
    # Reuses ListTitleForm's own validation (strip, required, max_length)
    # rather than re-implementing it, so the two entry points to the same
    # rule can't quietly drift.
    form = ListTitleForm(data={"title": payload.title}, instance=our_list)
    if not form.is_valid():
        raise HttpError(400, form.errors["title"][0])
    form.save()
    return area_ref_for(our_list)


@router.delete("/areas/{area_id}")
def delete_area(request, area_id: int):
    our_list = _owned_area(request, area_id)
    services.delete_list(our_list)
    return {"deleted": area_id}


@router.get("/tasks/{item_id}", response=TaskDetailOut)
def task_detail(request, item_id: int):
    # Matches edit_item's queryset exactly: archived tasks are managed
    # from the Archive route (restore/delete), not edited here.
    item = get_object_or_404(
        Item.objects.select_related("list", "commitment").prefetch_related("tags"),
        id=item_id,
        owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    return task_detail_data_for(item)


class ProjectOut(Schema):
    id: int
    title: str
    # Always a string, never null -- the model is blank-not-null and the wire
    # keeps that, so a client has one representation of "nothing written"
    # rather than two to coerce.
    purpose: str
    # Same blank-not-null contract as `purpose` above, and for the same reason.
    desired_outcome: str
    # What going wrong looks like -- S10, and D4's answer that this is not
    # `desired_outcome`. Same contract again.
    abandon_if: str
    notes: str
    due_date: str | None
    is_completed: bool
    completed_at: str | None
    # **Only the timestamp, where completion sends a flag and a stamp.** That
    # pair exists because `is_completed` predates `completed_at` and a check
    # constraint keeps them honest; there is nothing to keep honest here, and
    # `paused_at !== null` is a client-side expression rather than a second
    # field free to disagree with the first.
    paused_at: str | None
    created_at: str
    open_task_count: int
    areas: list["ProjectAreaOut"]
    is_overdue: bool


class ProjectAreaOut(Schema):
    id: int
    title: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class ProjectCreateIn(Schema):
    title: str
    # `str | None = None` rather than `str = ""`, which is the shape the field
    # actually wants and not what it looks like. A pydantic default reaches the
    # contract as `"default": ""`, and openapi-typescript 7 emits any property
    # carrying a default as *required* -- it always has a value, so the
    # generator says so -- which made `purpose` mandatory at every call site
    # that creates a project and broke the build. `due_date` above already has
    # this shape, which is why it did not.
    purpose: str | None = None
    due_date: str | None = None


class ProjectUpdateIn(Schema):
    """Every field optional; absent means "leave it alone".

    `due_date` has to distinguish absent from explicitly null, because
    clearing a due date and not mentioning it are different requests and
    `str | None = None` cannot tell them apart on its own. The handler reads
    `exclude_unset` rather than inventing a sentinel default.

    **`purpose` needs none of that**, and the asymmetry is worth naming
    because it looks like an oversight. Its cleared state is `""`, not null,
    so `None` is free to mean exactly one thing -- the client did not mention
    the field. That is what blank-not-null buys at the boundary.
    """

    title: str | None = None
    purpose: str | None = None
    # Same shape as `purpose`, same reason: "" is its cleared state, so None
    # means only "not mentioned".
    desired_outcome: str | None = None
    abandon_if: str | None = None
    notes: str | None = None
    due_date: str | None = None
    is_completed: bool | None = None
    # A boolean like `is_completed` rather than a verb route, because both
    # answer "which state is this project in" and two spellings of one idea is
    # the near-identical-controls problem C2 found in the task UI.
    is_paused: bool | None = None
    #: **S12's fourth clause.** Written after the work stops rather than
    #: with the completion, because the lesson arrives while reading what the
    #: retrospective shows.
    learned: str | None = None


class AreaProjectIn(Schema):
    # null clears it -- explicit rather than a separate DELETE route, since
    # "move to another project" and "remove from any project" are the same
    # write from the Area's point of view.
    project_id: int | None


def _areas_by_project(user):
    """This owner's areas, grouped by which project (if any) they're in.

    Computed once per request rather than once per project inside
    _project_out -- reuses list_summaries's own open/overdue annotation, one
    authoritative definition of "an area's open count," not two.
    """
    grouped = {}
    for each in agenda_reader.list_summaries(user):
        if each.project_id is not None:
            grouped.setdefault(each.project_id, []).append(each)
    return grouped


def _project_out(project, areas=None):
    if areas is None:
        areas = _areas_by_project(project.owner).get(project.id, [])
    return {
        "id": project.id,
        "title": project.title,
        "purpose": project.purpose,
        "desired_outcome": project.desired_outcome,
        "abandon_if": project.abandon_if,
        "learned": project.learned,
        "notes": project.notes,
        "paused_at": (
            project.paused_at.isoformat() if project.paused_at else None
        ),
        "due_date": project.due_date.isoformat() if project.due_date else None,
        # A finished project is never overdue regardless of due_date -- the
        # same rule tasks and areas already apply, extended here rather than
        # left for the client to reinvent with its own idea of "today".
        "is_overdue": (
            not project.is_completed
            and project.due_date is not None
            and project.due_date < timezone.localdate()
        ),
        "is_completed": project.is_completed,
        "completed_at": (
            project.completed_at.isoformat() if project.completed_at else None
        ),
        "created_at": project.created_at.isoformat(),
        # Annotated by projects_for; a freshly created project has not been
        # through that read, so it falls back rather than raising.
        "open_task_count": getattr(project, "open_task_count", 0),
        "areas": [
            {
                "id": each.id,
                "title": each.title,
                "open_count": each.open_count,
                "overdue_count": each.overdue_count,
                "color_key": each.color_key,
            }
            for each in areas
        ],
    }


@router.get("/projects", response=list[ProjectOut])
def projects(request):
    by_project = _areas_by_project(request.user)
    return [
        _project_out(each, areas=by_project.get(each.id, []))
        for each in project_reader.projects_for(request.user)
    ]


@router.get("/projects/{project_id}", response=ProjectOut)
def project_detail(request, project_id: int):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    return _project_out(project)


class BriefItemOut(Schema):
    """One retrieved note, with the evidence that selected it.

    `reason` is not decoration. Without it the interface can only say
    "related", which is the unfalsifiable label this whole mechanic exists to
    avoid -- `precision.md`'s point is that a person can check "these share
    three words appearing in none of your other notes" and cannot check a
    score.
    """

    id: str
    text: str
    captured_at: str
    reason: str
    distinctive_terms: list[str]


class BriefCommitmentOut(Schema):
    id: int
    text: str
    due_date: str | None


class BriefSourceOut(Schema):
    """Something read that this project's material came out of — **S16**.

    `reason` is a fact rather than a score, like `BriefItemOut`'s and for the
    same argument: the person can check *a note here came out of it* and cannot
    check a number.
    """

    id: str
    title: str
    author: str
    url: str
    reason: str
    note_count: int


class BriefDecisionOut(Schema):
    """A choice made while looking at this project's material — **S16**.

    `superseded` rather than omitting the ones that were replaced: *what he
    learned last time* includes the answer he later changed, and hiding it would
    remove the part that makes keeping the record worth anything.
    """

    id: str
    question: str
    chose: str
    considered: str
    decided_at: str
    superseded: bool
    reason: str


class BriefLessonOut(Schema):
    """What an earlier finished project taught — **S12's *kept for next time***.

    Named with its project, because a lesson with no source is an aphorism.
    """

    project_id: int
    project_title: str
    learned: str


class ProjectBriefOut(Schema):
    material: list[BriefItemOut]
    questions: list[BriefItemOut]
    commitments: list[BriefCommitmentOut]
    #: **S16's other two nouns.** The story's done-means is *notes, decisions
    #: and sources*, and this payload carried one of three until August 22,
    #: 2026 — because `Source` and `Decision` did not exist until that day.
    sources: list[BriefSourceOut]
    decisions: list[BriefDecisionOut]
    #: Why the two sections above are empty, when they are and it is not
    #: because nothing bears on the project. D5's discipline, one axis over.
    provenance_says: str
    #: What earlier finished projects taught. Delivered on the **brief**
    #: rather than the retrospective, because *next time* is a different
    #: project from the one that learned it — and the brief is what somebody
    #: opens while a project is still running.
    learned_before: list[BriefLessonOut]
    #: **S10's second clause**, which this payload dropped from the day the
    #: field was added until August 22, 2026. `ProjectBrief.abandon_if` says *a
    #: field nobody sees at the moment of deciding is a field that may as well
    #: not exist* — and nobody saw it, because it stopped here.
    abandon_if: str


def _brief_source_out(each):
    return {
        "id": str(each.source.public_id),
        "title": each.source.title,
        "author": each.source.author,
        "url": each.source.url,
        "reason": each.reason,
        "note_count": len(each.through),
    }


def _brief_decision_out(each):
    return {
        "id": str(each.decision.public_id),
        "question": each.decision.question,
        "chose": each.decision.chose,
        "considered": each.decision.considered,
        "decided_at": each.decision.decided_at.isoformat(),
        # Whether a later decision replaced this one. `revisited_at` alone would
        # not say: looking again and changing your mind are different acts, and
        # only the second supersedes.
        "superseded": each.decision.superseded_by.exists(),
        "reason": each.reason,
    }


def _brief_item_out(item):
    return {
        "id": str(item.node.public_id),
        "text": item.node.original_content,
        "captured_at": item.node.captured_at.isoformat(),
        "reason": item.reason,
        "distinctive_terms": list(item.distinctive_terms),
    }


class RetroWeekOut(Schema):
    week_start: str
    met: int
    unfinished: int
    set_aside: int


class RetroNoteOut(Schema):
    id: str
    text: str
    captured_at: str


class RetroDecisionOut(Schema):
    id: str
    question: str
    chose: str
    considered: str
    decided_at: str


class ProjectRetrospectiveOut(Schema):
    """What a project came to — **S12**.

    Week by week rather than one pair of numbers: a project that started well
    and stalled and one that ground along evenly have the same totals, and only
    the first is worth knowing about.
    """

    weeks: list[RetroWeekOut]
    met: int
    unfinished: int
    set_aside: int
    notes: list[RetroNoteOut]
    decisions: list[RetroDecisionOut]
    learned: str
    #: One sentence rather than a run of empty rows — see
    #: `projects.Retrospective.quiet_weeks_before_closing`.
    quiet_says: str


@router.get(
    "/projects/{project_id}/retrospective", response=ProjectRetrospectiveOut
)
def project_retrospective(request, project_id: int):
    """What a project came to, assembled rather than remembered — **S12**.

    **Its own route rather than part of the brief**, and the split is the point:
    a brief prompts a project that is *running* and may answer topically; a
    retrospective is a record of one that is over, and every item in it is a row
    somebody wrote. Same argument that gave the brief its own route, one state
    later.

    Reads only. There is nothing to confirm and nothing to stamp — see
    `projects.Retrospective`.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    looking_back = project_reader.retrospective_for(request.user, project)
    return {
        "weeks": [
            {
                "week_start": week.week_start.isoformat(),
                "met": week.met,
                "unfinished": week.unfinished,
                "set_aside": week.set_aside,
            }
            for week in looking_back.weeks
        ],
        "met": looking_back.met,
        "unfinished": looking_back.unfinished,
        "set_aside": looking_back.set_aside,
        "notes": [
            {
                "id": str(node.public_id),
                "text": node.original_content,
                "captured_at": node.captured_at.isoformat(),
            }
            for node in looking_back.notes
        ],
        "decisions": [
            {
                "id": str(decision.public_id),
                "question": decision.question,
                "chose": decision.chose,
                "considered": decision.considered,
                "decided_at": decision.decided_at.isoformat(),
            }
            for decision in looking_back.decisions
        ],
        "learned": looking_back.learned,
        "quiet_says": looking_back.quiet_says,
    }


@router.get("/projects/{project_id}/brief", response=ProjectBriefOut)
def project_brief(request, project_id: int):
    """What bears on this project, asked for rather than implied.

    **Its own route rather than a fatter `ProjectOut`.** A brief runs a
    full-text retrieval and a project detail is fetched on every render of a
    page that mostly wants a title; paying for the search each time would be
    the wrong default. It also matches what this is -- a briefing somebody
    opens, which is the Attention Policy's condition for showing a queue at
    all.

    Reads only, and records nothing. See `projects.ProjectBrief` for why that
    differs from `/mind/review/`, which records being opened on purpose.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    brief = project_reader.brief_for(request.user, project)
    return {
        "material": [_brief_item_out(each) for each in brief.material],
        "questions": [_brief_item_out(each) for each in brief.questions],
        "commitments": [
            {
                "id": task.id,
                "text": task.text,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            }
            for task in brief.commitments
        ],
        "sources": [_brief_source_out(each) for each in brief.sources],
        "decisions": [_brief_decision_out(each) for each in brief.decisions],
        "learned_before": [
            {
                "project_id": each.project.id,
                "project_title": each.project.title,
                "learned": each.learned,
            }
            for each in brief.learned_before
        ],
        "provenance_says": brief.provenance_says,
        "abandon_if": brief.abandon_if,
    }


@router.post("/projects", response=ProjectOut)
def create_project(request, payload: ProjectCreateIn):
    try:
        project = services.create_project(
            request.user,
            payload.title,
            due_date=_parse_date(payload.due_date),
            purpose=payload.purpose or "",
        )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return _project_out(project)


@router.patch("/projects/{project_id}", response=ProjectOut)
def update_project(request, project_id: int, payload: ProjectUpdateIn):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    if payload.is_completed is not None:
        if payload.is_completed:
            services.complete_project(project)
        else:
            services.reopen_project(project)
    # After completion, deliberately. `complete_project` clears the pause, so a
    # request that finished and paused in one call would otherwise depend on
    # the order these branches happen to be written in.
    if payload.is_paused is not None:
        if payload.is_paused:
            services.pause_project(project)
        else:
            services.resume_project(project)

    fields = []
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HttpError(409, services.EMPTY_PROJECT_TITLE_ERROR)
        project.title = title
        fields.append("title")
    if payload.purpose is not None:
        # No exclude_unset dance: "" is the cleared state, so None already
        # means only "not mentioned". See ProjectUpdateIn.
        project.purpose = payload.purpose.strip()
        fields.append("purpose")
    if "due_date" in payload.dict(exclude_unset=True):
        project.due_date = _parse_date(payload.due_date)
        fields.append("due_date")
    if fields:
        project.save(update_fields=fields)

    # Through their services rather than assigned here, which is the entire
    # reason those services were written -- `set_desired_outcome` says so in
    # its own docstring, and the call site was never switched over, so the pair
    # it exists to keep distinguishable had one half in each place for two
    # days. The services strip and store `""` for the cleared state, so `None`
    # still means only *not mentioned*.
    #
    # After the title check, so a 409 on an empty title writes none of them.
    if payload.desired_outcome is not None:
        services.set_desired_outcome(project, payload.desired_outcome)
    if payload.abandon_if is not None:
        services.set_abandonment_condition(project, payload.abandon_if)
    if payload.notes is not None:
        services.set_project_notes(project, payload.notes)
    # **S12**, and it belongs here with the rest. An earlier pass left this one
    # assigned in the handler on the stated grounds that it had no service to
    # route to -- it has had `record_what_was_learned` since August 23, and the
    # comment saying otherwise was written without looking. The same omission
    # as the three above, found the same way.
    if payload.learned is not None:
        services.record_what_was_learned(project, payload.learned)

    return _project_out(project_reader.project_for(request.user, project_id))


@router.delete("/projects/{project_id}")
def delete_project(request, project_id: int):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    services.delete_project(project)
    return {"deleted": project_id}


@router.patch("/areas/{area_id}/project", response=AreaRefOut)
def assign_area_project(request, area_id: int, payload: AreaProjectIn):
    """Put an Area into a Project, move it, or take it out again.

    A dedicated route rather than folding into AreaRenameIn: that schema's
    one field is always required, and project_id is optional/tri-state --
    bolting the two together would mean the always-required half inheriting
    exclude_unset semantics it doesn't need.
    """
    our_list = _owned_area(request, area_id)
    if payload.project_id is None:
        services.remove_area_from_project(our_list)
    else:
        project = project_reader.project_for(request.user, payload.project_id)
        if project is None:
            raise HttpError(404, "Project not found.")
        try:
            services.add_area_to_project(our_list, project)
        except services.TaskConflict as error:
            raise HttpError(409, str(error))
    return area_ref_for(our_list)


class AreaCreateIn(Schema):
    title: str


@router.post("/projects/{project_id}/areas", response=AreaRefOut)
def create_area_in_project(request, project_id: int, payload: AreaCreateIn):
    """A new, empty Area, already inside this Project.

    No first task required, unlike the Agenda sidebar's own "+ New area" --
    Vince's call, August 10, 2026: the predominant use case for a project
    is areas that don't exist yet, not reassigning ones that do.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    area = services.create_area(request.user, payload.title, project=project)
    return area_ref_for(area)


@router.get("/archive", response=ArchiveOut)
def archive(request):
    user = request.user
    archived_items = list(
        Item.objects.filter(owner=user, status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
        .order_by("-archived_at", "-id")
    )
    return archive_workspace_data_for(user, archived_items)
