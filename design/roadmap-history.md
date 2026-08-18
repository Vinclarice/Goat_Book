# Clarice — Roadmap History

Vince · completed work and decision record · archived from `roadmap.md` on
August 1, 2026

The reasoning, deployment record and lessons behind completed work, kept out of
the active plan so that plan stays scannable. The active plan is
[`roadmap.md`](roadmap.md).

## Production defects — Part 1, opened August 12 and closed August 15, 2026

Ten defects found by the commercial audit. All closed; `commercial-blueprint.md`
Part 1 is four lines now, because a defect list with nothing on it is a document
outliving its work.

| # | Defect | Closed by |
|---|---|---|
| 1 | CI had failed 17 consecutive runs | `fd4a8d7` — and it needed three fixes, not one: the `mind` suite was not in CI at all, `postgres:18` carries no pgvector, and the browser job could no longer use SQLite |
| 2 | Token-authenticated writes recorded the wrong day | `6da41c8`, at `_resolve_scoped_token` — the seam both token paths share, rather than at the six endpoints that each forgot |
| 3, 4 | Two dropped Tailwind styles | `2986ed6` — **already shipped on August 12**; the list said otherwise for two days |
| 5 | A white screen on any render exception | `0428efb` |
| 6 | Tags dropped on one of two promotion routes | Declined August 14; moot August 15 when Heron deleted both routes |
| 7 | The Android capture queue had no lock | A process-wide lock on the companion object — not `@Synchronized`, which would have passed a shared-queue test and protected nothing |
| 8 | The queue was included in Android backups | Excluded in *both* `backup_rules.xml` and `backup_rules_legacy.xml` |
| 9 | Nothing would tell you the site was down at 3am | `/healthz` (`fd896c6`), `restart_policy: unless-stopped` (`b2e16b2`), and UptimeRobot polling it from August 15 |
| 10 | Sentry could ship private note text | `bbfc38d` — `include_local_variables` defaults to `True` and is independent of `send_default_pii=False` |

**Three lessons cost a session each and outlive the defects.**

- **A signal that is always red carries no information.** CI failed seventeen
  times and stopped being read; the same shape appeared twice more that week —
  certbot failing on a deleted staging certificate, and a defect list nobody
  trusted.
- **A fix does not repair what the defect already wrote.** Defect 2 filed real
  `RoutineOccurrence` rows against the wrong date for as long as it existed, and
  nothing recorded which auth path created a row, so a repair would have to
  guess at a durable record — which `principles.md` refuses. Left alone
  deliberately, recorded so it is a decision rather than an oversight.
- **The list twice described finished work as open**, which cost more than the
  defects did: a session of re-investigation on the Android pair, two days on
  the Tailwind pair. If a list like this exists again, check the code before
  believing it.

## Code review findings — closed from August 18, 2026

Findings from [`code-review-2026-08-16.md`](code-review-2026-08-16.md), taken in
the order that review ranked them. **The review itself gets no status lines** —
it is a record of one review at one commit, and annotating it with what happened
afterwards is the drift [`README.md`](README.md)'s rule exists to stop. What
happened to its findings lives here instead.

`commercial-blueprint.md` Part 1 stays closed and empty throughout. None of these
was ever promoted to it, so there is no defect-list entry to close, and promoting
a finding remains a separate decision.

| # | Finding | Closed by |
|---|---|---|
| D1 | CRITICAL — unsaved edits destroyed by a background refetch, in three routes | `4bf8bc9` |
| D2 | HIGH — one nullable column, four broken surfaces | `4e89675` |
| D3 | HIGH — Sentry shipped raw request bodies despite `send_default_pii=False` | `dedc23d` |
| D4 | HIGH — `/api/v1/login` unthrottled at every layer | `9eb9eea` |
| D5 | HIGH — `open_question` filtered on `dormant_thread`'s name | `c9ac698` |
| D6, D11 | HIGH / MEDIUM — three scheduled loops where one account blocked the rest | `70f27b1` |
| D7 | HIGH — note text in the nginx access log and in Sentry's `query_string` | `faf55dd` |
| D8 | MEDIUM — area deletion destroyed completed and archived work with no count | `23a47e1` |
| D9 | MEDIUM — routine progress was an unlocked read-modify-write | `c9be0ec` |
| D10 | MEDIUM — a deletion could be scheduled with its warning never sent | `4d4a225` |
| — | A production incident, and what guarding these loops had cost | `0a87f91` |
| D12 | MEDIUM — the export dropped every tag association and three models | `79d2816` |
| D16 | LOW-MED — corrected the false hourly-cap claim (behaviour unchanged) | `0476bb3` |
| D13 | MEDIUM — side-nav counts went stale on every task write | `9631e32` |

### D1 — the refetch clobber

`TaskDetailRoute`, `AreaRoute` and `ProjectRoute` each seeded form state from
inside the `queryFn`, so the setters re-ran on every settle of the query. With
`refetchOnWindowFocus` on and `staleTime` at 0, alt-tabbing away from a
half-written note and back restored the server's value over it. It broke the
product's own core promise, and it was the **third** time the project had fixed
this bug — `PreferencesRoute` and `DayRoute` already carried the guard.

**It was never only the alt-tab, which the review did not say.** Four of
`ProjectRoute`'s own mutations call `refresh()`, which invalidates the very query
that seeds the title; `AreaRoute` reaches it through `projectMutation`'s direct
`refetch()`. Renaming a project and then adding an area to it lost the rename,
with the area's success message beside it — no window focus involved. That is
the path a person actually walks, and the review missed it by reasoning from the
mechanism rather than from the page.

**Moving a side effect out of a render path opens a gap.** With the setters in an
effect, one render has `data` and no seeded state; `TaskDetailRoute` guarded on
`!task || !areaRef` and would have flashed `RouteFailure` over a request that had
just succeeded. `!data` is a failure, `!task` is a load, and they are not the
same guard.

### D2 — the half-introduced nullable column

`Item.list` went nullable on August 14 (`0857835`). That commit fixed five sites
and drew the rule in its own message — *"a nullable column is only
half-introduced until both directions are covered"* — then did not touch
`src/review/` or `android/`. Four surfaces still read the column as non-null,
every one of them one tap from `/mind/`'s `confirm_actionable`.

`/api/v1/review` **500d permanently**, because Ninja validates responses and
`CompletedTaskOut.area_id` was `int`. There was no way out from inside the
product: `completed_in_week` filters on `completed_at` alone, so archiving the
task does not clear it and only setting an Area by hand ever did. The digest
**crashed rather than degraded**, and its loop orders by username, so one
affected account starved every recipient sorting after it. Both Android read tabs
**blanked**, because the payload-level catch discards the whole response.

**The near-miss is the finding.**
`test_a_task_without_an_area_is_readable.py` already constructed exactly the
state that 500s the week — `archive_item(complete_item(self.unfiled))` — and
asserted only `/api/v1/archive`. One more line would have caught this the day it
shipped.

### D3 — the same trap, one option over

`send_default_pii=False` gates **cookies**. In `_wsgi_common.extract_into_event`,
`should_send_default_pii()` guards the cookie line while `request_info["data"]`
is set unconditionally; the only thing between a request body and Sentry is
`max_request_body_size`, never passed, defaulting to `"medium"` — ten kilobytes.
Every captured thought, every day's intentions and every task note is far under
that, so a 500 on a capture or day write sent the writing itself.

**This is defect 10 a second time.** That fix's comment drew the rule — *"the
default belongs to a dependency: silence here is a decision made by whoever last
released the SDK"* — and the option beside it was left silent. Two comments and a
test docstring asserted the opposite of the truth in between, which is what let
the second one sit unnoticed after the first was found.

### D4 — the rule that was written down twice and never applied

`POST /api/v1/login` trades a password for a 90-day all-scopes token, is
`auth=None` by design, and matched nothing but the catch-all `location /`.
Both the nginx template's header and `settings.py` state that nginx throttling
is the first line of defence and django-axes the second; neither was true for
the one route where it mattered most. `architecture-trajectory.md` §6 records
closing this identical hole for `/` on August 3, and the API login shipped three
days later without a matching rule.

**The only one of these findings `roadmap.md` already carried as open**, and now
the only one whose fix is not yet live: an nginx template changes nothing until
the playbook runs.

**What replaces it is a test, not a rule.** The rule closes this route; the test
reads the template and the API together and fails on any operation with an
explicit `auth=None` that has no throttled exact-match block. `auth_param` is
the discriminator Ninja already keeps — `NOT_SET` for an operation inheriting
`django_auth`, `None` for one opting out. Two more tests keep it from passing
vacuously, because an introspection that quietly returned an empty set would
pass while covering nothing.

