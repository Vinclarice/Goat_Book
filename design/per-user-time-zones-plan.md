# Per-user time zones — delivery plan

**Status: built, not deployed.** Promoted out of Track D and implemented on
August 1, 2026. The field, middleware, per-user digest, preferences API,
picker, admin and settings form are all in; 437 backend and 120 frontend
tests pass locally, and CI run `30704717836` passed the same Django suite
against the Postgres 18 service container, applying migration
`accounts/0010` on production's database engine. It has not run against
production itself, and it adds that migration to the deploy that already
owes M1's `capture/0003`.

Two decisions were taken during implementation that this plan did not
originally contain:

- The morning is a **window**, 07:00–12:00 local, not just a start time.
  Past it the day is written off unsent but recorded as decided, so a
  container down all morning does not deliver "Good morning" at 20:00.
- `time_zone` is **required** in `PreferencesIn`. That is a breaking change
  for any client PATCHing without it, which is acceptable only because the
  SPA ships in the same deploy.

## Why this is no longer deferred

`bittern-plan.md` set the reconsideration trigger for per-user time zones as
"a second active user in another time zone **or** a real scheduling error
caused by the global zone." Both have now happened:

- A second active user is in Indonesia, roughly twelve hours from the
  application's single `TIME_ZONE` of `America/New_York`.
- The daily digest delivered at 03:00 Eastern on August 1 rather than 07:00.
  The cause is unrelated to the user's location — the crontab entry is
  `0 7 * * *` and cron runs in the server's zone, which is UTC — but it is
  the same class of defect: one global clock standing in for a person's day.

A twelve-hour offset is the worst case for this bug rather than a mild one.
When it is mid-afternoon Saturday in Jakarta it is still early Saturday
morning in New York, so "overdue," "due today," and "this week" are computed
against the wrong day for that user for a large part of every day, and the
digest arrives in the middle of their night.

This also unblocks a known dependency: `daily-operating-system-vision.md`
records that Crane 0's routine and target design "needs a per-user time-zone
decision before day boundaries and streaks can be trusted."

## What actually depends on the current global zone

The codebase funnels nearly all day-boundary logic through
`django.utils.timezone`, which is what makes this tractable:

| Call site | Purpose |
| --- | --- |
| `lists/agenda.py` `completed_today_for` | Default `today`, plus `make_aware` for the completed-at day range. |
| `lists/agenda.py` `list_summaries` | Overdue counts per list. |
| `lists/agenda.py` `digest_items_for` | Default `today` for digest bucketing. |
| `lists/api_v1.py` | The agenda endpoint's `today`. |
| `lists/services.py` | Snooze presets' base date. |
| `lists/management/commands/send_due_digest.py` | One `today` shared by every recipient. |

Two facts make the change smaller than it looks:

1. **The frontend never computes a local date.** `workspace_data_for` sends
   `today` as an ISO string and `frontend/src/agenda.ts` takes it as a
   parameter; its `addDays` does UTC arithmetic on that string. No client-side
   timezone work is required, and no mirrored constant has to change.
2. **Everything server-side reads the *active* zone, not a hard-coded one.**
   Activating the right zone per request makes those call sites correct
   without editing any of them.

## Design

### The field

Add `User.time_zone`, an IANA key validated against
`zoneinfo.available_timezones()`, defaulting to `America/New_York` — the
current global value, so every existing row keeps exactly its present
behavior and the migration changes no semantics on its own.

`settings.TIME_ZONE` stays `America/New_York` and `USE_TZ` stays `True`. The
setting becomes the fallback for anonymous requests and for anything with no
user in scope, not the definition of everyone's day.

### Web requests: activate, don't rewrite

Add a middleware placed after `AuthenticationMiddleware` that calls
`timezone.activate(...)` with the authenticated user's zone and deactivates
for anonymous requests. Every call site in the table above then becomes
per-user with no change to its code.

Token-authenticated API requests are outside this: Ninja resolves the token
in the view, so `request.user` is not populated at middleware time. Capture is
the only token surface and stores timestamps rather than local dates, so it is
unaffected — but this is a real boundary and any future date-bearing token
endpoint must activate the owner's zone itself.

### The digest: hourly cron, per-user day

The command currently computes one `today` and one send moment for everyone.
It becomes per-recipient:

- Cron changes from `0 7 * * *` to hourly.
- For each opted-in user, compute their local date and local hour.
- Send when their local time has reached 07:00 and no digest has been sent
  for their local date yet.

Add `User.last_digest_date` (nullable date) recording the user's local date of
the last send. This is what makes an hourly job safe: it is the idempotency
guard, so a retried cron run, a restarted container, or a DST repeat cannot
send twice.

Use "at or after 07:00 and not yet sent today" rather than "hour equals 7."
An equality test silently skips a day whenever the 07:00 run is missed — a
reboot, a slow image pull, or a spring-forward transition that skips the hour
entirely in some zones.

`--dry-run` and `--username` keep working. Add an override for the send hour
so a test run does not require waiting for 07:00 anywhere.

### Choosing a zone

Add the field to the account settings form beside the digest preference and
theme. Existing users see `America/New_York` preselected.

Signup does not ask. A wrong guess is worse than a default that the person can
correct once, and there is no self-service signup yet anyway.

## Deliberately not in this change

- **No per-user digest hour.** Everyone gets 07:00 local. The field is easy to
  add later; adding it now doubles the preference surface for no evidence.
- **No browser-detected zone.** Offering `Intl.DateTimeFormat().resolvedOptions().timeZone`
  as a suggestion is reasonable later, but silent detection makes the app's
  idea of "today" change when someone travels, which is the opposite of what a
  due-date system should do.
- **No historical reinterpretation.** Existing `due_date` values are plain
  dates and stay exactly as entered. Changing a zone changes what "today"
  means from now on; it does not re-date anything.

## Tests

- Two users in `America/New_York` and `Asia/Jakarta` see different bucketing
  for the same task at a moment when their local dates differ.
- The agenda endpoint returns each user's own `today`.
- Snooze presets resolve against the requesting user's local date.
- The digest sends to a Jakarta user at 07:00 Jakarta and to a New York user
  at 07:00 New York on the same calendar run.
- A second run in the same local day sends nothing.
- A run that first executes at 09:00 local still sends that day's digest.
- An anonymous request falls back to `settings.TIME_ZONE` without error.
- Existing users without an explicit choice behave exactly as before.

## Sequencing against Bittern

This does not lift Stage 0's gate. B0's read-only artifact evidence still has
to be gathered before any deploy, and this work now guarantees a deploy is
coming, so gathering it stays the first thing.

The `CRON_TZ` correction considered for the 03:00 delivery is superseded and
should not be applied: a single zone-pinned daily cron cannot serve both
users, and the hourly schedule above replaces it.
