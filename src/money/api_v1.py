"""The Money module's HTTP surface.

**Its own router since September 2, 2026**, step 3 of moving Money into an app.
Sixteen of `lists/api_v1.py`'s forty-one endpoints were money's, which is a
large slice of a file named after something else -- and every one of them was
about a record the task core no longer owns.

**`/api/v1/money/*` is unchanged**, and that is the point: this is a backend
ownership correction and no client should be able to tell it happened. The
frontend routes stay `/money`, the paths stay identical, and
`clarice/api.py` mounts this router at the same empty prefix as every other.

**`AgendaBillOut` lives here and is imported by two task surfaces.** That is the
contract `modules.md` asks for rather than a leak: the Day and the Agenda show
bills, so they receive them in a shape money defines. The dependency points from
the task core into money and not the other way, which is what makes the
extraction one-directional.

**One router, not two.** A knowledge-core endpoint belongs on `/api/v1/` as a
router beside the others -- `CLAUDE.md`'s rule, and the reason `mind`'s second
`NinjaAPI` was deleted having never been called. The same applies here.
"""
import datetime
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn
from clarice.clocks import today_for
from clarice.errors import Conflict
from clarice.recurrence import Recurrence
from money.models import Account, Bill, Direction, MoneyCategory
from money import reads as money_reader
from money import services as bills

router = Router()


class AgendaBillOut(Schema):
    """A bill as the agenda and the day carry it: what a bill is, and none of
    what a task is.

    **`id`, and it is a `Bill`'s.** It was `task_id` from August 31 to
    September 1, 2026 -- deliberately, so that the commit changing what a bill
    *is* did not also carry a mechanical rename. See `agenda._agenda_bill_out`.
    """

    id: int
    payee: str
    due_date: str | None
    amount: str | None
    currency: str
    direction: str
    repeats: bool

class MonthBillOut(Schema):
    #: The bill's own id. It was `task_id` for two days after the flip, kept
    #: that way on purpose: the pay, edit and delete routes are all keyed on it,
    #: and renaming server, contract, routes and SPA in the commit that changed
    #: what a bill *is* would have put two failure modes in one place.
    #: Increment 9 of `bill-as-a-model-plan.md` was that rename.
    id: int
    due_date: date
    #: A string, not a float: this column exists to avoid binary rounding
    #: and sending it as a JSON number would put it straight back. Null for a
    #: bill nobody has priced.
    amount: str | None
    currency: str
    payee: str
    #: Whether it is settled. Derived rather than stored -- there is one
    #: definition of paid and the day and the agenda already read it.
    paid: bool
    #: Whether this comes round again. The page needs it to know whether
    #: deleting has one meaning or two: removing August's rent is not the same
    #: act as stopping rent.
    repeats: bool
    #: What kind of thing it is, and null for uncategorised. **Both the name
    #: and the id**, because they serve different readers: the heading groups on
    #: the name and needs no lookup, and the edit form's picker is keyed on the
    #: id. Sending only the name meant the editor opened on *Uncategorised* for
    #: a filed bill and cleared it on save -- caught before it shipped, by the
    #: type checker refusing a body that had lost a required field.
    category: str | None
    category_id: int | None
    #: **The account this bill moves money against**, and null when it names
    #: none. Both the name and the id, for the reason `category` sends both: a
    #: row shows the name and an edit form's picker is keyed on the id.
    #:
    #: *Moves against*, not *paid from*. An outgoing bill against a card
    #: reduces what is owed; an incoming one against an investment increases
    #: what is held. Which current account the money physically left is a
    #: second fact this product does not record, and one field meaning either
    #: would make every reader guess.
    account: str | None
    account_id: int | None
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
    #: A string, for the reason `MonthBillOut.amount` is one, and null for a
    #: bill nobody has priced --
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
    #: The account it pays down or feeds, when it is one. Increment 7 of
    #: bill-as-a-model-plan.md -- the disconnect Vince reported, which is that a
    #: card and the bill that pays it were unrelated records.
    account_id: int | None = None


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
    chosen_account = None
    if payload.account_id is not None:
        chosen_account = Account.objects.filter(
            pk=payload.account_id, owner=request.user
        ).first()
        if chosen_account is None:
            raise HttpError(404, "No such account.")
    try:
        bill = bills.record(
            request.user,
            payee=payload.payee,
            amount=amount,
            currency=payload.currency,
            due_date=payload.due_date,
            repeats=payload.repeats,
            recurrence=payload.recurrence,
            lead_days=payload.lead_days,
            account=chosen_account,
        )
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    # The same builder every other bill response uses. It used to be spelled
    # out here because a freshly created task had no sidecar loaded yet; a
    # `Bill` is one row and there is nothing to reload.
    return 201, _bill_row_out(bill)