**Proved by running it.** There is no staging, so a template test that says a
rule exists is not the same as knowing nginx accepts it. The template was
rendered with the playbook's own variables and served by nginx 1.31.3 in a
container: eight POSTs to the login gave four 200s then four 429s, the reset
gave six then two, and eight GETs to `/api/v1/agenda` all returned 200 — the
half that matters second, since a rate limit that reached the authenticated API
would be a worse defect than the one being fixed.

### D5 — a workaround that hid the defect it worked around

`open_question` imported `_previously_proposed_ids` from `dormant_thread`, and
Python binds a function's globals to its *defining* module — so the filter
queried `detector="dormant_thread"`. Its own `DETECTOR` sat one line below the
import, consulted by nothing. A dismissed answer came back every night forever,
and every pair `dormant_thread` had already proposed was permanently invisible
to it — the directional finding this detector exists for, unreachable on exactly
the pairs most likely to have one.

**`semantic_echo` and `shared_referent` had each already worked around it**, by
keeping an identical private copy of the body. That is what kept it hidden: with
two of three detectors carrying their own, the one that did not looked like the
pattern rather than the exception. A fourth copy would have left the trap for the
fifth detector, so the fix passes the detector as an argument and there is one
body again.

**The refactor proved itself mid-change.** Between changing the signature and
changing the body, `shared_referent`'s own dismissal tests failed — evidence
both that the collapsed function is the one all four use, and that those tests
reach the filter rather than the fingerprint constraint that would mask it.

### D6 and D11 — three loops, one shape

Taken together because they are one defect in three files. Every scheduled
command that loops over accounts ended its run on the first failure.

**The digest was the worst of them.** The loop orders by username, so an
unguarded raise did not *delay* everyone sorting after the failing recipient —
it never delivered to them, and the write-off path stamped `last_digest_date`
anyway, recording the day as decided. Daily, and leaving no trace in the data.
`purge_deleted_accounts` held every remaining erasure open on one bad address;
`run_mind_maintenance` lost the pass *and the marker* for every owner after a
failure, which `/numbers/` then reports as never maintained — true, and silent
about why.

**The digest already guarded the other instance of this exact class**, two lines
above the one that was missed: `resolve_time_zone(...) or ZoneInfo(...)` exists
so one bad time zone cannot stop the run. The class was recognised and the
likelier case left open.

**A failed iteration is deliberately not marked done.** The digest does not stamp
a day it did not decide, so the next hourly run retries and the existing
`until_hour` write-off still closes it out; maintenance writes no marker for a
corpus it did not finish. Catching an exception must not turn into recording
success.

**One narrower instance is left open on purpose.** `run_detectors` catches only
`Unavailable` per node, so a single malformed note still costs one owner their
pass. Its blast radius is now one owner, reported and exiting non-zero, instead
of everybody after them.

### D7 — the words were in the URL by design

`manifest.json` declares the share target `"method": "GET"`, which is what lets a
share work with no service worker, so a shared passage reaches `/mind/share/` as
`?text=`. `/mind/search/` takes `?q=`. That is a good design decision and it put
somebody's own words in the request line, where two separate things wrote them
down.

**The disk half was unconditional and is the larger one.** No `access_log`
anywhere in the template and the playbook never templates `nginx.conf`, so the
distro default applied — `combined`, whose `$request` is the verbatim request
line. Every search and every share, on every request, in plaintext, for as long
as rotation keeps it. The fix logs `$uri` instead, keeping every other field, so
the log holds its operational value and not the query. The port-80 block needed
it too: it only redirects, but `return 301 https://$host$request_uri` carries the
query onto that hop.

**The Sentry half is narrower, and the review was right to separate them.**
`query_string` is set unconditionally and the default `EventScrubber` never
touches it — but with no `traces_sample_rate` there are no transaction events, so
it travels only when an error is captured. On error, not on every request. No
option covers it, so it takes a `before_send`; `request.url` is left alone
because `get_request_url` excludes the query already.

**Observed, not reasoned.** nginx 1.31.3 was run against the rendered template
before and after: `"GET /mind/search/?q=therapy%20notes%20about%20my%20marriage"`
became `"GET /mind/search/"`. The template tests that now guard it were written
afterwards and passed immediately — regression guards, and said to be.

### D8 — the finding was the disclosure, not the behaviour

The first of these that turned out to be a product decision rather than a defect,
and the verifier who narrowed it was right. Deleting an Area does hard-delete
completed and archived tasks, and `completed_in_week` has no snapshot so they
leave past weeks retroactively — but the UI already warned, and `reads.py`
already documents the consequence by name, calling it the reason §8 has a
completed review stamp its figure. A reasoned trade, not a missed case.

**So the fix is disclosure and the behaviour stands** — Vince's call, asked
rather than assumed. The dialog now names the counts, archived separately
because `area_detail` sends `archived_count` rather than including those tasks in
`items`: they are not in the list the person is looking at, which is why they are
easiest to forget.

**Detaching had become newly possible in the meantime, and was not taken.** D2's
nullable `Item.list` made an unfiled task first-class, so `SET_NULL` would work
now where it would not have when this was designed. Recorded because the option
changed without anyone deciding it had.

**Both halves of the consequence are stated.** Weeks never reviewed change; weeks
whose review was completed keep their stamped figures. Saying only the alarming
half would be its own kind of wrong, and the breakdown is shown only where it
says something — "0 completed, 0 archived" is the padding that teaches people to
dismiss the dialog.

### D9 — the count that cannot be reconstructed

`log_progress` read `progress`, added in Python and saved: no
`select_for_update`, no `F()`. Two taps read the same number and wrote the same
number. It matters more here than the shape suggests because **the log is the
count** — nothing else records the increment, so if the loss is what makes a
period miss its target, `habits_met` is wrong for that week and no record
disagrees. `lists/services.py` opens every mutation with a lock; this module
opened none.

**Proved with two threads on two connections.** A test inside one transaction
cannot see this and would pass against the broken version. Before the fix,
`2 != 3`; after, `3`, five runs running. The occurrence is created and committed
before the threads start, or both race `get_or_create`'s INSERT instead — which
Postgres serialises on the unique index, a different mechanism that would mask
the one under test.

**The sweep found three more and one of them bit back.** `call_it_enough` is the
same defect on the same row; `pause_routine` and `resume_routine` are the same
shape on `Routine`, costing a duplicated `RoutinePause`. Rebinding `routine` to
the locked row stopped those functions mutating the instance the caller handed
them — so a test that paused a routine and then logged against that object found
`is_active` still true. **A concurrency fix quietly reopened the hole pausing
exists to close**, and three existing tests caught it. Locked and refreshed in
place instead.

Only `log_progress` has a concurrency test; the other three carry the idiom and
their behavioural tests. Said here rather than left to look like full coverage.

### D10 — the guard was right and its precondition was not

`request_deletion` wrote the timestamp, committed, then sent the email. A failed
send left the account scheduled with nobody told — and the idempotency guard made
that **permanent**, because the retry took the early return. The guard is
correct: a doubled click is not a second decision. What nothing enforced was its
precondition, that the message went out when the timestamp was written.

**`purge_account` already had this right, twenty lines below**, and says so in
its own comment: *"a receipt for an erasure that did not happen is worse than no
receipt."* Reasoned once, in the same file, and not applied to its neighbour.

**`EMAIL_TIMEOUT` is part of the fix, not beside it.** Sending inside the atomic
block puts an SMTP round trip between BEGIN and COMMIT; unset, smtplib inherits
the global default socket timeout — also unset — so a hung relay would hold that
transaction open unboundedly, on one worker with four threads.

**The rollback was not enough, and the test caught why.** A transaction undoes
the row and cannot undo an attribute on the caller's instance, so the user object
kept claiming a timestamp the database no longer had — and the guard took the
early return again. *The defect, reintroduced by its own fix.* The same
divergence bit `pause_routine` during D9, one finding earlier.

**`cancel_deletion` is deliberately asymmetric and now says so.** Rolling a
cancellation back because its receipt bounced would leave an account scheduled
for erasure after the person asked to keep it — trading a missing email for the
outcome the email was about.

### The August 16 SMTP timeout — the fix that would have hidden the next one

Not a review finding. A real Sentry report, arriving mid-series: a connection
timeout at `send_due_digest`'s `send_mail`, 13:00 UTC on August 16 — D6 in
production, on the deployed code, before any of this landed.

