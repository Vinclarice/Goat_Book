from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = template.Library()

# Blocking, runs before the stylesheet loads so there's no flash of the
# wrong theme. localStorage is a stand-in for the real per-user preference
# until Step 4 adds User.theme and /api/v1/me/preferences -- once that
# lands, a server-rendered value takes priority over this.
_THEME_RESOLUTION_SCRIPT = """
<script>
(function () {
  var STORAGE_KEY = "clarice-theme";
  var COOKIE_NAME = "clarice_theme";

  function resolve(saved) {
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.cookie = COOKIE_NAME + "=" + theme + "; path=/; max-age=31536000; samesite=lax";
  }

  var saved = localStorage.getItem(STORAGE_KEY);
  apply(resolve(saved));

  if (!saved) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (event) {
      apply(event.matches ? "dark" : "light");
    });
  }
})();
</script>
""".strip()


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
    shell entry's JS. Styling is separate -- see token_styles() below,
    shared with the Django-rendered token pages.
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


@register.simple_tag
def theme_resolution_script():
    return mark_safe(_THEME_RESOLUTION_SCRIPT)
