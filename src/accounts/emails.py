from django.conf import settings
from django.core.mail import EmailMessage, mail_admins


# Fixed, and deliberately not built from anything the visitor typed. A
# subject naming the sender would be more useful in the inbox and would put
# user input into a header; the name is one line down, in the body, where a
# newline is just a newline.
CONTACT_SUBJECT = "Clarice contact form message"


def send_support_message(*, name, email, message):
    """One message to the support inbox, replyable straight back to the
    visitor.

    From is Clarice's own address, never the visitor's: sending as them
    would forge a From on a domain Clarice doesn't own, which Resend
    refuses outright and which would fail SPF and DMARC at the recipient
    if it didn't.
    """
    EmailMessage(
        subject=CONTACT_SUBJECT,
        body=f"From: {name} <{email}>\n\n{message}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.SUPPORT_EMAIL],
        reply_to=[email],
    ).send()


def notify_admins_of_pending_signup(user):
    mail_admins(
        subject=f"New Clarice signup pending approval: {user.username}",
        message=(
            f"{user.username} ({user.email}) just signed up and is waiting "
            "for approval.\n\n"
            "Approve them from /admin/ by opening their account and "
            "ticking \"Active\"."
        ),
    )


def confirm_deletion_scheduled(user, *, purge_at):
    """Tell somebody their account is on its way out.

    **To the person, not the admins**, and this is the point of it. The password
    re-entry on the form stops a passer-by at an unlocked screen; it does not
    help if somebody has the password. This is what makes the thirty-day window
    a real protection rather than one that only works if you happen to log in
    and read a banner.

    Sent whether or not they asked for it, for the same reason a bank writes to
    you when the address on an account changes: the message is most valuable
    exactly when the recipient did not do the thing.
    """
    EmailMessage(
        subject="Your Clarice account is scheduled for deletion",
        body=(
            f"Hello {user.username},\n\n"
            f"Your Clarice account is scheduled to be deleted permanently on "
            f"{purge_at:%d %B %Y}.\n\n"
            "Everything goes: every task, note, routine, review and the record "
            "of them. It cannot be undone afterwards.\n\n"
            "Until that date nothing has been touched. If you want to keep the "
            "account, sign in and choose \"Keep my account\" on your "
            "preferences page.\n\n"
            "**If you did not ask for this, sign in and cancel it now, then "
            "change your password.**\n\n"
            "You can download everything in the account from that same page, "
            "and it is worth doing before the date above — afterwards there is "
            "nothing left to download.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    ).send()


def confirm_deletion_cancelled(user):
    """The bookend. Somebody who cancels should get the same reassurance in the
    same place they got the warning, rather than having to trust a page."""
    EmailMessage(
        subject="Your Clarice account is no longer scheduled for deletion",
        body=(
            f"Hello {user.username},\n\n"
            "The deletion of your Clarice account has been cancelled. Nothing "
            "was removed, and the account carries on as before.\n\n"
            "If you did not do this, sign in and change your password.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    ).send()


def confirm_account_erased(*, username, email):
    """The receipt, sent immediately before the rows go.

    Takes the address as an argument rather than a user, deliberately: by the
    time this could read one there is no row to read it from, and a receipt that
    depends on the record it is confirming the destruction of is a receipt that
    will not send.
    """
    EmailMessage(
        subject="Your Clarice account has been deleted",
        body=(
            f"Hello {username},\n\n"
            "Your Clarice account and everything in it have now been deleted. "
            "This is the last message you will receive from us, and there is "
            "nothing left to recover.\n\n"
            "Thank you for using it.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    ).send()


def notify_admins_of_lockout(*, username, ip_address):
    mail_admins(
        subject="Clarice account locked out after repeated failed logins",
        message=(
            f"The account {username!r} was locked out after too many "
            f"failed sign-in attempts from {ip_address}.\n\n"
            "This resolves itself automatically after the cooloff period "
            "(see AXES_COOLOFF_TIME in settings.py)."
        ),
    )