**It confirmed two committed fixes and broke a third.** The breadcrumbs run
13:00:03 to 13:04:35: four and a half minutes inside `socket.create_connection`,
Linux retrying SYNs across both of the relay's addresses with no timeout set.
D10's `EMAIL_TIMEOUT` bounds exactly that, and Django's SMTP backend does read it
through to `create_connection`. And the failure was the *relay being
unreachable*, not one rejected recipient — so it failed identically for
everybody, and unguarded it cost every user that hour rather than the ones
sorting after a bad address.

**The third is the one worth keeping.** The only reason anybody knew about this
is that the exception propagated and Sentry caught it. Guarding the loop took
that away: `BaseCommand.run_from_argv` catches the `CommandError` the guard
raises, writes it to stderr and exits, so it never propagates — and cron has no
`MAILTO` and the host no MTA, so stderr reaches nobody. **The fix for D6 would
have made the next outage completely silent, which is worse than the crash it
replaced.** All three guarded loops now `logger.exception` the caught error;
sentry-sdk installs `LoggingIntegration` at event level ERROR by default, so that
is an event without any command importing the SDK.

Generalise it: **a guarded loop reports through logging or it reports nowhere.**
Catching an exception moves the decision about who hears about it from the
runtime to you, and the default answer becomes nobody.

### D12 — a promise nothing could check

`_rows` iterates `_meta.concrete_fields`, which excludes many-to-many by
definition, so tags left as a list of names with nothing saying which tag was on
which task. Three models were never queried: `HypothesisMember` — the span
citations that are a hypothesis's whole evidence — plus `Attachment` and
`SentenceEmbedding`. The module docstring promised *"every row of every owned
model across both cores"*.

**The stakes are what make it more than untidy.** This file is what stands
between somebody and irreversible erasure. Export, then delete, and an
association missing here is not missing — it is destroyed, with no other copy.
`product-stories.md` scores leaving with your data as one of only three journeys
that work.

**The promise was not checkable, so it was not true.** `EXPORT_KEYS` now exists
to be checked rather than read: a test walks every concrete model in the six
owning apps and fails if one has no export line. A model added later is caught by
the suite instead of by somebody who has already deleted their account.

**The guard passed by coincidence, and the probe is the only reason that is
known.** Walking the payload recursively descended into `ActivityEvent`'s JSON,
so a key appearing in somebody's activity data counted as proof a model was
exported — it reported the export complete with `Attachment` removed. It reads
the payload's own two levels now and fails on that same mutation.

### D13, D14 and D16 — re-verified before being touched

Three findings the review itself was least sure of, checked against the tree
before any of them was fixed. **All three mechanisms held**, and three details
did not.

**D13 was understated.** The right pattern is in *seven* files, not four —
`AgendaWorkspace`, `AreaRoute`, `PreferencesRoute`, `ProjectRoute`,
`ProjectsIndexRoute`, `ReviewRoute` and `DeletionBanner`. Seven right and three
wrong reads as oversight rather than unsettled convention. Fixed by invalidating
after *every* write path in the three, not the ones whose counts obviously move:
picking is how it happened, and a rule re-derived per handler gets missed again.

**D14 held, including its own self-correction.** No `SearchRank` anywhere; a
`.distinct()[:30]` over a `-captured_at` order with no count in the template. Run
directly: 35 matches, 30 returned, 5 silently dropped. And searching a term the
person *deleted* in a revision returns the note while the page renders text
without it. `retirement_gate` really is about absorbing the task core's domains,
so inflated misses hold it shut — the review was right to invert its own claim.

**D16 held, and I had made it worse.** Its honest framing is that the defect is a
false statement, and D4 rewrote that exact comment block while preserving the
sentence — *"caps how many messages actually leave per hour"* — the review had
already identified as untrue. The counter is `LocMemCache` in one gunicorn worker
recycling every ~500 requests, and whitenoise serves every static asset through
that worker, so ordinary browsing resets it. Corrected in both places that
claimed it; the behaviour fix needs a shared cache, which is infrastructure
nobody has decided to add.

### What these have in common

- **A fix applied only where the bug was reported is not a fix.** D1 was guarded
  in two of five stateful routes; D2 in five of nine sites; D3 was the option
  beside the one defect 10 had just fixed. All three survived a fully green suite
  because the unguarded places were the untested ones.
- **The idiom was always already present.** `PreferencesRoute`'s `seeded` ref for
  D1; `optIntOrNull("project_id")` one line below `getInt("area_id")` for D2;
  defect 10's own "pass it explicitly" comment for D3. None needed a design
  decision, only a sweep.

- **A comment that is wrong hides the next defect.** D3 sat behind three
  assertions that `send_default_pii` covered request bodies — in the module, in a
  test comment and in a test docstring. The first fix read them and stopped.
- **A regression guard that passes on its first run has to be probed.** The
  seeding ref is keyed on the record id rather than a boolean; degrading it to a
  boolean kills that test and only it, which is what makes it worth keeping.
- **The type check earns its place at a schema change.** Regenerating the
  contract after D2 named `ReviewRoute`'s hand-written mirror type immediately —
  the same way `0857835` found seven.

- **A stated architecture is not an implemented one.** D4's rule was written
  down in two files and applied in neither, for the route that needed it most.
  Where a guarantee spans two languages or two tools, the only thing that holds
  it is a test that reads both — which is what D2's and D4's fixes each left
  behind.

- **A local workaround hides the defect it works around.** Two detectors kept a
  private copy of D5's filter rather than fixing why the shared one was wrong,
  and that made the broken caller look like the ordinary case. Copying to avoid
  a bug is a decision worth writing down, because the next person reads the
  copies as the pattern.

- **Guarding one instance of a class is where the class stops being looked
  for.** D6 sat two lines below a guard against the same failure, D3 one option
  below a fix for the same trap, and D5 one import from two detectors that had
  already worked around it. Each time the near-miss was written down and the
  neighbour was not checked. The sweep is the cheap part; remembering to run it
  is the whole discipline.

- **A fix is a change, and changes have their own blast radius.** D9's sweep
  reintroduced a defect while removing one, because rebinding a variable
  silently dropped an in-place mutation three tests depended on. D10's fix
  reintroduced *its own* defect, because a rollback cannot reach an attribute
  on the caller's instance. Twice in two findings, both times the divergence
  between a row and the object holding it, both times caught by a test. The
  sweep these lessons keep asking for is not free; the tests are what make it
  affordable.

- **Editing around a known untruth preserves it.** D16's false comment survived
  a rewrite of the very lines it sat in, because the edit was about rate limits
  and the sentence was about something else. A finding that says "this comment is
  wrong" is a finding about a file, and touching that file is the moment to act
  on it.

- **A test written after the fix has to be attacked before it is trusted.** D12's
  coverage guard passed on its first run and was worthless: it descended into a
  JSON blob and found the key it was looking for by accident. Two of these
  regression guards have now been probed by breaking the code they guard, and
  one of them failed that check. The first run proves nothing; the mutation is
  the test of the test.

- **Symmetry is not a reason.** D10's two halves look identical and must behave
  differently: the request rolls back because the email *is* the protection, the
  cancellation must not because rolling back would schedule an erasure the
  person just declined. Written down at the function, because the next person to
  notice the asymmetry will otherwise fix it.

- **Not every finding is a defect, and the difference is who decides.** D8's
  mechanism was real and its framing was not: the behaviour was a documented
  trade and only the disclosure was missing. A review can establish that
  something happens; whether it should is the product's question, and the fix
  that changes behaviour needs an answer rather than an assumption.

- **Three of these were about what leaves the server, and only one had a
  setting.** Defect 10 had `include_local_variables`, D3 had
  `max_request_body_size`, D7 had nothing and needed a hook. A dependency's
  options are a list of what it thought to make configurable, not a list of what
  it sends — so the question to ask of a monitoring SDK is what the payload
  contains, not which switches are off.

D1b — `AddRoutine` clearing before its request resolves, and expired-session 401s
handled on reads but not writes — is D1's class and is **not** fixed.

## Account deletion and data export — August 16, 2026

The first piece of the commercial substrate, and the one that did not wait on
`commercial-blueprint.md` Part 9's unanswered first question — *is Clarice a
business, a product with users, or a personal tool* — because the answer is the
same either way: the blueprint calls the pair a legal blocker rather than a
feature gap, and Sentry and Resend already process other people's data.

**Deletion was not unbuilt, it was impossible.** `ActivityEvent` is append-only
by a `BEFORE UPDATE OR DELETE` trigger and `ActivityEvent.owner` was
`on_delete=CASCADE`, so `User.delete()` raised. The model had reasoned exactly
this through for its *node* reference — "CASCADE, SET_NULL and SET_DEFAULT are
each a *mutation* of the log, which the append-only trigger refuses" — and made
that one non-constraining; the owner reference never got the same treatment,
because nothing had ever deleted an account.

