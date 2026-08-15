import json

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = template.Library()

# Blocking, runs before the stylesheet loads so there's no flash of the
# wrong theme. SERVER_THEME is the authenticated user's persisted
# preference (User.theme, via /api/v1/me/preferences) when the caller has
# one; localStorage is the fallback for anonymous pages (login, signup)
# and stays in sync with whatever SERVER_THEME says, so a stale value from
# a previous account/device doesn't linger across a login/logout.
_THEME_RESOLUTION_SCRIPT_TEMPLATE = """
<script nonce="__NONCE__">
(function () {
  var STORAGE_KEY = "clarice-theme";
  var COOKIE_NAME = "clarice_theme";
  var SERVER_THEME = __SERVER_THEME__;

  function resolve(saved) {
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.cookie = COOKIE_NAME + "=" + theme + "; path=/; max-age=31536000; samesite=lax";
  }

  var saved = SERVER_THEME !== null ? SERVER_THEME : localStorage.getItem(STORAGE_KEY);
  if (SERVER_THEME !== null) {
    if (SERVER_THEME === "system") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, SERVER_THEME);
    }
  }

  apply(resolve(saved));

  if (!saved || saved === "system") {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (event) {
      apply(event.matches ? "dark" : "light");
    });
  }
})();
</script>
""".strip()


@register.filter(name="add_class")
def add_class(field, css_class):
    """Adds a class to a bound form field's rendered widget.

    Django's default {{ field }} rendering carries no styling hook, and
    there's no django-widget-tweaks dependency in this project -- this
    is the same as_widget(attrs=...) mechanism that package wraps, used
    directly so auth-page templates can apply Tailwind classes without
    every form needing its own widget attrs defined in forms.py.
    """
    return field.as_widget(attrs={"class": css_class})


@register.simple_tag
def app_shell_assets():
    """Same dev/build split as frontend_assets(), for the router-based
    shell entry's JS. Token styling is separate -- see token_styles()
    below, shared with the Django-rendered token pages.

    Also links app.css: reused components (AgendaWorkspace, TaskWorkspace)
    still use their original CSS-module styles, compiled into that file
    alongside the legacy per-page bundle's. In dev mode this isn't needed
    -- Vite's dev server injects CSS-module styles itself as the importing
    JS module loads.
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
        '<link rel="stylesheet" href="{}">'
        '<script type="module" src="{}"></script>',
        static("frontend/app.css"),
        static("frontend/app-shell.js"),
    )


@register.simple_tag
def token_styles():
    """The Tailwind-compiled token stylesheet (frontend/src/app/tailwind.css),
    shared by base.html and app_shell.html -- one compiled artifact, not a
    separate copy per consumer.
    """
    dev_server_url = settings.VITE_DEV_SERVER_URL.rstrip("/")
    if settings.DEBUG and dev_server_url:
        return format_html(
            '<link rel="stylesheet" href="{}/src/app/tailwind.css">',
            dev_server_url,
        )

    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("frontend/tokens.css"),
    )


@register.simple_tag(takes_context=True)
def theme_resolution_script(context, user_theme=""):
    """The pre-paint theme script, carrying the request's CSP nonce.

    takes_context so the nonce can be read off the request: the policy names
    this script specifically rather than permitting inline script generally,
    so the tag and clarice.middleware have to agree on the value.

    Falls back to an empty nonce attribute when there is no request -- a tag
    rendered outside a request cycle should not raise, and a script with no
    nonce simply fails the policy rather than breaking the render.
    """
    server_value = user_theme if user_theme in ("system", "light", "dark") else None
    request = context.get("request")
    nonce = getattr(request, "csp_nonce", "") if request is not None else ""
    script = _THEME_RESOLUTION_SCRIPT_TEMPLATE.replace(
        "__SERVER_THEME__", json.dumps(server_value),
    ).replace("__NONCE__", nonce)
    return mark_safe(script)