class EditBillIn(Schema):
    """Every field optional, and absent is not empty.

    The same partial-write contract the day and the review already have: a field
    left out keeps its stored value. **Clearing an amount is explicit** --
    `amount: null` with `clear_amount: true` -- because "the water bill,
    whatever it comes to" is a state somebody chooses rather than a field they
    forgot to fill in.
    """

    #: **Which bill is meant, when it repeats.** False edits this occurrence
    #: -- August's rent went up. True edits the standing arrangement and every
    #: later unpaid occurrence -- *rent* went up.
    #:
    #: **The delete path's word, not a new one.**
    #: `DELETE .../entry/{id}?whole_series=true` already draws exactly this line,
    #: and one distinction with two names in one module is how a reader starts
    #: guessing. It defaults to the narrow act for the same reason delete does:
    #: the wider answer is the one that is not undone by editing something back.
    #:
    #: **`due_date` ignores it**, deliberately. When a bill falls is the
    #: cadence's answer, not a value to broadcast; and `recurrence` is the
    #: mirror image -- always the rule's, because a cadence on one occurrence is
    #: not a thing.
    whole_series: bool = False
    payee: str | None = None
    amount: str | None = None
    clear_amount: bool = False
    currency: str | None = None
    due_date: date | None = None
    lead_days: int | None = None
    recurrence: str | None = None
    #: The category to file it under. Null is not "leave alone" here -- see
    #: `clear_category`, which is how uncategorised is chosen deliberately.
    category_id: int | None = None
    clear_category: bool = False
    #: The account it moves against, with the same pair for the same reason:
    #: absent means leave it alone, so *no account* has to be said out loud.
    account_id: int | None = None
    clear_account: bool = False


def _bill_row_out(bill):
    """One bill, shaped like a row of the month it belongs to.

    **The record, not a task and its sidecar.** Before August 31, 2026 this
    read two rows and reconciled them, and the month endpoint carried a second
    hand-written copy of the same dict; both are one function over one row now.

    **Three things it no longer has to do**, which is the split paying for
    itself: `paid` reads `paid_at` rather than `completed_at` with a paragraph
    explaining why the status cannot be trusted; `repeats` asks whether there
    is a standing rule rather than inspecting a recurrence enum on the
    occurrence; and there is no `url`, because a bill has no `/api/items/{id}`
    to point at and nothing ever read the field.
    """
    series = bill.series
    return {
        "id": bill.id,
        "due_date": bill.due_date,
        "amount": str(bill.amount) if bill.amount is not None else None,
        "currency": bill.currency,
        "payee": bill.payee,
        "paid": bill.paid,
        # A standing rule that has ended does not still repeat -- otherwise the
        # page offers *stop this bill entirely* for a bill already stopped.
        "repeats": series is not None and series.ended_at is None,
        "category": bill.category.name if bill.category_id else None,
        "category_id": bill.category_id,
        "account": bill.account.name if bill.account_id else None,
        "account_id": bill.account_id,
        "direction": bill.direction,
        "recurrence": (
            series.cadence
            if series is not None and series.ended_at is None
            else Recurrence.NONE
        ),
        "lead_days": bill.lead_days,
        "paid_amount": (
            str(bill.paid_amount) if bill.paid_amount is not None else None
        ),
        "overdue": bill.overdue_on(today_for(bill.owner)),
    }