**The line taken: append-only means history cannot be rewritten within a live
account.** It was never a promise to outlive the account's own erasure, and
could not be, because the log is not content-free — concept events carry the
labels somebody typed, on real material including other people's names, and
every event carries the username as `actor`. The exemption is narrow on purpose:
`DELETE` only, naming **one owner id**, read from a **transaction-local**
setting. A boolean would have passed the "erases my log" test and failed the
"does not touch anybody else's" one; `SET LOCAL` matters because connections are
reused across requests.

**A thirty-day grace period, and `is_active` deliberately untouched** — that flag
already means "pending admin approval", and one flag for two unrelated states is
indistinguishable everywhere it is read. The account stays fully usable while
leaving, which is what keeps *cancel* reachable without inventing a signed-link
email flow for a window that is the person's own to close.

**Two things were found by reading rather than by asserting.** A fixture claimed
to cover every owned model and missed four, caught by the "another account is
untouched" test failing — a neighbour with no rows cannot have them preserved;
there is now a test that the fixture populates what it claims. And an export for
an account with no areas produced a `tasks.md` containing the word "Tasks" and
nothing else, indistinguishable from a broken export at the exact moment you
most need to trust the file.

**Four more came from Vince reading the copy rather than the code**, which is the
review the tests could not do — every one passed against wording that was not
good enough.

* **It never said "permanent".** *Erased after 30 days* implies irreversibility
  rather than stating it. It now says permanently deleted and cannot be
  recovered — section, banner and email — and tests assert those words.
* **There was no acknowledgement.** Password re-entry guards the wrong mistake:
  it stops a passer-by at an unlocked screen and does nothing about somebody who
  has misread what the button does. Two gates now, and the tests say which
  mistake each one guards.
* **Nothing was emailed.** The thirty-day window only protects somebody who
  finds out inside it, and a banner cannot guarantee that. Three messages now —
  scheduled, cancelled, and a receipt sent immediately before the rows go, which
  reads the address *before* the delete, because a receipt depending on the
  record whose destruction it confirms never sends.
* **The banner was built to be global and wasn't.** `deletion_purge_at` went on
  the nav payload specifically so it could render on every route, then was wired
  only into Preferences. `DeletionBanner` now lives in `AppLayout` and carries
  the stop button itself, because "go and find the page where you did it" is
  harder than starting it was.

**One nav entry went with it.** "Settings" sat beside "Preferences" and linked to
`/accounts/settings/`, a two-line view redirecting to `/preferences` — one page
with two doors. The URL stays, since it is bookmarkable and `change_password`
redirects to it; the duplicate door is gone.

Verified by 911 Django, 616 pytest, 277 frontend and 32 browser tests, including
a browser test that downloads the archive and opens it. The secrets exclusion was
checked by emptying it and confirming the password and token hash then appear —
the test would have caught its removal, which is not the same as the test having
been watched fail.

## Heron — the crossover, August 15, 2026

**Tagged `heron` on `04e7c71`.** All five steps built, deployed and verified in
production in one day: 1–4a at 1200, then 4b and 5 together at 2030 — held to
one deploy on Vince's call, so the crossover was never half-live. The plan is
[`one-capture-surface-plan.md`](one-capture-surface-plan.md).

**Steps 1 and 2** wired a typed tag to a confirmed concept and carried a node's
concepts onto the task made from it, on almost no new machinery:
`ConceptCandidate` already had `label`, `confirmed_at` and `reason`, and
`propose_mention` with an explicit origin already self-confirmed. The trade it
settled was real, though — the Inbox modelled tags as first-class rows and the
knowledge core deliberately models none. The reconciliation is that **the
gravity gate exists to filter the system's guesses**: three mentions across a
day is what an *extracted* candidate pays because extraction over-generates on
purpose, and a person typing a tag is not a guess.

**Step 3** moved 34 captures and 2 ideas into the graph carrying their original
timestamps, 22 archived on the way in as discards. The corpus is the binding
constraint on the whole knowledge core, so this was not cleanup that preserved
data — it was the step that gave the detectors something to work on.

### 4a, and the check that came back the other way round

Step 4 said to check first that nothing on the phone still used the task-core
capture scope, believing `Backends.kt` already routed capture to the knowledge
core. **It does not, and never has on any shipped build.** `secondMindBaseUrl`
defaults to `""`, so `isSplit` is false and `capture` is literally the same
object as `workspace`: every thought typed on the phone posts to the task core's
`/api/v1/capture`, and deleting it as planned would have drained the encrypted
offline queue into 404s. The plan had also miscounted the surfaces at two — the
SPA Day page's quick-capture box posts to the same endpoint on session auth.

So the step became: keep the URL, the bearer token and the `capture:write`
scope, change what they write. `/api/v1/capture` writes a `Node` through
`services.capture_idempotent`, shared with `/mind/api/v1/capture` so the two
cannot drift, and the router moved from `capture/api_v1.py` to `mind/api_v1.py`
— which is what turned 4b from a migration into a deletion. No APK rebuild,
nobody logged in twice, one `/api/v1/` for one application.

**A fix that had shipped to the wrong endpoint.** Android sends `captured_at`
from both call sites — `CaptureViewModel.deliver` and `QueueDrainer.drain` — so
a thought that waited hours in the queue arrives with the time it was written;
the live endpoint's schema was `text` and `tags` only, so Ninja dropped the
field in silence. It had been found and fixed once, on the
August 14 device pass, on `/mind/api/v1/capture` — which nothing calls. The
defect stayed live on the real path for a day, and the 22 device-test captures
now in the graph carry delivery times rather than writing times as a result.

**The lesson, and it is the third time in two days** — after `/healthz` that
nothing polled and detectors that were built, green and never invoked. **Code
that exists is not code that runs, and a test that walks the wrong endpoint
proves the wrong thing**: `test_journeys.py` was posting to
`/mind/api/v1/capture` with a `mind.ApiToken`, and now walks the real route with
the real credential.

Deployed at noon as `DEPLOYED-2026-08-15/1200` (`99d48a2`), which `LIVE` points
at. Verified by 974 Django, 686 pytest, 271 frontend, 30 browser and a clean
build, then in production: the live OpenAPI schema carries `captured_at` and
returns `{public_id, captured_at}`, and an offline capture was walked from the
phone through the queue to `/mind/`. A last capture reached the Inbox after the
migration and before the deploy — "Barry tv show" — which is the gap the re-run
of `migrate_inbox` exists to close. The graph stands at 41 nodes, 19 visible to
the detectors.

### 4b — the deletion, and three things it did not cause

`/capture/`'s pages, forms, services, admin and tests are gone, with `Capture`,
`Idea` and `migrate_inbox`. Inbox and Ideas left both navs — the SPA's `SideNav`
and the Django `base.html` — and `inbox_count`, `inbox_url` and `ideas_url` left
the `/nav` payload. **`inbox_count` was the only number in that nav measuring a
backlog**, and nothing replaces it; a test now asserts that no nav key ends in
`_count` except `archived_count`, because a bare entry invites somebody to add
one and the attention policy exists to refuse exactly that.

Three things broke, and none of them were about capture:

- **`base.html` reversed `capture_inbox` and `ideas`.** Every Django-rendered
  page 500'd; the suite caught it in the first run.
- **The generated migration would not reverse.** `idea_owner_status_idx` covers
  `owner`, and unapplying `DeleteModel` runs before unapplying `RemoveField`, so
  a rewind rebuilt the table and then tried to index a column it had not
  re-added. Nothing in production would ever have reached it; the
  migration-rewind tests did. Fixed with a `RemoveIndex` first, because a
  migration nobody can back out of is worst at the moment they want to.
- **Four migration-rewind tests only rolled their own app forward** in teardown.
  Harmless for as long as every table had a live model, because the inter-test
  flush truncates by model — and fatal the instant a table had none, surfacing
  as `cannot truncate a table referenced in a foreign key constraint` in a test
  about checklist steps. They now roll the whole graph forward, which is what
  their own comment already claimed and what `accounts` had always done.

The pattern in all three: **deleting a model is a schema change, and what it
breaks is whatever quietly depended on the schema being wider than it needed.**
None was found by reading the diff.

872 Django, 672 pytest, 270 frontend, 30 browser, clean build. Deployed with
step 5 at 2030 as `DEPLOYED-2026-08-15/2030`. The pre-flight ran against
production while the models still existed, because `0008` has no reverse and
after it there is nothing left to check against: every `Capture` and `Idea` row
accounted for by a `Node` with an `inbox:` import key. Confirmed afterwards with
`showmigrations capture` — `[X] 0008_delete_idea_capture` — because that
migration runs in its own container and could fail without the play visibly
failing. `/capture/` and `/capture/ideas/` now answer 404 where they used to
redirect to a login, and the live `/nav` payload carries none of the three keys:
the two observable facts that say 4b landed.

