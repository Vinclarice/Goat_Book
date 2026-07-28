from django.core.mail import mail_admins


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