def _bill_or_404(request, bill_id):
    """The caller's bill, or a refusal. One lookup for five endpoints."""
    bill = (
        Bill.objects.filter(pk=bill_id, owner=request.user)
        .select_related("series", "category", "account")
        .first()
    )
    if bill is None:
        raise HttpError(404, "No such bill.")
    return bill


@router.get(
    "/money/bills/entry/{bill_id}", response=MonthBillOut, auth=SessionAuthIfLoggedIn()
)
def one_bill(request, bill_id: int):
    """One bill, for its own page.

    **The surface moves to Money before the model does.** A bill was opened at
    `/app/tasks/{id}` until August 31, 2026, borrowing the task detail page --
    which spent that morning being taught to call itself *Bill detail*, hide
    Priority, Area and Checklist, and link back here, because none of it was
    true for a bill. `bill-as-a-model-plan.md` makes the borrowing impossible:
    a bill that is not an `Item` has no `/tasks/{id}` to borrow. Moving the
    page first keeps the flip from having to invent one at the same moment it
    changes what a bill is.

    **On the write path's key, not a new one.** `PATCH`, `POST /pay` and
    `DELETE` already live on `entry/{bill_id}`; a read at a second address for
    the same thing is how two spellings of one resource start.

    **A plain task is not found here.** Answering for one would make *is this a
    bill* a question every caller has to ask afterwards, and the page has no
    fields for a task.
    """
    return _bill_row_out(_bill_or_404(request, bill_id))


@router.patch(
    "/money/bills/entry/{bill_id}", response=MonthBillOut, auth=SessionAuthIfLoggedIn()
)
def edit_bill(request, bill_id: int, payload: EditBillIn):
    """Correct a bill without leaving the page it is shown on.

    **`entry/{id}` rather than `{id}`**, because `/money/bills/{day}` already
    takes a date in that position and two routes differing only by the type of
    one segment is a collision waiting for the first numeric-looking date. The
    read keeps the shorter path; the writes take the longer one.

    **Under `/money/` since August 27, 2026.** The resources are still bills --
    a bill is one kind of money thing and income is its sibling on the same
    record, pointed the other way -- so what moved is the namespace, not the
    noun. The model is named `Bill` for exactly that reason: one named after the
    module would have to mean both.
    """
    bill = _bill_or_404(request, bill_id)
    fields = {}
    if payload.payee is not None:
        fields["payee"] = payload.payee
    if payload.currency is not None:
        fields["currency"] = payload.currency
    if payload.due_date is not None:
        fields["due_date"] = payload.due_date
    if payload.lead_days is not None:
        fields["lead_days"] = payload.lead_days
    if payload.clear_category:
        fields["category"] = None
    elif payload.category_id is not None:
        chosen = MoneyCategory.objects.filter(
            pk=payload.category_id, owner=request.user
        ).first()
        if chosen is None:
            raise HttpError(404, "No such category.")
        fields["category"] = chosen
    if payload.clear_account:
        fields["account"] = None
    elif payload.account_id is not None:
        chosen_account = Account.objects.filter(
            pk=payload.account_id, owner=request.user
        ).first()
        if chosen_account is None:
            raise HttpError(404, "No such account.")
        fields["account"] = chosen_account
    if payload.clear_amount:
        fields["clear_amount"] = True
    elif payload.amount not in (None, ""):
        try:
            fields["amount"] = Decimal(payload.amount)
        except InvalidOperation:
            raise HttpError(409, "That amount is not a number.")
    try:
        if payload.whole_series:
            # **The due date stays this occurrence's.** `revise_from` takes no
            # date and it is not an omission: a series has no due date to
            # revise, so a caller sending both is asking for one edit that is
            # narrow and one that is wide, and gets exactly that.
            moved = fields.pop("due_date", None)
            bill = bills.revise_from(bill, **fields)
            if moved is not None:
                bill = bills.update(bill, due_date=moved)
        else:
            bill = bills.update(bill, **fields)
        # **Cadence last, and separately.** It lives on the series, not the
        # occurrence, so changing it is a different act from correcting this
        # month's figure -- see `bills.set_cadence`, which is where that
        # distinction is made rather than smuggled into a field update. It is
        # series-level whichever scope was asked for, because there is no other
        # place a cadence could live.
        if payload.recurrence is not None:
            bill = bills.set_cadence(bill, payload.recurrence)
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    bill.refresh_from_db()
    return _bill_row_out(bill)


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
    #: The account it feeds. **Declared here as well as on `NewBillIn`, and
    #: wired**: this schema's twin declared `recurrence` and `lead_days` for
    #: four days while the endpoint passed neither on, so the form's cadence
    #: picker made monthly bills whatever it said. Every field a schema names
    #: has to reach a service, and a test says so end to end.
    account_id: int | None = None


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
    chosen_account = None
    if payload.account_id is not None:
        chosen_account = Account.objects.filter(
            pk=payload.account_id, owner=request.user
        ).first()
        if chosen_account is None:
            raise HttpError(404, "No such account.")
    try:
        bill = bills.record(
            request.user,
            payee=payload.payer,
            amount=amount,
            currency=payload.currency,
            due_date=payload.due_date,
            repeats=payload.repeats,
            recurrence=payload.recurrence,
            lead_days=payload.lead_days,
            direction=Direction.IN,
            account=chosen_account,
        )
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    return 201, _bill_row_out(bill)