### 5 — the URL that did not move

Step 5 was written as *move `/mind/` to the URL 4b frees*, and asking the
question directly reversed it. **`/mind/` is permanent — Vince's call**, for the
reasons `CLAUDE.md` now carries: nine routes under `/mind/` and only one is
capture, so `/capture/` would name the smallest thing in the room, against a
live PWA shortcut and every bookmark. **"Temporary" was a reason to reconsider
the name once the collision was gone, not an obligation to move.** The change
was therefore subtraction — the word came out of `clarice/urls.py`,
`mind/urls.py`, both navs and their tests, replaced by the reason it is
permanent. It also answered a question the plan had listed as beyond it: the
knowledge core's other pages stay together, under a different root from the task
core's `/app/` — two cores, two homes, one login, one nav reaching both.

### The leftovers, cleared the same day

**`/mind/api/v1/` and `mind.ApiToken`.** The knowledge core arrived with its own
`NinjaAPI` and its own `sm_`-prefixed bearer token table, so the Android app
could point at a separate Second Mind server by setting one build property.
**No shipped build ever set it, and the `/mind/` pages carry no JavaScript at
all**, so nothing had ever called it from either direction. Dropping the table
took the same pre-flight 4b took — a row would have meant a device this silently
disconnects. Production returned **0**.

**The `capture` app**, which 4b had to leave in `INSTALLED_APPS` because Django
needs an app installed for its migrations to run. With `0008` applied in
production the shell went too; no other app's migrations depended on it, checked
first because it would have been the blocker. `django_migrations` keeps eight
inert rows, deliberately — editing production's bookkeeping to tidy something
Django ignores is the worse trade.

**One test was rewritten rather than deleted, and it is the point of the whole
exercise.** `test_capture_time_zones.py` asserted that a token capture reads
"tomorrow" in the *owner's* zone — the twin of defect 2, found by asking whether
the task core's bug had a counterpart here — and it ran through
`/mind/api/v1/capture`. Deleting that endpoint would have removed the only
coverage of a behaviour that is still live; it now runs through
`/api/v1/capture` on a `PersonalAccessToken`, where `_resolve_scoped_token`
makes the same `activate_for` call. **The seam moved; the defect did not.**

One test was genuinely lost: `test_ownerless_list_removal`'s third case, that an
`Idea` survives losing the task it pointed at. It needed `Idea` in a historical
migration state, and there is no longer one — not a re-evaluated risk, a
scenario that stopped existing.

### And the rule Heron finally killed

The task core had been in maintenance since the merger was planned. **The freeze
is lifted — Vince's call, the same day.** The rule's history is the useful part:
it had been rewritten twice to survive — "until the merger", then "until the
crossover ends", on the narrower ground that `Capture` and `Idea` were retiring.
Heron deleted both. **Each rewrite found a narrower justification for a
conclusion already held**, which is the shape of motivated reasoning, and a
third would have been cargo. What replaced it is a priority rather than a
prohibition, and it lives in `CLAUDE.md`.

## After Dunlin — Release F and six unlettered lines of work, August 6–12, 2026

Six of these seven shipped outside the release structure entirely, which is the
honest reason the letters stopped carrying information; the window was tagged
**Fulmar** belatedly on August 15, with an annotation saying so. **In-app login,
the optional unlock gate and release signing** shipped on August 6 alongside
capture tags and were folded into Dunlin rather than promoted; see *Capture tags
— folded into Dunlin* below.

### Release F — opened August 7, closed August 13

Opened with the second-mind discovery pass, **Vince's call, ahead of the pain
that would otherwise have forced it**: `architecture-trajectory.md` §5 named two
candidates, this and the staging environment, and neither had fired its stated
trigger, so this was recorded as a deliberate exception rather than a trigger
pretended to have fired.

**Discovery done and the first slice shipped in full, August 10.** Reading the
models against the charter found most of the idea/reference/project/task/routine
boundary already settled by releases that were not about this at all:
`Idea.status` had already made idea/reference one model, and Dunlin and Crane 0
had settled task/project/area and routine/task. The slice was `Idea.tags`
reusing `lists.Tag`, tag carry-forward through promotion, and a plain
`related_ideas` link with no `kind` field. 856 backend tests green throughout.
Two of the brief's own assumptions did not survive contact with the code and
were corrected in the document rather than built around: `capture.Idea` had no
Ninja API at all, and `Idea` had no detail page for chips to live on, so they
render inline on the shared list.

**Closed August 13, 2026, with its subject moved out of the project.** The
second mind became its own repository, which Clarice is absorbed into rather
than the reverse. The shipped slice stays deployed; it is simply the last of
that line, since `Idea` does not survive the merger.

### The project workspace redesign — August 10

Trigger: a real navigation dead end — opening a project from the side nav only
ever routed to its parent Area, because `Project` had never had a page of its
own. [`project-workspace-plan.md`](project-workspace-plan.md) inverted the
containment, so a Project became a standalone workspace holding one or more
Areas rather than living inside exactly one. Eight slices, each its own commit,
model through browser smoke pass. 858 backend, 231 frontend, 28 browser
journeys. One gap the plan missed — nowhere to create a *new* project once
`ProjectsPanel.tsx` was gone — surfaced only while writing the browser journey.

**Two follow-ups the same day, both from using the shipped feature rather than
from planning:** a `/projects` index page, and letting a Project create a
brand-new Area rather than only reassign one. The second forced a standing-rule
change — **an Area no longer needs a first task to exist.** The follow-up's own
browser journey caught a real bug neither plan anticipated: the sidebar going
stale after completing or deleting a project. 865 / 239 / 30.

### The Bootstrap → Tailwind arc — three components, August 10–11

**Task list** (`a12a310`, `DEPLOYED-2026-08-10/1928`). Trigger: `TaskWorkspace.tsx`
flagged as "simply a mess" mid-review of the Projects redesign. The migration
plus additions approved against a reviewed mockup — due-date sort, select-mode
bulk complete/archive, removable tag pills, pill dedup. 254 / 867. Pre-existing
`ProjectJourneyTest` failures were ruled out by bisecting against `main` first.

**Agenda** (`94a6c4f`, `DEPLOYED-2026-08-10/2100`). The last Bootstrap-era
component and the app's highest-traffic page. Two real functional gaps were
found by reading the code rather than guessing: no text search anywhere on the
page, and no staleness signal, because `age_in_days` lived on Daily's and the
review's own item types rather than the shared `Task` type. Shipped with the
migration, the touch-target fix, a unified area/tag filter row replacing three
separate surfaces, search, and the staleness label; bulk actions and manual
reordering were deliberately left out as editing-shaped work belonging to the
Area page. 263 / 867. Live verification against the built bundle caught a layout
bug nothing else did — a search field collapsing to 30px for want of a
`flex-shrink:0` guard.

**Archive** (`1cf9147`, `85154a8`). The last component on `site.css`. The
migration, the same touch-target fix, and the row date switched from
`created_at` to `archived_at`, confirmed against the model's own
`CheckConstraint` rather than assumed. Because it was the last dependent,
**`site.css` and `workspace.module.css` were retired from the app entirely**,
source deleted rather than left unreferenced. 264 / 867.

**The finding worth keeping, because it was not confined to one page.** The
Archive delete dialog's buttons measured 32px against a ≥44px claim. `Button`'s
size variants top out at 36px, and no component test measures rendered layout.
Checking the other two found every `<Button size="sm">` composer and dialog
button in all three at 28–36px, despite each brief claiming ≥44px and each live
verification reporting it confirmed. Fixed in all three with an explicit height
override. **Three consecutive verifications reported a measurement none of them
had taken.**

### Android as a full client — slices 1 and 2, August 10–11

Trigger: a request for a "more comprehensive overhaul" after a design pass on
the app's previously nonexistent visual theme.
[`android-full-client-plan.md`](android-full-client-plan.md) checked the gap
first and got half of it wrong: `lists`, `daily`, `review` and `routines` expose
the same *routes* the SPA consumes but not the same *auth* — only `/api/v1/me`
and `/api/v1/capture` took the Bearer token Android carries.

**Slice 1 (Daily, read-only)** installed clean on both devices and then did not
load: the stored token authenticated Settings and got 401 from `/api/v1/day`.
Asked directly rather than patched around, the call was to design a scoped token
tier before opting more routers into `TokenAuth` — see
[`token-scopes-plan.md`](token-scopes-plan.md). 899 backend tests, deployed the
same day and verified live, with the older device's pre-existing token still
working — the migration's grandfathering.

