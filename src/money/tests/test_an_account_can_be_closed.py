"""An account somebody stops using, and one they should never have added.

**`close_account` has been dark since the day accounts were built**, with its
deferral declared and this trigger named: *"they can be created and not removed,
so a card somebody stops using stays in the monthly balance pass forever asking
for a figure."* This is the surface that discharges it.

**And discharging it changed what it does.** It was a hard delete, and the
reason its docstring gave — *"an account's existence answers nothing about
whether a practice happened"* — is true of the account row and silent about
what hangs off it. `BalanceReading` cascades, so closing a card you had finally
paid off deleted the twelve months proving you paid it off. That is the one
question the history page exists to answer.

**The precedent is one model away.** Ending a `BillSeries` sets `ended_at` and
keeps what it produced, because *"those rows are a record of money that moved"*.
An account's readings are the same kind of row, so an account gets the same
treatment and `closed_at` is `ended_at` spelled for accounts.

**So there are two acts and they are different, which is the whole point.**
Closing says *I stopped using this*: it leaves the balance pass and keeps its
history. Deleting says *this should never have existed*: it and its readings go.
Rule 6 asks for the deletion decision to be stated rather than for it to be
hard, and this states both.
"""
import datetime
from decimal import Decimal

from django.test import Client, TestCase

from accounts.models import User
from money import reads as money_reader
from money import services as bills
from money.models import Account, AccountKind, BalanceReading

AUGUST = datetime.date(2026, 8, 1)
PASSWORD = "a secure password"


class ClosingAnAccountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.card = bills.create_account(
            self.user, name="Dell Community", kind=AccountKind.CARD
        )
        bills.record_balance(self.card, on_date=AUGUST, amount=Decimal("220.00"))

    def test_closing_keeps_the_account_and_its_readings(self):
        """The correction. A card you finally paid off is exactly the one worth
        keeping the history of."""
        bills.close_account(self.card)

        self.card.refresh_from_db()
        self.assertIsNotNone(self.card.closed_at)
        self.assertEqual(BalanceReading.objects.filter(account=self.card).count(), 1)

    def test_closing_twice_does_not_move_the_date(self):
        """Idempotent, and the date is why: how long something has been closed
        is the only thing this timestamp is for -- the same call
        `pause_project` makes for the same reason."""
        bills.close_account(self.card)
        self.card.refresh_from_db()
        first = self.card.closed_at

        bills.close_account(self.card)

        self.card.refresh_from_db()
        self.assertEqual(self.card.closed_at, first)

    def test_reopening_clears_it(self):
        """`principles.md`: undo has to exist, not merely be conceivable. An act
        with no way back is a durable decision, and stopping using a card is not
        one."""
        bills.close_account(self.card)

        bills.reopen_account(self.card)

        self.card.refresh_from_db()
        self.assertIsNone(self.card.closed_at)

    def test_deleting_is_the_other_act_and_still_takes_everything(self):
        """*This should never have existed* is a real thing to mean, and it is
        not what closing means. Hard, and stated -- rule 6."""
        bills.delete_account(self.card)

        self.assertEqual(Account.objects.count(), 0)
        self.assertEqual(BalanceReading.objects.count(), 0)