@router.post(
    "/money/bills/entry/{bill_id}/pay", response=MonthBillOut, auth=SessionAuthIfLoggedIn()
)
def pay_bill(request, bill_id: int, payload: PayBillIn):
    """Pay a bill from the page it is shown on.

    **The action this page was missing entirely.** It could add a bill and
    delete a bill and not pay one, which is the thing a person does twelve
    times more often than both put together.
    """
    bill = _bill_or_404(request, bill_id)
    amount = None
    if payload.amount not in (None, ""):
        try:
            amount = Decimal(payload.amount)
        except InvalidOperation:
            raise HttpError(409, "That amount is not a number.")
    try:
        bill = bills.settle(bill, amount=amount)
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    bill.refresh_from_db()
    return _bill_row_out(bill)


@router.delete(
    "/money/bills/entry/{bill_id}", response={204: None}, auth=SessionAuthIfLoggedIn()
)
def remove_bill(request, bill_id: int, whole_series: bool = False):
    """Remove a bill, and say which one is meant when it repeats.

    **`whole_series` as a query parameter** rather than a body: a DELETE with a
    payload is legal and poorly supported, and this is one boolean the caller
    already knows before it asks.

    The default is the narrow act. Deleting August's rent means *not this one*;
    somebody who meant *stop paying rent* has to say so, because the wider
    answer is the one that cannot be undone by adding a bill back.
    """
    bill = _bill_or_404(request, bill_id)
    try:
        bills.remove(bill, whole_series=whole_series)
    except bills.BillConflict as error:
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
    #: **What pays this down, or feeds it.** Null when nothing is filed against
    #: it, which is a real state and gets its own sentence rather than an empty
    #: row -- Vince, August 31, 2026: *"it should be tied to the payments."*
    next_payment: NextPaymentOut | None


class NextPaymentOut(Schema):
    """The soonest unpaid bill against an account.

    **The read half of increment 7**, and the reason `Account.paid_by` is
    allowed back. `d50d6eb` deleted the first version of this link because it
    was *"set by nothing and read by nothing"*; a field with a writer and no
    reader is the same mistake with a longer runway, so the two ship together.

    **Soonest unpaid, not a list.** The balances screen answers *what do I owe
    on this* and *what is coming*; every bill an account has ever had is the
    month page's question and is one click away through `id`.
    """

    #: **`bill_id`, not `id`.** This sits inside an account row that has an `id`
    #: of its own, so a bare one would read as the account's. Everywhere a
    #: schema *is* a bill -- `MonthBillOut`, `AgendaBillOut`, `LandingLineOut`
    #: -- the field is `id`, matching `TaskOut.id` beside `/tasks/{task_id}`.
    bill_id: int
    payee: str
    due_date: date
    amount: str | None
    currency: str


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

    #: The bill's own id -- see `MonthBillOut`, which carries why this was
    #: `task_id` for two days first.
    id: int
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
    #: **Have you ever put anything here.** Every field above reads empty both
    #: for somebody with nothing recorded and for somebody whose month is
    #: simply quiet, and those want opposite pages -- see `money.MoneyLanding`.
    line_count: int
    account_count: int


