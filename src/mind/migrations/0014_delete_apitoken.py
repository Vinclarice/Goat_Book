"""The knowledge core's own token table, dropped.

`ApiToken` was a long-lived bearer credential with its own `sm_` prefix and its
own resolver, built so the Android app could point at a separate Second Mind
server by setting one build property. No shipped build ever set it, and these
pages carry no JavaScript, so nothing ever called the API it authenticated.

**Checked before dropping, not after: `ApiToken.objects.count()` on production
returned 0 on August 15, 2026**, before this was written to run there.

That check was the whole of the safety. The table stores only hashes, so there
is nothing to migrate anywhere and nothing a backup would have helped with; a
non-zero count would have meant a device somewhere that this silently
disconnects, and would have meant stopping to find out which.

Reversing recreates an empty table, which is honest: the secrets were never
recoverable, so no reverse could restore a working credential even in principle.

The application has one token table now, `accounts.PersonalAccessToken`, and it
has scopes, which this never did.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mind", "0013_maintenance_ran_event"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ApiToken",
        ),
    ]