**Slice 2 (Agenda, read *and* write)** turned out bigger than the read half.
Complete/reopen, reschedule and quick-add live on `lists/api.py`'s hand-rolled
pre-Ninja endpoints with no token concept, sitting behind Django's *real*
`CsrfViewMiddleware` that every Ninja route is structurally exempt from.
`token-scopes-plan.md` §7 traces the mechanism Ninja actually uses and ports it
by hand as a `token_or_session_required` decorator, with a field-level guard so
`agenda:write` can complete or reschedule a task but never delete one or touch
its text, tags, notes or recurrence. 918 backend, 260 Android.

**Slice 1 extended to writable** the same day: focus pin/unpin, the day's own
text, and all six routine actions, behind `day:write` and `routines:write`.
Every endpoint was already Ninja, so no CSRF porting was needed. 933 / 285.

Both verified live on the SM-S928U1 against production. **One operational
lesson: a scope-adding deploy needs a fresh login on each device**, because an
existing connection predates the new scopes. Also found and fixed: a long
action-item title left the "Pinned" badge a few pixels wide, wrapping it letter
by letter.

### The staging environment — designed August 11, deferred August 12

Next in line on the infrastructure track per `architecture-trajectory.md` §6,
and decided directly rather than guessed: a second DigitalOcean droplet, not a
second process on production's already memory-tight host, with its own database
on the existing Postgres cluster — see
[`staging-environment-plan.md`](staging-environment-plan.md).

**Designing it found a real gap before it could reach production.**
`settings.py`'s `DEBUG` had only two states and neither fit `"staging"` safely;
the decision was pulled into a tested `clarice/deployment.py::is_debug()`, the
same "a function with a test, not a branch in a config file" pattern
`monitoring.py` already used. 937 backend tests.

**Deferred the next day, before provisioning** — see that plan's §8. Nothing in
flight touched the deploy mechanism and there was no real user data to protect
from an untested migration, so the recurring droplet cost had nothing to offset.
The decisions and the `is_debug()` fix stand; the droplet waits for a trigger.

Alongside it, §6's other two "now" items closed: **local development moved onto
Postgres**, closing the gap where SQLite silently omitted a constraint
production enforces, and the droplet-swap item — done back on August 3 — was
found never to have been marked complete.

## Production verification markers, per release

The practice these record is worth more than the markers themselves: **verify
with a marker the change actually introduced, not one that merely looks
plausible.** Bittern nearly confirmed a deploy that had not happened by checking
for `Something went wrong.`, a string that predated the change.

**Bittern.** The deployed bundle carried `RequestFailed`, the class B2.1
introduced. No unapplied migrations. Sentry active with `DEBUG` false. B1's
spawned occurrence rendering with its children and no refresh. Android capture
reaching the Inbox exactly once across every network condition. Per-user time
zones discriminating between accounts at 07:00 WITA.

**Crane.** The review routes answered 401 while a made-up route answered 404;
the POST-only `/review/{day}/complete` and `/routines/{id}/enough` answered 405
to a GET; the served bundle carried "Recent weeks", "Save the review" and "Call
it enough"; `/app/review` rendered on the real account. `lists/0023` linked both
existing repeating tasks.

**Dunlin.** `/api/v1/projects` and `/api/v1/areas/1` answered 401 while a
made-up route answered 404; `/api/v1/lists/1` was gone at 404; `/lists/1/`
redirected to `/areas/1/`; the login page said "areas" and never "lists"; the
served bundle carried "No projects in this area yet." and "stay open if you
complete this" with none of the old vocabulary. `app-shell.js` on production was
byte-identical to the build the tests ran against. All six migrations applied;
`0026` converted six subtasks; ownerless areas numbered zero.

## C2 — the interface failure, and the reason it was not an interface problem

C2 was an observation task rather than work: *reassess information architecture
after B0*, on the theory that "I can't tell where things are" might dissolve
once the navigation actually rendered. **Its evidence arrived from B1's own
verification on August 2, 2026.** Setting
up one recurring parent with three children took three attempts, and each
failure was the interface rather than the person:

- A task's **Repeat** (a select, parent-only) sat directly above each subtask's
  **Repeats** (a checkbox, child-only). Near-identical words, one screen,
  opposite meanings — and setting the first to None silently hid every instance
  of the second, so the control being reached for disappeared as a side effect
  of the mistake.
- A subtask row carried two checkboxes with no visual distinction: the leading
  one completed the task, a later one governed recurrence. Having used the
  first, the row read as done with.
- Neither failure produced an error. Both looked like success.

The verdict from that session was recorded as given: the web UI needed a
complete overhaul, not adjustment.

**Closed by Dunlin, August 3, 2026 — and the verdict was only half right.** Both
defects are gone. The first dissolved *by construction* when a Checklist Step
lost its recurrence field: the interface was never redesigned to fix it, which
is the strongest evidence the thesis behind that release was right. The second
became a checkbox and a switch. **The model was the larger problem, and fixing
it removed a defect no amount of interface work would have.** The evidence above
is left as recorded rather than rewritten, because what it observed is why the
release took the shape it did.

## Capture tags — folded into Dunlin rather than promoted

**Decided August 3, 2026.** Merged onto `main` the same day, deployed August 6
in `DEPLOYED-2026-08-06/2248`. Optional tags on a capture, typed on the Android
compose screen and displayed as pills in the web Inbox. It reused `lists.Tag`
rather than a parallel model (`_resolve_tags` became public `resolve_tags` so
`capture.services` could call it), added `Capture.tags` additively, and the
Android queue carried tags through offline capture the same way it already
carried text. Triage gained no tags field, and a capture's tags did not carry
forward onto the task or idea it became — both deliberate non-goals, not
oversights. The second was closed later by Release F's first slice.

The same decision covered the rest of what the Android device-testing branch
carried in: in-app login, the optional unlock gate, and release signing wired
into the build. None of it earned a release of its own, **which is why the
letter sequence skips E.**

## Dunlin — shipped August 3, 2026

`dunlin` (`82fd591`) was tagged after production was verified. Two deploys
carried it: 00:27 EDT (`e76c200`, `DEPLOYED-2026-08-03/0027`), which took slices
1 to 8 and all six migrations in one run, and 02:03 EDT
(`DEPLOYED-2026-08-03/0203`), which took the UI brief, the carries-forward
switch, and the playbook fix below. It closed with work outstanding by decision
rather than omission, listed at the end.

### What shipped

- **Slices 1–4 — the parent–child redesign, end to end.** A subtask is a
  **Checklist Step**: its own model, no due date, no tags, cannot recur, dies
  with its parent, promotable into a real task. `lists/0025` added the table,
  `0026` converted every existing subtask — deleting the `Item` each came from,
  or auto-promoting it when it carried a due date, tags, notes or a recurrence
  the new model could not hold — and `0027` retired `Item.parent`,
  `always_recurs` and `archive_group` outright rather than leaving them dead.
- **Slice 5 — the Area vocabulary.** A `List` is an **Area** everywhere a person
  reads one: copy, `aria-label`s, JSON field and schema names, and URL paths.
  The `List` model and the `lists` app keep their names, per
  `architecture-trajectory.md` §7. The old `/lists/` paths redirect rather than
  404. No migration.
- **Slice 6 — `List.owner` non-null.** `0028` deleted the anonymous-era
  ownerless areas, irreversibly; `0029` made the column required. Charter rule 1
  — owned at birth — now holds for every model without an exception.
- **Slices 7–8 — `Project`.** Work that completes, inside an Area that never
  does. `Project.area` is required, `Item.project` additive and nullable, so a
  task keeps its Area and may *additionally* join a project. Projects are
  created and finished on the Area page; a task joins one from its own detail
  page.
- **Slice 9 — the interface brief**, plus the single fix in it that had evidence
  behind it: a checklist step's carries-forward control is a `Switch`, so the
  two questions on a step row are told apart by control type rather than by
  their labels alone.

**What it closed.** C2's recorded interface failure, both defects — see *C2*
above, which records how and why.

### What it taught

- **A word in a plan document hid a defect for two slices.** `release-d-plan.md`
  §4 predicted the two-checkbox row would be mechanical "once `is_done` is the
  only boolean on the row." It was not — `carries_forward` stayed on the row as
  a second checkbox. Slice 3's own entry called it a "toggle", and because the
  plan then read as though the problem were solved, nobody checked. **Check a
  plan's predictions against the shipped interface before writing the next plan
  on top of them.**
