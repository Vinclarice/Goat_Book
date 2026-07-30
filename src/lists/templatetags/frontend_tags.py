from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html


register = template.Library()


@register.simple_tag
def frontend_assets():
    dev_server_url = settings.VITE_DEV_SERVER_URL.rstrip("/")
    if settings.DEBUG and dev_server_url:
        return format_html(
            '<script type="module" src="{}/@vite/client"></script>'
            '<script type="module" src="{}/src/main.tsx"></script>',
            dev_server_url,
            dev_server_url,
        )

    return format_html(
        '<link rel="stylesheet" href="{}">'
        '<script type="module" src="{}"></script>',
        static("frontend/app.css"),
        static("frontend/app.js"),
    )


@register.simple_tag
def app_shell_assets():
    """Same dev/build split as frontend_assets(), for the router-based
    shell entry. No stylesheet yet -- this bundle has no CSS until Step 3
    gives it something to style.
    """
    dev_server_url = settings.VITE_DEV_SERVER_URL.rstrip("/")
    if settings.DEBUG and dev_server_url:
        return format_html(
            '<script type="module" src="{}/@vite/client"></script>'
            '<script type="module" src="{}/src/app/main.tsx"></script>',
            dev_server_url,
            dev_server_url,
        )

    return format_html(
        '<script type="module" src="{}"></script>',
        static("frontend/app-shell.js"),
    )
