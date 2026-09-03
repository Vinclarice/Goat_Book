"""What Money contributes to somebody's account export.

**One function, called by `accounts/export.py`.** That module used to import
five money models and build their rows itself, which meant the export knew
Money's tables — so a model added here was a change over there, and the person
who added it would have had no reason to look.

**The export system still owns the promise and the shape.** It decides what an
archive is, what it is called, when it is built and how it is delivered; this
decides what Money has to say. `EXPORT_KEYS` still names every model, because
the completeness guard reads it and that guard is the thing standing between a
new model and somebody's archive quietly missing it.

**Rows, not files.** Returning plain dictionaries keeps this testable without a
zip and keeps Money out of the business of formats.
"""
from money.models import Account, BalanceReading, Bill, BillSeries, MoneyCategory

#: The models this app contributes, and the payload key each travels under.
#: Read by `accounts.export` rather than duplicated there.
EXPORTED = {
    BillSeries: "bill_series",
    Bill: "bill_occurrences",
    # **Named `accounts_with_balances`, not `accounts`.** The archive already
    # has an `account` key for the person's own login details, and two things
    # called account in one payload is how somebody reading their own export
    # learns the wrong thing about it.
    Account: "accounts_with_balances",
    MoneyCategory: "money_categories",
    BalanceReading: "balances",
}


def for_owner(owner, serialize):
    """Every money row belonging to `owner`, keyed as the archive expects.

    `serialize` is passed in rather than imported: turning a model instance into
    JSON-safe values is the export system's rule -- what a date looks like, what
    a decimal looks like -- and there is nothing money-specific about it. Money
    says which rows; the archive says what a row looks like.

    **Balances are reached through their account**, which is the one shape here
    that is not `owner=`: a reading has no owner of its own, and the sidecar
    shape is exactly what goes missing from a list like this.
    """
    return {
        "bill_series": serialize(BillSeries.objects.filter(owner=owner)),
        "bill_occurrences": serialize(Bill.objects.filter(owner=owner)),
        "accounts_with_balances": serialize(Account.objects.filter(owner=owner)),
        "money_categories": serialize(MoneyCategory.objects.filter(owner=owner)),
        "balances": serialize(BalanceReading.objects.filter(account__owner=owner)),
    }
