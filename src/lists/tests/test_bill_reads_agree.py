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
            # **Missed on the first writing of this helper**, and the renewal
            # test below caught it -- which is the risk of a second copy of
            # `0055` behaving itself. In the migrations it is `0056`'s backfill
            # that carries this over, because the column did not exist when
            # `0055` was written.
            lead_days=item.lead_days,
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


class BothLandingReadsAgreeTest(TestCase):
    """The second and last read the split touches.

    Balances, history and categories read `Account`, `BalanceReading` and
    `MoneyCategory`, which the split does not touch -- so with the month read
    above, this is the whole surface increment 4 has to switch.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def compare(self, today=AUGUST):
        convert(self.user)
        old = money_reader.landing_for(self.user, today=today)
        new = money_reader.landing_from_bills(self.user, today=today)
        return (
            {
                "overdue": [row.bill.payee for row in old.overdue],
                "due_soon": [row.bill.payee for row in old.due_soon],
                "renewing": [row.bill.payee for row in old.renewing_soon],
                "yearly": old.yearly_totals,
                "line_count": old.line_count,
            },
            {
                "overdue": [row.payee for row in new.overdue],
                "due_soon": [row.payee for row in new.due_soon],
                "renewing": [row.payee for row in new.renewing_soon],
                "yearly": new.yearly_totals,
                "line_count": new.line_count,
            },
        )

    def test_overdue_reaches_back_through_every_month_in_both(self):
        services.create_bill(
            self.user,
            payee="Old subscription",
            amount=Decimal("9.00"),
            due_date=datetime.date(2026, 6, 3),
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["overdue"], ["Old subscription"])

    def test_due_soon_crosses_a_month_boundary_in_both(self):
        services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 9, 1),
        )

        old, new = self.compare(today=datetime.date(2026, 8, 25))

        self.assertEqual(old, new)
        self.assertEqual(new["due_soon"], ["Landlord"])

    def test_a_renewal_inside_its_lead_time_appears_in_both(self):
        """**The case that found `Bill.lead_days` missing.** `renewing_soon`
        needs a lead time per bill, and increment 1 put one only on the series
        -- so a one-off with a lead time had nowhere to keep it."""
        services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("240.00"),
            due_date=datetime.date(2026, 9, 20),
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        old, new = self.compare(today=datetime.date(2026, 8, 25))

        self.assertEqual(old, new)
        self.assertEqual(new["renewing"], ["Adobe"])

    def test_the_yearly_cost_matches_in_both(self):
        services.create_bill(
            self.user,
            payee="Netflix",
            amount=Decimal("10.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.MONTHLY,
        )
        services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("240.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.ANNUAL,
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["yearly"], {"USD": Decimal("360.00")})

    def test_a_one_off_is_not_an_annual_cost_in_either(self):
        services.create_bill(
            self.user,
            payee="Plumber",
            amount=Decimal("300.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.NONE,
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["yearly"], {})

    def test_income_stays_out_of_the_landing_read_in_both(self):
        """The landing page is about what is owed; a salary is not."""
        services.create_income(
            self.user, payer="Work", amount=Decimal("3000.00"), due_date=AUGUST
        )

        old, new = self.compare()

        self.assertEqual(old, new)
        self.assertEqual(new["overdue"], [])
        self.assertEqual(new["yearly"], {})


class TheAgendaSourceAgreesTest(TestCase):
    """`open_bills_for` selects what `agenda.open_items_for` selects, for bills.

    **The read decision 4 is bought with.** Vince's call, August 31, 2026: bills
    stay on the day and the agenda rather than being dropped as a side effect of
    the model split. Every read that queries `Item` gains a second source, and
    this is the proof that the second source picks the same rows.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def bill_payees_from_the_agenda(self):
        from lists import agenda as agenda_reader

        return sorted(
            item.money_line.payee
            for item in agenda_reader.open_items_for(self.user)
            if hasattr(item, "money_line")
        )

    def new_payees(self):
        convert(self.user)
        return sorted(row.payee for row in money_reader.open_bills_for(self.user))

    def test_an_outstanding_bill_is_selected_by_both(self):
        services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 1),
        )

        self.assertEqual(self.bill_payees_from_the_agenda(), ["Landlord"])
        self.assertEqual(self.new_payees(), ["Landlord"])

    def test_a_paid_bill_is_selected_by_neither(self):
        bill = services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )
        services.pay_bill(bill)

        old = self.bill_payees_from_the_agenda()
        new = self.new_payees()

        # The successor the payment spawned is outstanding and appears in both.
        self.assertEqual(old, new)

    def test_income_is_excluded_by_both(self):
        """A salary is not something to do on a Tuesday, and it landing in the
        agenda would make the list a ledger."""
        services.create_income(
            self.user,
            payer="Work",
            amount=Decimal("3000.00"),
            due_date=datetime.date(2026, 8, 28),
        )

        self.assertEqual(self.bill_payees_from_the_agenda(), [])
        self.assertEqual(self.new_payees(), [])

    def test_one_persons_bills_are_their_own_in_both(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        services.create_bill(
            other, payee="Theirs", amount=Decimal("9.00"), due_date=AUGUST
        )
        services.create_bill(
            self.user, payee="Mine", amount=Decimal("9.00"), due_date=AUGUST
        )

        self.assertEqual(self.bill_payees_from_the_agenda(), ["Mine"])
        self.assertEqual(self.new_payees(), ["Mine"])


class BillsStayOnTheAgendaTest(TestCase):
    """Decision 4, asserted rather than intended.

    `money-module-plan.md`: *bills stay ordinary tasks elsewhere -- day,
    agenda, lists. Paying is a real thing to do on a day, and the day is where
    it gets noticed.* The model split would drop them from every read that
    queries `Item`, so they move to an array of their own **on the same
    screen** rather than off it.

    **What these guard is the move, not the array.** A bill that left `items`
    and did not arrive in `bills` is decision 4 dying quietly, which is the
    exact failure this plan's §5 exists to prevent.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.user)

    def agenda(self):
        return self.client.get("/api/v1/agenda").json()

    def test_a_bill_is_on_the_agenda_and_only_once(self):
        services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 1),
        )

        body = self.agenda()

        self.assertEqual([b["payee"] for b in body["bills"]], ["Landlord"])
        self.assertEqual(
            [i["text"] for i in body["items"]],
            [],
            "It left `items` rather than appearing in both.",
        )

    def test_a_task_is_untouched_by_any_of_this(self):
        services.create_item(services.create_area(self.user, "Home"), "Call the vet")

        body = self.agenda()

        self.assertEqual([i["text"] for i in body["items"]], ["Call the vet"])
        self.assertEqual(body["bills"], [])

    def test_a_bill_carries_what_the_row_needs_and_nothing_of_a_task(self):
        services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )

        row = self.agenda()["bills"][0]

        self.assertEqual(row["amount"], "64.99")
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["direction"], "out")
        self.assertTrue(row["repeats"])
        self.assertNotIn("tags", row)
        self.assertNotIn("area_id", row)

    def test_income_is_on_neither(self):
        """A salary is not something to do on a Tuesday, and it landing here
        would make the agenda a ledger. Excluded from `items` before this
        change and from `bills` after it."""
        services.create_income(
            self.user,
            payer="Work",
            amount=Decimal("3000.00"),
            due_date=datetime.date(2026, 8, 28),
        )

        body = self.agenda()

        self.assertEqual(body["bills"], [])
        self.assertEqual(body["items"], [])

    def test_a_paid_bill_is_on_neither(self):
        bill = services.create_bill(
            self.user,
            payee="Comcast",
            amount=Decimal("64.99"),
            due_date=datetime.date(2026, 8, 22),
        )
        services.pay_bill(bill)

        payees = [b["payee"] for b in self.agenda()["bills"]]

        self.assertEqual(
            payees, ["Comcast"], "The successor it spawned, which is still owed."
        )

    def test_the_daily_email_still_mentions_bills(self):
        """`digest_items_for` keeps them inline, because its format has one
        kind of row and nothing to merge into -- which is why
        `open_items_for` takes a flag rather than dropping them for everybody.
        """
        from lists import agenda as agenda_reader

        services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 1),
        )

        digest = agenda_reader.digest_items_for(
            self.user, datetime.date(2026, 8, 1)
        )

        self.assertIn("Pay Landlord", [item.text for item in digest])