class CategoryOut(Schema):
    id: int
    name: str
    #: How many money lines carry it. Shown when deleting, so *"3 bills will
    #: become uncategorised"* is a fact rather than a surprise.
    line_count: int


class CategoryIn(Schema):
    name: str


@router.get(
    "/money/categories", response=list[CategoryOut], auth=SessionAuthIfLoggedIn()
)
def money_categories(request):
    """This owner's categories, seeded on the first ask."""
    categories = bills.categories_for(request.user).annotate(
        # `bills`, not `lines`. `lines` was `MoneyLine`'s reverse accessor and
        # went with the model in increment 8; `Bill.category` is `bills`. A
        # string is invisible to a rename, so this 500'd the Categories screen
        # on load and on save until September 2, 2026.
        used=Count("bills")
    )
    return [
        {"id": each.id, "name": each.name, "line_count": each.used}
        for each in categories
    ]


@router.post(
    "/money/categories", response={201: CategoryOut}, auth=SessionAuthIfLoggedIn()
)
def add_money_category(request, payload: CategoryIn):
    try:
        category = bills.add_category(request.user, name=payload.name)
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    return 201, {"id": category.id, "name": category.name, "line_count": 0}


@router.patch(
    "/money/categories/{category_id}",
    response=CategoryOut,
    auth=SessionAuthIfLoggedIn(),
)
def rename_money_category(request, category_id: int, payload: CategoryIn):
    category = MoneyCategory.objects.filter(
        pk=category_id, owner=request.user
    ).first()
    if category is None:
        raise HttpError(404, "No such category.")
    try:
        bills.rename_category(category, payload.name)
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    return {
        "id": category.id,
        "name": category.name,
        "line_count": category.bills.count(),
    }


@router.delete(
    "/money/categories/{category_id}",
    response={204: None},
    auth=SessionAuthIfLoggedIn(),
)
def remove_money_category(request, category_id: int):
    """Remove a label. **The bills keep going** -- `SET_NULL`, so they become
    uncategorised rather than leaving with it."""
    category = MoneyCategory.objects.filter(
        pk=category_id, owner=request.user
    ).first()
    if category is None:
        raise HttpError(404, "No such category.")
    bills.delete_category(category)
    return 204, None


@router.get("/money", response=MoneyLandingOut, auth=SessionAuthIfLoggedIn())
def money_landing(request):
    """How the money stands, today.

    **No date in the path.** Every other read here takes one because it is about
    a month; this one is about *now*, and a landing page addressed by date would
    invite the question of what last Tuesday's dashboard looked like.
    """
    today = today_for(request.user)
    found = money_reader.landing_from_bills(request.user, today=today)

    def line(bill):
        return {
            "id": bill.id,
            "payee": bill.payee,
            "due_date": bill.due_date,
            "amount": str(bill.amount) if bill.amount is not None else None,
            "currency": bill.currency,
            "days": (bill.due_date - today).days,
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
        # **Adding a field to MoneyLandingOut is not enough**, because this
        # dict is hand-built rather than dumped from the dataclass -- and the
        # two disagreeing is a 500, not a missing key. It happened on August
        # 31, 2026 with these exact two fields, past 2009 green Django tests,
        # because every test drove `landing_for` and none made a request.
        #
        # ~~`TheLandingEndpointTest` now does.~~ **It did, for this endpoint,
        # and that was the mistake**: the note and its test both covered the
        # response they were written about. `AccountOut` gained `next_payment`
        # on September 1 and this same defect 500'd account creation, in this
        # same file, with this paragraph already here. **A note is not a
        # control and a test of one endpoint is not a rule.**
        # `test_the_money_endpoints_answer.EveryDeclaredFieldIsSentTest` reads
        # every money schema against what its endpoint actually sends.
        "line_count": found.line_count,
        "account_count": found.account_count,
    }


