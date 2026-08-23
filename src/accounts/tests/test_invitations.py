"""Approval that is not a person — **S1's last require**.

> Sam follows a link, reads what Clarice is, makes an account, and is doing
> something real before he decides whether to stay.

**Done means:** he reaches a usable workspace **without waiting for a human**,
the first screen offers one obvious thing to do rather than six concepts, and
within four minutes he has captured a thought and planned a day.

Three of the four requires shipped in August. The fourth stayed open and was
named exactly: *"`is_active` is still approval and approval is still a person.
Vince's call."*

**Answered August 23, 2026: invitation links.** Vince mints one, whoever holds
it signs up, and the account works immediately. The approval happened when the
link was made — so there is a person in the story and **no person in the
loop**, which is what the done-means asks.

**Not public self-service, which was the other way to close it.** That is what
the story literally describes and it is five lines of code; it is refused
because the posture answered on August 20 is *personal tool with an intent to
invite*.

**One reason given for that was wrong and is worth recording.** The
recommendation also said terms and a privacy policy were unwritten; both have
been live at `/terms/` and `/privacy/` for some time, and the claim came from a
stale line in `CLAUDE.md` — the exact failure that file warns about two
paragraphs above the stale line. The decision stands on the posture alone.

**`is_active` and `email_confirmed_at` come apart here, and that separation was
built for exactly this.** S1's entry said so a week early: *"`email_confirmed_at`
now carries confirmation so the two facts are separable, which is what makes
closing this later a change of policy rather than of design."* An invited
account is active at once — Vince vouched for the address — and the confirmation
mail still goes, still stamps `email_confirmed_at`. **Four minutes does not
include a round trip to an inbox.**

**A stored model rather than a signed token, unlike `activation_token`.** That
one is stateless because *"a token whose whole existence is 'this URL is valid
until it is used' has no life cycle at all."* An invitation does: minted, held,
redeemed or expired, and worth listing — *who have I invited, and did they come?*
is a question only a table can answer. `architecture-trajectory.md` §4's test,
passed rather than assumed.
"""

import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Invitation, User


class MintingAnInvitationTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password", is_staff=True
        )

    def test_an_invitation_knows_who_made_it(self):
        invitation = Invitation.objects.create(created_by=self.vince)

        self.assertEqual(invitation.created_by, self.vince)

    def test_it_expires(self):
        """A bearer link that never expires is a credential sitting in an inbox
        forever. The window is the whole protection, since the link is the only
        thing needed to use it."""
        invitation = Invitation.objects.create(created_by=self.vince)

        self.assertGreater(invitation.expires_at, timezone.now())

    def test_it_carries_a_note_about_who_it_is_for(self):
        """Not an address, deliberately: binding the invite to one email means
        a typo kills it and a forward is refused, and Vince already chooses who
        to send it to. The note is so *he* can tell two open invitations apart
        a fortnight later."""
        invitation = Invitation.objects.create(created_by=self.vince, note="Priya")

        self.assertEqual(invitation.note, "Priya")

    def test_its_url_can_be_shown_again(self):
        """**A UUID rather than a hashed secret**, so the link is re-displayable
        for as long as the invitation is live. A hash would mean one chance to
        copy it, and a lost link would be an invitation nobody can use and
        nobody can see is dead."""
        invitation = Invitation.objects.create(created_by=self.vince)

        self.assertIn(str(invitation.public_id), invitation.path)


class UsableTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.invitation = Invitation.objects.create(created_by=self.vince)

    def test_a_fresh_invitation_is_usable(self):
        self.assertTrue(self.invitation.is_usable)

    def test_a_redeemed_one_is_not(self):
        """Single use. A forwarded copy after somebody has joined must not be a
        second way in."""
        self.invitation.redeemed_at = timezone.now()

        self.assertFalse(self.invitation.is_usable)

    def test_an_expired_one_is_not(self):
        self.invitation.expires_at = timezone.now() - timedelta(days=1)

        self.assertFalse(self.invitation.is_usable)

    def test_a_revoked_one_is_not(self):
        """Sent to the wrong address, or to somebody who then said no. Revoking
        keeps the row — *who have I invited* stays answerable — where deleting
        it would quietly make the question unanswerable."""
        self.invitation.revoked_at = timezone.now()

        self.assertFalse(self.invitation.is_usable)


class JoiningTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.invitation = Invitation.objects.create(created_by=self.vince, note="Priya")

    @property
    def url(self):
        return reverse("join", kwargs={"public_id": self.invitation.public_id})

    def join(self, **overrides):
        payload = {
            "username": "priya",
            "email": "priya@example.com",
            "password1": "a rather secure password",
            "password2": "a rather secure password",
        }
        payload.update(overrides)
        return self.client.post(self.url, payload)

    def test_the_page_is_reachable_with_a_live_invitation(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_joining_creates_an_account_that_works_immediately(self):
        """**The whole of S1's last require.** No queue, no admin, no waiting."""
        self.join()

        priya = User.objects.get(username="priya")
        self.assertTrue(priya.is_active)

    def test_he_is_signed_in_and_lands_somewhere_usable(self):
        """*Within four minutes he has captured a thought and planned a day* —
        which is not possible from a "check your email" page."""
        response = self.join()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]),
                         User.objects.get(username="priya").pk)

    def test_the_address_is_still_unconfirmed_and_still_asked_about(self):
        """**`is_active` and `email_confirmed_at` come apart, and that is the
        point.** Vince vouched for the person, which is what `is_active`
        records; nobody has yet proved the address receives mail, which is what
        `email_confirmed_at` records, and the digest and password reset both
        depend on it. So the account works now and the mail still goes."""
        from django.core import mail

        self.join()

        priya = User.objects.get(username="priya")
        self.assertIsNone(priya.email_confirmed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("priya@example.com", mail.outbox[0].to)

    def test_the_invitation_records_who_used_it(self):
        self.join()

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.redeemed_by.username, "priya")
        self.assertIsNotNone(self.invitation.redeemed_at)

    def test_it_cannot_be_used_twice(self):
        self.join()

        self.join(username="somebody-else", email="else@example.com")

        self.assertFalse(User.objects.filter(username="somebody-else").exists())

    def test_an_expired_invitation_refuses(self):
        Invitation.objects.filter(pk=self.invitation.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )

        self.join()

        self.assertFalse(User.objects.filter(username="priya").exists())

    def test_an_unknown_invitation_refuses(self):
        response = self.client.get(
            reverse("join", kwargs={"public_id": "11111111-1111-1111-1111-111111111111"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("no longer", response.content.decode().lower())

    def test_every_dead_invitation_reads_the_same(self):
        """Expired, used, revoked and never-existed are four things to us and
        one thing to whoever is holding the link: *ask for another*. The
        `activate` view makes the same choice for the same reason, and here it
        also avoids telling the holder of a forwarded link whether somebody
        else got there first."""
        # Per-response randomness stripped: `base.html` carries a log-out
        # form with a CSRF token and the CSP middleware stamps a fresh nonce on
        # every script tag. Comparing raw HTML would compare those rather than
        # the page.
        def as_read(html):
            html = re.sub(r'value="[A-Za-z0-9_\-]{32,}"', 'value="..."', html)
            html = re.sub(r'nonce="[^"]+"', 'nonce="..."', html)
            # And the id itself, which `og:url` echoes back. That one is the
            # reader's own address bar and tells them nothing they did not
            # already type.
            return re.sub(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                "...",
                html,
            )

        pages = []
        for state in ({"redeemed_at": timezone.now()},
                      {"expires_at": timezone.now() - timedelta(days=1)},
                      {"revoked_at": timezone.now()}):
            Invitation.objects.filter(pk=self.invitation.pk).update(
                redeemed_at=None, revoked_at=None,
                expires_at=timezone.now() + timedelta(days=14),
            )
            Invitation.objects.filter(pk=self.invitation.pk).update(**state)
            pages.append(as_read(self.client.get(self.url).content.decode()))

        unknown = as_read(
            self.client.get(
                reverse(
                    "join",
                    kwargs={"public_id": "11111111-1111-1111-1111-111111111111"},
                )
            ).content.decode()
        )

        self.assertEqual(len(set(pages + [unknown])), 1)

    def test_an_invitation_does_not_let_somebody_take_an_existing_username(self):
        self.join(username="vince")

        self.assertEqual(User.objects.filter(username="vince").count(), 1)

    def test_somebody_already_signed_in_is_not_offered_it(self):
        self.client.force_login(self.vince)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)


class ThePublicFormIsUnchangedTest(TestCase):
    """**Public signup still queues, and that is the policy rather than an
    oversight.**

    S1 is closed on the invited path — which is the path its own sentence
    describes, *Sam follows a link*. Anyone arriving at `/accounts/signup/`
    without one still lands in a queue, because opening that door needs terms
    and a privacy policy that do not exist yet.
    """

    def test_signing_up_without_an_invitation_still_waits(self):
        self.client.post(
            reverse("signup"),
            {
                "username": "stranger",
                "email": "stranger@example.com",
                "password1": "a rather secure password",
                "password2": "a rather secure password",
            },
        )

        self.assertFalse(User.objects.get(username="stranger").is_active)


class ThereIsSomewhereToMintOneTest(TestCase):
    """**A slice is not closed while nothing calls it.**

    `principles.md`, written after three seams turned up switched off in two
    days. A model with no surface would be the fourth, and this one would be
    invisible in the worst way: the feature would look shipped and no
    invitation would ever exist.
    """

    def setUp(self):
        self.vince = User.objects.create_superuser(
            "vince", "vince@example.com", "a secure password"
        )
        self.client.force_login(self.vince)

    def test_invitations_are_in_the_admin(self):
        response = self.client.get("/admin/accounts/invitation/")

        self.assertEqual(response.status_code, 200)

    def test_the_page_for_one_shows_a_link_that_can_be_copied(self):
        invitation = Invitation.objects.create(created_by=self.vince, note="Priya")

        body = self.client.get(
            f"/admin/accounts/invitation/{invitation.pk}/change/"
        ).content.decode()

        self.assertIn(str(invitation.public_id), body)

    def test_revoking_keeps_the_row(self):
        """*Who have I invited* stays answerable. Deleting would make the
        question the model exists for quietly unanswerable."""
        invitation = Invitation.objects.create(created_by=self.vince)

        self.client.post(
            "/admin/accounts/invitation/",
            {"action": "revoke", "_selected_action": [str(invitation.pk)]},
        )

        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.revoked_at)
        self.assertFalse(invitation.is_usable)
