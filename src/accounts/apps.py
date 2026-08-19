import logging

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.conf import settings
        from django.db.models.signals import post_save
        from django.urls import reverse

        from axes.signals import user_locked_out

        from accounts import emails
        from accounts.emails import notify_admins_of_lockout
        from accounts.models import User

        def _on_user_locked_out(sender, request, username, ip_address, **kwargs):
            notify_admins_of_lockout(username=username, ip_address=ip_address)

        user_locked_out.connect(_on_user_locked_out, dispatch_uid="accounts.notify_admins_of_lockout")

        def _on_user_saved(sender, instance, created, **kwargs):
            """Tell somebody their account is open, once, when it opens.

            **The transition is what matters, not the value.** `is_active` is
            True for the whole rest of an account's life, and `last_login` is
            written on every single sign-in — so a hook that fired on "saved
            and active" would email on every login forever. `User.from_db`
            records what was loaded and this compares against it.

            A signal rather than an admin action because approval is a
            `list_editable` checkbox and a change-form field, and hooking two
            places is how one of them gets forgotten. What no approach catches
            is `queryset.update()`, which bypasses signals entirely; approval
            through the admin does not use it.

            The send is guarded because the admin's tick is the real work and
            it has already committed. Letting a mail failure raise here would
            500 the admin page and, worse, make it look as though the approval
            had not taken.
            """
            was_active = getattr(instance, "_loaded_is_active", None)
            # The instance now matches the row it was written to, whatever
            # happens below. Without this a second save on the *same* object --
            # a view that activates and then updates something else -- would
            # still be carrying the pre-approval value and would send again.
            instance._loaded_is_active = instance.is_active

            if created or not instance.is_active or was_active is not False:
                return

            try:
                # Through the module rather than a name bound at ready(), so
                # the send is reachable to patch. A closure over the function
                # would make this branch untestable, and it is the branch that
                # decides whether a failed email can break an approval.
                emails.send_account_approved(
                    instance,
                    login_url=f"{settings.SITE_URL}{reverse('login')}",
                )
            except Exception:
                logger.exception("account-approved email failed for %s", instance.pk)

        post_save.connect(
            _on_user_saved,
            sender=User,
            dispatch_uid="accounts.send_account_approved",
        )