class ProjectionOut(Schema):
    """Where a balance is heading, with its own derivation attached."""

    #: [[month, figure], ...] oldest first.
    months: list[list[str]]
    monthly_change: str
    #: What it was drawn from. Shown, because a projection whose derivation is
    #: invisible is a claim rather than an estimate.
    readings_used: int
    #: The month a debt reaches zero, when it does. Null for something held.
    clears_on: date | None


class HistoryRowOut(Schema):
    account_id: int
    name: str
    currency: str
    owes: bool
    #: One entry per month in `months`, same order. **Null is a gap, not a
    #: zero**: nothing recorded and nothing owed are different facts.
    balances: list[str | None]
    #: Absent under three readings, deliberately -- two points make a line
    #: through whatever noise those two months contained.
    projection: ProjectionOut | None


class BalanceHistoryOut(Schema):
    months: list[date]
    rows: list[HistoryRowOut]


@router.get(
    "/money/history", response=BalanceHistoryOut, auth=SessionAuthIfLoggedIn()
)
def balance_history(request, months: int = 12):
    """Every account over the last ``months``, and six months of arithmetic."""
    today = today_for(request.user)
    found = money_reader.history_for(request.user, today=today, months=months)
    return {
        "months": found.months,
        "rows": [
            {
                "account_id": row.account.id,
                "name": row.account.name,
                "currency": row.account.currency,
                "owes": row.account.owes,
                "balances": [
                    str(row.balances[each]) if row.balances[each] is not None else None
                    for each in found.months
                ],
                "projection": (
                    {
                        "months": [
                            [when.isoformat(), str(figure)]
                            for when, figure in row.projection.months
                        ],
                        "monthly_change": str(row.projection.monthly_change),
                        "readings_used": row.projection.readings_used,
                        "clears_on": row.projection.clears_on,
                    }
                    if row.projection is not None
                    else None
                ),
            }
            for row in found.rows
        ],
    }


@router.get("/money/accounts/{day}", response=AccountsOut, auth=SessionAuthIfLoggedIn())
def months_accounts(request, day: date):
    """Every account, with the month's figure and the one before it."""
    first = day.replace(day=1)
    previous = (first - timedelta(days=1)).replace(day=1)
    accounts = list(
        # **Closed accounts leave the pass and keep their history**, which is
        # the whole reason closing is not deleting. `close_account`'s deferral
        # was declared with this exact sentence as its trigger: a card somebody
        # stops using stays here forever asking for a figure.
        Account.objects.filter(owner=request.user, closed_at__isnull=True)
        .prefetch_related("readings")
    )
    # **One query for every account, not one each.** This screen lists
    # everything somebody has, so a lookup inside the loop below is the shape
    # that turns eight accounts into eight queries. Ordered by date and taken
    # first-wins, so each account keeps its soonest.
    #
    # Income counts: an investment is fed rather than paid down, and the page
    # words it by direction the way the pay button already does.
    next_payments = {}
    for bill in (
        Bill.objects.filter(
            owner=request.user, paid_at__isnull=True, account__isnull=False
        ).order_by("due_date", "id")
    ):
        next_payments.setdefault(
            bill.account_id,
            {
                "bill_id": bill.id,
                "payee": bill.payee,
                "due_date": bill.due_date,
                "amount": str(bill.amount) if bill.amount is not None else None,
                "currency": bill.currency,
            },
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
                "next_payment": next_payments.get(account.id),
            }
        )
    return {
        "month_start": first,
        "accounts": rows,
        "owed_totals": {code: str(total) for code, total in owed.items()},
        "held_totals": {code: str(total) for code, total in held.items()},
    }


class EditAccountIn(Schema):
    """Rename it, close it, or open it again.

    **Absent is leave alone**, the partial-write contract every other edit on
    this router has. `closed` is a tri-state for that reason: true closes,
    false reopens, and absent means the caller was renaming and had no opinion.
    """

    name: str | None = None
    #: True stops using it -- out of the monthly pass and out of what is owed,
    #: still in the history. False starts again. See `Account.closed_at` for why
    #: closing keeps the readings and deleting does not.
    closed: bool | None = None