- **A migration that prints its evidence is worthless if the deploy discards
  it.** `0026` and `0028` printed counts precisely so that running them against
  production would be the evidence no local database could supply. The playbook
  ran migrations through `docker_container_exec`, which captures stdout into an
  unregistered Ansible result, so it went nowhere and `docker logs` never had it
  either. `0026`'s figure was recoverable by counting rows; `0028`'s is gone
  permanently. Fixed the same night in `a6550e4`, and exercised on the second
  deploy while the stakes were a no-op.
- **The nullable-to-required cost is asymmetric, and one slice's experience
  reversed the next slice's design.** Slice 6 spent an entire slice paying it on
  `List.owner`: an audit, a destructive migration, sixteen tests. Slice 7 then
  had to choose for `Project.area`, and `release-d-plan.md` §3 had recommended
  nullable on reversibility grounds — reasoning that inverts once the direction
  is named, since required→nullable is a bare `AlterField` with no data work.
  **The permissive default is the expensive one to undo.**
- **The local database was not evidence, exactly as the plan said.** Local
  development held three lists and zero ownerless rows; production held nine
  areas. Both migrations were written for the general case rather than the
  observed one, and that was right for reasons only visible afterwards.
- **A contract rename lands wider than the plan scopes it.** Slice 4 found
  `daily` and `review` each carrying their own hand-rolled `parent` breadcrumb
  rather than reusing `lists.serializers.serialize_item`; slice 5 found the same
  split for `area_id`. `daily` got the rename for free; `review` needed it
  applied separately. **That difference is the whole argument for the shared
  serializer.**
- **A feature can be write-only if you only build the surfaces that create it.**
  Slice 8 shipped project assignment, and `project` reaches exactly three
  frontend files — not the Agenda, which already renders an area pill and has
  room for a second, nor the Daily Page, the review, or the Archive. Someone can
  put a task in a project and never see that fact again. Found while writing
  slice 9's brief.

### Closed with work outstanding

- **Two migration counts are lost**, per the second lesson above.
- **`ui-second-pass-plan.md` steps 2 to 4 were blocked on evidence, not effort**
  — a project is invisible everywhere a task is worked, and Projects have no
  place in navigation, but both findings came from reading source where C2's
  came from a person failing a real task, and production held zero projects. An
  observational sitting on August 3 confirmed them; F1–F5 all shipped by
  August 6.
- **The vocabulary half of Crane 0** was still deferred at Dunlin's close. It
  had been blocked on knowing what a subtask is, which Dunlin answered.

## Crane — shipped August 2, 2026

`crane` (`e0acf05`) was deployed at 20:05 EDT and marked by
`DEPLOYED-2026-08-02/2005`. Two deploys carried it: 17:54 EDT, which took Crane
0a, 1 and 2 in one run of ten migrations, and the last one, which took Crane 3's
four. The tag went on after production was verified rather than alongside the
deploy, which is the correction Bittern's own record asks for. It closed with
work outstanding by decision rather than omission: the remainder of Bittern's
carried-in checklist, most of which this deploy finally unblocked.

### What shipped

- **Crane 0 and 0a — the repetition domain.** A design brief settling routines,
  targets and occurrences, plus the one half built immediately:
  `RecurringCommitment` and `Item.commitment`, so a recurring task's occurrences
  form a series rather than a chain of rows whose only connection was a matching
  text string. Its backfill linked both repeating tasks in production. The
  vocabulary half — moving `text` and `recurrence` onto a real template — went
  to release D with the parent–child redesign it depends on.
- **Crane 1 — the Daily Page**, in seven slices: a written day, the agenda
  embedded rather than copied, capture, a durable Daily Focus whose
  `released_at` distinguishes a decommitment from an unfinished commitment, the
  Personal Compass, the home surface with a preference to opt back out, and a
  phone-viewport pass.
- **Crane 2 — routines and task age**, in five slices: `Routine` and
  `RoutineOccurrence` with lazily created periods and snapshotted targets,
  correction and skip as distinct statements, routines on the day, pausing that
  keeps what already happened, and how long a task has been waiting said without
  reproach.
- **Crane 3 — the weekly review**, in ten slices: what a week finished, planned
  and made of it, its own words and what is still waiting, a dated review record
  that stamps the figure it concluded from, one explicit decision at a time with
  no bulk reschedule anywhere on the surface, habit performance over the periods
  a week actually asked of, a paused week that says so, a satisfied-but-partial
  close that is not a skip, four weeks of context, and a phone pass.

### What it taught

- **A slice list hides a missing surface unless you look for one.** It had
  happened twice — the Daily Page reachable only by typing its URL until slice
  6, routine creation with no surface at all until Crane 2 slice 3 — so Crane
  3's list was read back for that specific failure before any code was written.
  It found three: the navigation entry, the way to reach the week *before* this
  one, and a control for the new partial close. Reading the list for a known
  failure mode is cheaper than a slice discovering it.
- **A test can be wrong about the world rather than about the code.** Four times
  in this release: an assertion that the week of July 27 was not the current
  one, made on a Sunday inside it; a British date order asserted against a
  locale-following formatter; an unanchored `/all/` matching "Call the bank";
  and a straight apostrophe asserted against the typographic one the application
  renders. Each looked like a defect for as long as it took to read it.
  `principles.md` says to diagnose before editing either side; the corollary is
  that the test is a suspect too.
- **The schema could not answer a question the plan asked.** Slice 9 needed
  "before the account existed" and `accounts.User` carries no creation timestamp
  at all — no `date_joined`, no `created_at` — which a test found by asserting
  against one that was not there. Adding the field would have meant defaulting
  three real accounts to today and marking their whole history prehistoric, so
  the line was drawn at the owner's first trace instead: earliest day written,
  task made, routine kept, thought captured. The better question, arrived at by
  being unable to ask the worse one.
- **A rule emerged that no single slice set out to make.** Released pins,
  skipped periods and periods closed as enough all leave a denominator — three
  decisions taken a slice apart that turned out to be one: *a deliberate
  decision leaves the denominator; only what merely elapsed stays in it.* It is
  written that way in the code rather than as three subtractions, so the next
  decision-shaped outcome inherits it.
- **A guard that has never been seen red is a claim, not a check.** Three passed
  on their first run this release — that nothing in the review mutates a task,
  that the pause backfill seeds what it should, and that the page does not
  scroll sideways at 375px. Each was made to fail on purpose before being left
  alone.
- **Running the tests does not migrate the development database.** The first
  browser check of the review record failed with `no such table` on a suite
  green for an hour, because tests build their own database and `migrate` had
  never been run against the dev one. The page said "Couldn't reach Clarice"
  with a retry rather than rendering blank — B2.1's fix doing precisely what it
  was built for, an unplanned confirmation of an earlier release from a mistake
  in this one.

## Bittern — shipped August 2, 2026

`bittern` (`359a7e3`) was deployed at 00:35 EDT and marked by
`DEPLOYED-2026-08-02/0035`. Three deploys carried the release: 11:56 EDT on
August 1 (`fed210b`), 21:51 EDT that evening, and the last one, which was the
only one to carry B2.1 and B2.2 — their commits landed after the second deploy,
and an earlier claim that Bittern was already live rested on `/contact/`
returning 200, which proved B3 and nothing else.

It closed with work outstanding by decision rather than omission: five
after-deploy checks never run, three infrastructure confirmations owed, and
several Android gaps. All were carried into Crane.

### What shipped

- **A native Android capture client** (`android/`, M1–M5). Personal access token
  authentication, capture online or offline, a durable encrypted queue drained
  in the background, a share target, and idempotent writes that cannot duplicate
  a thought. 143 JVM tests and 16 instrumentation tests.
- **Per-user time zones.** Left the deferred list the day both halves of its
  trigger fired: a second active user in Indonesia, and a digest delivering at
  03:00 Eastern.
- **Web session and state gaps closed** — B1's spawned recurring subtasks, B2's
  SPA logout, B2.1's failure states, B2.2's browser smoke coverage.
- **Branded email and a contact path** (B3), and **production error monitoring**
  (B4).
- **B0** — the missing side navigation, diagnosed and fixed; see below.

### What it taught

- **A phone was the first thing to discover a production contract gap.** The
  Android client's first real connection failed because the bearer-auth
  `/api/v1/me` endpoint was still only on `main`. The token was always valid.
  Check the deployed OpenAPI schema before pointing a client at an endpoint, not
  after. B0.1 exists because of this.
- **Verification tooling can lie.** The script written to prove production's
  duplicate protection matched `"id":[0-9]*` against an API that renders
  `"id": 2`, extracted nothing from either response, compared the two nothings,
  and announced that production was broken — over evidence in its own output
  showing it working. Assert on values you have proven you can parse.
