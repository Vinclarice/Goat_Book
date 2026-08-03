"""Project-level middleware. Currently the content security policy.

Kept here rather than in an app because it is not about tasks, capture or
accounts -- it is a property of every response the project serves.
"""
import secrets


# One place, so the header and the template tag that consumes the nonce
# cannot drift into disagreeing about what is allowed.
#
# Report-only for now -- see clarice/tests/test_content_security_policy.py
# for what that does and does not defer. Switching to enforcement is a
# one-line change to the header name, and should happen once the browser
# console has stayed quiet through real use.
CSP_HEADER = "Content-Security-Policy-Report-Only"

CSP_DIRECTIVES = (
    "default-src 'self'",
    # 'self' plus a per-request nonce for the one inline script this
    # application deliberately has: the theme resolution script, which must
    # run before first paint or the page flashes the wrong theme. A nonce
    # names that script specifically instead of permitting every inline
    # script the way 'unsafe-inline' would.
    "script-src 'self' 'nonce-{nonce}'",
    # 'unsafe-inline' stays, and it is a considered trade rather than an
    # oversight. app_shell.html carries an inline <style> block and React
    # writes inline style *attributes* for the area colour dots; a nonce
    # cannot cover an attribute, so removing this would mean a refactor
    # against a far narrower class of attack than script injection.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    # Belt and braces with XFrameOptionsMiddleware, which says the same
    # thing in the older header that some clients still prefer.
    "frame-ancestors 'none'",
)


class ContentSecurityPolicyMiddleware:
    """Attaches a per-request nonce and the policy that names it.

    The nonce is generated *before* the view runs, because the template tag
    that renders the inline script reads it off the request while rendering.
    Generating it afterwards would produce a header naming a nonce no script
    ever carried.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        # setdefault, so a view that has its own reason to set a policy keeps
        # it rather than being silently overridden here.
        response.setdefault(
            CSP_HEADER,
            "; ".join(CSP_DIRECTIVES).format(nonce=request.csp_nonce),
        )
        return response