def _account_or_404(request, account_id):
    account = Account.objects.filter(pk=account_id, owner=request.user).first()
    if account is None:
        raise HttpError(404, "No such account.")
    return account


@router.patch(
    # **`entry/{id}` rather than `{id}`**, exactly as the bill writes do and for
    # the identical reason: `/money/accounts/{day}` already takes a date in that
    # position, and two routes differing only by the type of one segment is a
    # collision waiting for the first numeric-looking date. It is not waiting --
    # Ninja answered 405 the first time this was tried. The read keeps the
    # shorter path; the writes take the longer one.
    "/money/accounts/entry/{account_id}", response=AccountOut,
    auth=SessionAuthIfLoggedIn(),
)
def edit_account(request, account_id: int, payload: EditAccountIn):
    """Correct an account's name, or stop and start using it."""
    account = _account_or_404(request, account_id)
    try:
        if payload.name is not None:
            account = bills.rename_account(account, payload.name)
        if payload.closed is True:
            account = bills.close_account(account)
        elif payload.closed is False:
            account = bills.reopen_account(account)
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    return _account_out(account)


@router.delete(
    "/money/accounts/entry/{account_id}", response={204: None},
    auth=SessionAuthIfLoggedIn(),
)
def remove_account(request, account_id: int):
    """Delete an account and its readings.

    **The other act, and the destructive one.** Closing says *I stopped using
    this*; this says *this should never have existed*, and takes twelve months
    of readings with it. `Account.closed_at` carries the argument.
    """
    bills.delete_account(_account_or_404(request, account_id))
    return 204, None


def _account_out(account):
    """One account, with no figures: the writes above answer with what they
    changed, and a balance belongs to a month rather than to an edit."""
    return {
        "id": account.id,
        "name": account.name,
        "kind": account.kind,
        "currency": account.currency,
        "owes": account.owes,
        "balance": None,
        "previous": None,
        "next_payment": None,
    }


@router.post("/money/accounts", response={201: AccountOut}, auth=SessionAuthIfLoggedIn())
def add_account(request, payload: NewAccountIn):
    try:
        account = bills.create_account(
            request.user,
            name=payload.name,
            kind=payload.kind,
            currency=payload.currency,
            owes=payload.owes,
        )
    except bills.BillConflict as error:
        raise HttpError(409, str(error))
    return 201, {
        "id": account.id,
        "name": account.name,
        "kind": account.kind,
        "currency": account.currency,
        "owes": account.owes,
        # Null for all three, and none of them is a guess: an account created a
        # moment ago has no reading this month, none last month, and nothing
        # filed against it.
        "balance": None,
        "previous": None,
        # **Added September 2, 2026 after this 500'd in production.**
        # `AccountOut` gained `next_payment` in increment 7 and this dict did
        # not, so Ninja refused the response *after* `create_account` had
        # committed -- the account existed, the caller saw a 500, and retrying
        # answered "you already have one called that".
        "next_payment": None,
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
                bills.record_balance(
                    account,
                    on_date=payload.on_date,
                    amount=Decimal(reading.amount),
                )
            except InvalidOperation:
                raise HttpError(409, f"{account.name}: that is not a number.")
            except bills.BillConflict as error:
                raise HttpError(409, f"{account.name}: {error}")
    return months_accounts(request, payload.on_date)


@router.get("/money/bills/{day}", response=MonthOfBillsOut, auth=SessionAuthIfLoggedIn())
def months_bills(request, day: date):
    """What is due this month and what it comes to.

    Session-only, like the calendar: a new surface the phone does not have,
    and widening the token surface for one it cannot show would be the
    un-switched-on seam this project keeps finding.
    """
    found = money_reader.month_from_bills(request.user, day)
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])
    return {
        "month_start": first,
        "previous_month": (first - timedelta(days=1)).replace(day=1),
        "next_month": last + timedelta(days=1),
        # **`_bill_row_out`, not a second copy of it.** This dict was written
        # out here because the old row was a task *and* a sidecar and the two
        # builders had drifted into differing about `paid`; one record means
        # one builder.
        "bills": [_bill_row_out(row) for row in found.bills],
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
