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
