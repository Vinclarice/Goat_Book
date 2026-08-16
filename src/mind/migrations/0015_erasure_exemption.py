"""One narrow hole in the append-only log, so an account can be erased.

`ActivityEvent` is append-only by trigger, and that made deleting a `User`
impossible: `owner` is `on_delete=CASCADE`, so `User.delete()` issues a `DELETE`
against the log and the trigger raises. Nothing had noticed, because nothing had
ever deleted an account — `commercial-blueprint.md` calls that a legal blocker.

**Append-only means history cannot be rewritten within a live account.** It was
never a promise to outlive the account's own erasure, and it cannot be: the log
is not content-free. Concept events carry the labels somebody typed, which on
real material include other people's names, and every event carries the username
as `actor`.

Three things make this an exemption rather than a loophole:

* It fires only for `DELETE`. `UPDATE` is refused exactly as before, so no row
  can be rewritten by any route.
* It names **one owner id** rather than being a boolean. An erasure in flight
  cannot take another account's log with it, even by a mistake in the caller.
* It is read from a **transaction-local** setting (`SET LOCAL`, via
  `set_config(..., true)`). Connections are reused across requests; a setting
  that outlived its transaction would leave the log erasable by whatever ran
  next on that connection.

`current_setting(name, true)` returns NULL when unset, and `NULL = anything` is
NULL rather than true, so the ordinary path falls straight through to the
`RAISE`. The only caller is `accounts.services.purge_account`.
"""

from django.db import migrations

ERASURE_EXEMPTION = """
CREATE OR REPLACE FUNCTION mind_activity_event_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('mind.erasing_owner', true) = OLD.owner_id::text THEN
        RETURN OLD;
    END IF;

    RAISE EXCEPTION 'activity_event is append-only (attempted %)', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

# The function exactly as `0002_invariant_triggers` created it. The trigger
# itself is untouched by both directions -- only the body it calls changes -- so
# there is nothing to drop and recreate.
ERASURE_EXEMPTION_REVERSE = """
CREATE OR REPLACE FUNCTION mind_activity_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'activity_event is append-only (attempted %)', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("mind", "0014_delete_apitoken"),
    ]

    operations = [
        migrations.RunSQL(ERASURE_EXEMPTION, ERASURE_EXEMPTION_REVERSE),
    ]
