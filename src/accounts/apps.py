from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from axes.signals import user_locked_out

        from accounts.emails import notify_admins_of_lockout

        def _on_user_locked_out(sender, request, username, ip_address, **kwargs):
            notify_admins_of_lockout(username=username, ip_address=ip_address)

        user_locked_out.connect(_on_user_locked_out, dispatch_uid="accounts.notify_admins_of_lockout")
