"""The old money read and the new one give the same answers.

Increment 3 of `design/bill-as-a-model-plan.md`. `bills_for` reads
`MoneyLine` + `Item`; `month_from_bills` reads `Bill`. Both are live in the
codebase and only the first is called, which makes this file the whole point of
the increment: **it is what lets increment 4 switch the surfaces over without
guessing.**

**Every test here builds data the old way and converts it**, using the same
mapping `0055_copy_money_lines_into_bills` uses, so what is compared is a real
conversion rather than two hand-built fixtures that agree because one person
wrote both.

**When increment 4 lands, this file goes with it.** Two reads agreeing is worth
testing while both exist and is meaningless afterwards, and a comparison test
kept past its subject is how a suite grows things nobody can delete.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import money as money_reader, services
from lists.models import Bill, BillSeries, Direction, Item, MoneyLine

AUGUST = datetime.date(2026, 8, 15)


def convert(owner):
    """The migration's mapping, applied to live models.

    **A second copy of `0055`'s logic, and deliberately so.** A migration must
    freeze against historical models and cannot import a service, so the two
    cannot share code. What they can share is a test that they agree, which is
    what the conversion tests and this file are between them.
    """
    for line in MoneyLine.objects.select_related("item", "item__commitment").filter(
        item__owner=owner
    ):
        item = line.item
        series = None
        if item.commitment is not None:
            series, _ = BillSeries.objects.get_or_create(
                owner=owner,
                payee=line.payee,
                defaults={
                    "amount": line.amount,
                    "currency": line.currency,
                    "direction": line.direction,
                    "category": line.category,
                    "cadence": item.commitment.cadence,
                    "cadence_mode": item.commitment.cadence_mode,
                    "lead_days": item.lead_days,
                },
            )
        Bill.objects.create(
            owner=owner,
            series=series,
            due_date=item.due_date,
            payee=line.payee,
            amount=line.amount,
            currency=line.currency,
            direction=line.direction,
            category=line.category,
            paid_amount=line.paid_amount,
            paid_at=item.completed_at,
            notes=item.notes,
        )


class BothMonthReadsAgreeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def compare(self):
        """Both reads, over the same month, as comparable answers.

        Totals and counts rather than objects: the rows are different types by
        design, and what has to match is what a person sees.
        """
        convert(self.user)
        old = money_reader.bills_for(self.user, AUGUST)
        new = money_reader.month_from_bills(self.user, AUGUST)
        return (
            {
                "due": old.due_totals,
                "paid": old.paid_totals,
                "expected_in": old.expected_in_totals,
                "received": old.received_totals,
                "unpriced": old.unpriced,
                "payees": [row.bill.payee for row in old.bills],
                "settled": [row.paid for row in old.bills],
            },
            {
                "due": new.due_totals,
                "paid": new.paid_totals,
                "expected_in": new.expected_in_totals,
                "received": new.received_totals,
                "unpriced": new.unpriced,
                "payees": [row.payee for row in new.bills],
                "settled": [row.paid_at is not None for row in new.bills],
            },
        )

    def test_an_ordinary_month_of_outstanding_bills(self):
        services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 1),
        )
        services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["due"], {"USD": Decimal("1264.99")})

    def test_a_paid_bill_lands_in_the_same_bucket_either_way(self):
        bill = services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )
        services.pay_bill(bill, amount=Decimal("71.40"))

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["paid"], {"USD": Decimal("71.40")})

    def test_an_unpriced_bill_is_counted_and_not_totalled_by_both(self):
        services.create_bill(
            self.user, payee="Water", amount=None, due_date=datetime.date(2026, 8, 9)
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["unpriced"], 1)
        self.assertEqual(new["due"], {})

    def test_income_stays_out_of_the_still_to_pay_column_in_both(self):
        """The four-bucket rule: a salary counted as owed makes every month
        look catastrophic."""
        services.create_income(
            self.user,
            payer="Work",
            amount=Decimal("3000.00"),
            due_date=datetime.date(2026, 8, 28),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["expected_in"], {"USD": Decimal("3000.00")})
        self.assertEqual(new["due"], {})

    def test_two_currencies_stay_apart_in_both(self):
        services.create_bill(
            self.user,
            payee="Gandi",
            amount=Decimal("40.00"),
            currency="GBP",
            due_date=datetime.date(2026, 8, 28),
        )
        services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(
            new["due"], {"GBP": Decimal("40.00"), "USD": Decimal("64.99")}
        )

    def test_a_bill_in_another_month_is_absent_from_both(self):
        services.create_bill(
            self.user,
            payee="September",
            amount=Decimal("10.00"),
            due_date=datetime.date(2026, 9, 3),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["payees"], [])

    def test_one_persons_month_is_their_own_in_both(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        services.create_bill(
            other,
            payee="Theirs",
            amount=Decimal("99.00"),
            due_date=datetime.date(2026, 8, 4),
        )
        services.create_bill(
            self.user,
            payee="Mine",
            amount=Decimal("10.00"),
            due_date=datetime.date(2026, 8, 4),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["payees"], ["Mine"])

    def test_a_paid_recurring_bill_is_settled_in_both(self):
        """**The case the old read needs a paragraph for.** Completing a
        recurring task archives it rather than completing it, so `BillRow.paid`
        must read `completed_at` and never the status -- and reading the status
        would have hidden every paid rent. `paid_at` carries no such trap, and
        this test is the two agreeing about it.
        """
        rent = services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 1),
            recurrence=Item.Recurrence.MONTHLY,
        )
        services.pay_bill(rent)
        rent.refresh_from_db()
        self.assertEqual(
            rent.status, Item.Status.ARCHIVED, "The precondition this is about."
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["settled"], [True])
        self.assertEqual(new["paid"], {"USD": Decimal("1200.00")})
