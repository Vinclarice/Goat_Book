"""Enrolment mechanics for the second factor: the QR, and the recovery codes.

Kept out of the view for the reason `monitoring.py` and `deployment.py` give
for their own splits -- these are decisions with consequences worth testing
directly, rather than steps buried in a request handler.

See `design/admin-mfa-plan.md`.
"""
import base64
import io

import qrcode
from qrcode.image.svg import SvgPathImage

from django_otp.plugins.otp_static.models import StaticDevice, StaticToken


# Ten is the usual size of a recovery batch, and the number matters less than
# the fact that it is a batch: one code is a single point of failure and fifty
# is a thing nobody writes down.
RECOVERY_CODE_COUNT = 10

# The name every recovery batch travels under, so re-issuing replaces rather
# than accumulates. A person with three overlapping batches does not know which
# piece of paper is live.
RECOVERY_DEVICE_NAME = "recovery codes"


def enrolment_qr(device):
    """The device's `otpauth://` URI as an inline SVG data URI.

    **A data URI rather than a served file**, and that is a policy decision
    rather than a convenience. `clarice.middleware` allows `img-src 'self'
    data:` and nothing else, so an image served from a generated URL would need
    a new CSP rule -- and the secret would then exist at a fetchable address
    rather than only inside the page that already required a session to render.

    SVG rather than PNG because the PNG factory needs Pillow, which is a large
    dependency to add for an image made of squares.
    """
    image = qrcode.make(device.config_url, image_factory=SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def issue_recovery_codes(user):
    """Replace this account's recovery batch, and return the new codes.

    Returns the plain strings, because this is the one moment they can be
    shown; afterwards they are rows that `StaticDevice.verify_token` consumes
    one at a time and deletes. Nothing can recover them, which is the same
    property the access-token page relies on and for the same reason.

    **Replace rather than add.** `get_or_create` on a fixed name, then clear
    the old tokens: re-issuing is something a person does *because* they think
    the last batch is compromised or lost, so leaving it working would defeat
    the action they just took.
    """
    device, _ = StaticDevice.objects.get_or_create(
        user=user, name=RECOVERY_DEVICE_NAME
    )
    device.token_set.all().delete()

    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        token = StaticToken.random_token()
        StaticToken.objects.create(device=device, token=token)
        codes.append(token)
    return codes