class TheBalancePassLeavesClosedAccountsOutTest(TestCase):
    """The trigger, in the words it was declared with: *a card somebody stops
    using stays in the monthly balance pass forever asking for a figure.*"""

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.user)
        self.open_card = bills.create_account(
            self.user, name="Amex", kind=AccountKind.CARD
        )
        self.closed_card = bills.create_account(
            self.user, name="Old Store Card", kind=AccountKind.CARD
        )
        bills.record_balance(
            self.closed_card, on_date=AUGUST, amount=Decimal("400.00")
        )

    def accounts(self):
        return [
            row["name"]
            for row in self.client.get(
                f"/api/v1/money/accounts/{AUGUST.isoformat()}"
            ).json()["accounts"]
        ]

    def test_it_is_asked_for_a_figure_while_open(self):
        self.assertIn("Old Store Card", self.accounts())

    def test_it_stops_being_asked_once_closed(self):
        bills.close_account(self.closed_card)

        self.assertEqual(self.accounts(), ["Amex"])

    def test_it_comes_back_if_reopened(self):
        bills.close_account(self.closed_card)
        bills.reopen_account(self.closed_card)

        self.assertIn("Old Store Card", self.accounts())

    def test_its_history_is_still_there(self):
        """The distinction that makes closing worth having: out of the monthly
        pass, still in the record of what happened."""
        bills.close_account(self.closed_card)

        history = money_reader.history_for(self.user, today=AUGUST)

        self.assertIn("Old Store Card", [row.account.name for row in history.rows])

    def test_a_closed_account_is_not_counted_into_what_is_owed(self):
        """A card closed at zero should not go on saying four hundred is owed;
        the totals are about what is live."""
        bills.record_balance(self.open_card, on_date=AUGUST, amount=Decimal("100.00"))
        bills.close_account(self.closed_card)

        landing = money_reader.landing_from_bills(self.user, today=AUGUST)

        self.assertEqual(landing.owed_totals, {"USD": Decimal("100.00")})


class RenamingAnAccountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.card = bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)

    def test_it_takes_the_new_name(self):
        bills.rename_account(self.card, "American Express")

        self.card.refresh_from_db()
        self.assertEqual(self.card.name, "American Express")

    def test_a_blank_name_is_refused(self):
        with self.assertRaises(bills.BillConflict):
            bills.rename_account(self.card, "   ")

    def test_a_name_already_used_is_refused_in_words(self):
        """`unique_account_name_per_owner` would raise an IntegrityError, which
        is not a sentence anybody can act on."""
        bills.create_account(self.user, name="Barclays", kind=AccountKind.SAVINGS)

        with self.assertRaises(bills.BillConflict) as caught:
            bills.rename_account(self.card, "Barclays")

        self.assertIn("Barclays", str(caught.exception))

    def test_renaming_to_its_own_name_is_allowed(self):
        """Saving a form without changing the name is not a collision, and
        making somebody think about that is the product being difficult."""
        bills.rename_account(self.card, "Amex")

        self.card.refresh_from_db()
        self.assertEqual(self.card.name, "Amex")

    def test_a_closed_account_still_holds_its_name(self):
        """Deliberate: the constraint does not know about closing, and two
        accounts called Amex in one history is exactly the confusion the
        constraint exists to prevent."""
        bills.close_account(self.card)

        with self.assertRaises(bills.BillConflict):
            bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)


class TheAccountEndpointsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.user)
        self.card = bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)

    def patch(self, **body):
        return self.client.patch(
            f"/api/v1/money/accounts/entry/{self.card.id}",
            data=body, content_type="application/json",
        )

    def test_it_renames(self):
        response = self.patch(name="American Express")

        self.assertEqual(response.status_code, 200)
        self.card.refresh_from_db()
        self.assertEqual(self.card.name, "American Express")

    def test_it_closes_and_reopens(self):
        self.assertEqual(self.patch(closed=True).status_code, 200)
        self.card.refresh_from_db()
        self.assertIsNotNone(self.card.closed_at)

        self.assertEqual(self.patch(closed=False).status_code, 200)
        self.card.refresh_from_db()
        self.assertIsNone(self.card.closed_at)

    def test_a_duplicate_name_is_a_409_with_a_sentence(self):
        bills.create_account(self.user, name="Barclays", kind=AccountKind.SAVINGS)

        response = self.patch(name="Barclays")

        self.assertEqual(response.status_code, 409)
        self.assertIn("Barclays", response.json()["detail"])

    def test_it_deletes(self):
        response = self.client.delete(f"/api/v1/money/accounts/entry/{self.card.id}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Account.objects.count(), 0)

    def test_another_person_s_account_is_not_found(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = bills.create_account(bob, name="Theirs", kind=AccountKind.CARD)

        self.assertEqual(
            self.client.patch(
                f"/api/v1/money/accounts/entry/{theirs.id}",
                data={"name": "Mine"}, content_type="application/json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/money/accounts/entry/{theirs.id}").status_code, 404
        )