- **Rebuilding a state object silently drops fields.** Twice in one evening: a
  pending count left standing over an emptied queue, and a keyboard preference
  reverting on every capture. Neither would ever be reported as a bug; people
  would just quietly stop trusting the app.
- **Some defects only exist on hardware.** Background delivery worked on its
  first real attempt, and the count on screen did not update, because a screen
  cannot see a background drain. Every unit test asserting that count was
  correct.
- **A marker has to be something the change introduced.** Checking whether B2.1
  was deployed, `Something went wrong.` was found in the served bundle and
  nearly taken as proof — it predates B2.1 by months. `RequestFailed`, which
  B2.1 actually added, was absent. The weaker check would have confirmed a
  deploy that never happened, and the same instinct produced a premature
  "Bittern is live" in these documents an hour earlier.
- **`state: latest` on an infrastructure package** means a routine deploy is
  willing to upgrade — and so restart — the thing running the application. The
  "Install docker" task looked hung on three separate deploys and was cancelled
  each time; it was never hung, just resolving upgrade candidates on every run.
  Fixed in `fed210b` with `state: present` and `cache_valid_time: 3600`, and the
  commands to check before cancelling an apt task are in `CLAUDE.md`.
- **Isolating one half of a store's identity is isolating neither.** The
  instrumentation tests parameterised the Keystore alias but not the preference
  file, so running them deleted a live token off a real phone.

## Albatross — shipped July 31, 2026

`albatross` (`f5ddb85`) was deployed at 22:24 EDT and marked by
`DEPLOYED-2026-07-31/2224`. It carried seven migrations, taking the schema from
53 to 60 without changing existing rows.

### Platform and production work

- Replaced the task UI with a React Router/TanStack Query SPA backed by a Django
  Ninja `/api/v1/` contract and generated TypeScript types.
- Moved production from bind-mounted SQLite to managed Postgres.
- Added GitHub Actions: Django tests against Postgres, frontend tests and builds
  on every push and pull request.
- Restricted the application to a dedicated Postgres database user, proved the
  backup/restore path against a cloned managed database, and closed the database
  firewall to the application droplet. Grants are not ownership; Django
  migrations required correcting table ownership.
- Added the daily-digest cron job, verified by dry run. Its first unattended
  fire was 07:00 on August 1, 2026; "runs as root from cron on a schedule" has a
  failure mode that "prints to stdout when I run it" does not, so it was not
  proven until that run was checked.
- Added self-service password reset, including live validation of lockout
  behaviour, and production-ready static asset handling through Docker,
  Gunicorn, WhiteNoise, nginx and Ansible.
- Added an adversarial per-user isolation suite, including id-based task/list
  and subtask cases.

### Task and agenda work

- Added archive/restore state handling and snooze presets.
- Added notes as plain text on task detail.
- Added one-level subtasks with duplicate protection, ordering, ownership
  isolation, archive/restore, completion, recurrence, and undo behavior.
- Added `always_recurs` to decide which subtasks return with a recurring parent,
  plus the follow-up fix that prevents completed children from being orphaned
  when their recurring parent archives.
- Added persistent SPA navigation in source. Its absence in production was
  Bittern B0 — the deployed bundle was never the problem. Direct Inbox and Ideas
  links on the Agenda workspace mitigated it only once the current bundle was
  deployed; they did not replace B0's diagnosis.

### Capture and account work

- Added Capture: a zero-friction, owner-scoped inbox for untriaged thoughts, and
  triage into a task, an Idea, or a discarded record, with undo. The planned
  two-week usage checkpoint was dropped as a release gate — the triage model had
  enough direct product conviction to ship.
- Added Ideas with exploring/reference states, notes, edit/delete, and promotion
  to a task.
- Added personal access tokens and `POST /api/v1/capture` for non-browser
  capture clients, plus account themes and daily-digest preferences.

Track A (infrastructure and public-readiness, A0–A6) and Track A Next (the
task-model queue) both closed here. Track A Next's one deliberately unscoped
consequence — a spawned recurring task not serializing its copied subtasks, so
they appeared only after a refresh — was closed as Bittern B1 on August 1, 2026.

## Bittern B0 — the missing side navigation, diagnosed August 1, 2026

B0 existed to decide between two causes: a stale or mispackaged frontend bundle,
or a current bundle failing at runtime.

**The artifact was never the problem**, and the stale-artifact branch was closed
on read-only evidence gathered before any redeploy. The served
`app-shell.b94af7d63d1b.js` was what the deployed `staticfiles.json` mapped
`app-shell.js` to, so it was what `app_shell.html` referenced, and its
`Last-Modified` was the `DEPLOYED-2026-07-31/2224` deploy; it carried
every navigation string and, correctly, no `Log out`, since B2 was unbuilt; the
served `app.css` was byte-identical to a local build; and `AppLayout`, `SideNav`
and `sidenav.module.css` were unchanged between `f5ddb85` and `main`.

**The cause.** `AppLayout` wrapped `SideNav` in a `<details>` that nothing ever
opened, while `sidenav.module.css` hid its `<summary>` unconditionally. Above
the breakpoint the nav was sealed inside a closed disclosure with no handle to
open it — the source comment asserted "above it the nav is always open," but no
code implemented that. A closed `<details>` has its contents skipped, so the
element collapsed to zero height. Measured on the live page:

```text
detailsBox: 210x0     <- the empty gutter the user could see
navBox:     210x306   <- a skipped subtree keeps its geometry
shellCols:  210px 1814px
```

Firefox does not paint skipped content, so the column was simply empty. Chromium
148 still paints it, which is why the same page looked correct in Edge and on a
Chromium phone, and why the defect shipped.

**Why no test caught it.** `SideNav.test.tsx` renders the component directly,
never inside the `<details>`, and jsdom has no paint model in any case — the
condition is invisible to unit tests by construction. `AppLayout.test.tsx` now
asserts the invariant that was violated: above the breakpoint the disclosure is
open, and stays open across navigation. Proving what a person actually sees
needed B2.2's browser-level coverage.

**The fix, and its verification.** The layout holds the disclosure open above
the breakpoint via `matchMedia` rather than depending on how an engine treats a
closed one, and only closes on navigation when narrow; with the patch the
disclosure's own box goes from `210x0` to `210x145`, matching its content.
Deployed at 11:56 EDT on August 1; the served bundle rotated to
`app-shell.98590f71d7af.js`, byte-identical to a local build of the same source
and carrying the fix's own `min-width: 761px` breakpoint. An authenticated visit
confirmed the nav down the left above the cutoff, collapsing into the ☰ menu
below it. B0 closed.

**A false trail worth keeping.** The first reproduction reported the nav as
"visible" in every browser, which discarded the correct hypothesis for most of
the investigation. The instrument was wrong: it tested
`getBoundingClientRect().width > 0 && height > 0`. **A layout box is not paint.**
Content skipped by a closed disclosure keeps its geometry, so the probe answered
"visible" for something invisible on screen, and the user's own report was
trusted less than a faulty measurement. The signal that finally settled it was a
container measuring `210x0` while its child measured `210x306` — a contradiction
that can only mean skipped content.

## Decisions and lessons retained from the work

### Product decisions

- Capture never forces categorization at entry time; triage decides whether a
  thought becomes a task, an Idea, or nothing worth keeping.
- An Idea is not a task without a due date. It has a distinct lifecycle and can
  later promote into a task, carrying its notes with it.
- The task UI is now SPA-only. Capture and account surfaces can remain
  Django-rendered where that is the better fit.
- The agenda is a date-based cross-list view; lists are navigation targets, not
  agenda filters in the persistent navigation.

### Engineering lessons

The ones that are not already stated in a release section above:

- A deployment task is not proven until it has run against production.
- Test against the same database family and relevant version as production.
- A clean hard refresh does not prove the deployed frontend image contains
  current source. Inspect the served bundle when UI source and production
  disagree.
- Markup must not depend on how an engine renders a closed `<details>`. Engines
  differ and are still converging; a layout that only works in the browser it
  was built in will look correct to whoever built it.
- Every id-taking surface requires direct per-user isolation tests, not just
  trust in a general ownership convention.

## Release conventions

Releases use alphabetic bird names, and a release receives three tags — `LIVE`,
`DEPLOYED-<date>/<HHMM>` and the bird codename — after it is verified in
production. What each tag means is in `CLAUDE.md`; the letter sequence and which
bird holds which letter are in `roadmap.md` under *Release practice*. Neither is
restated here. A letter is never reused: a follow-up production release receives
the next bird name, even if it immediately corrects the last.
