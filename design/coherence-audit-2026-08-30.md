# Coherence audit — August 30, 2026: the task core

**A record, and a repair list.** It follows
[`code-review-2026-08-16.md`](code-review-2026-08-16.md) and
[`code-review-2026-08-21.md`](code-review-2026-08-21.md) in describing one pass
at one state of the tree, so it cannot go stale; unlike them it was asked for by
a **feeling** rather than by a risk model, and the feeling is the finding.

**Reviewed at:** `main` at `f3afd01`, working tree clean.

**Asked for by Vince, August 30, 2026**, in these words:

> *the superlists core was developed more in bits and pieces so its not really
> coherent*

**The first answer offered was wrong and is worth recording.** Asked what *more
useful* meant, this audit's author first went to
[`product-stories.md`](product-stories.md) and found the task core at *works*
for every Do/Adjust/Decide journey — S2 through S12 — and concluded the score
had nothing left to say. That was true and useless. **The score measures
journeys end to end and is blind to the seams inside them**, because a journey
that completes by two different mechanisms still completes. Nine findings
below; the score sees none of them.

**These are not production defects.**
[`commercial-blueprint.md`](commercial-blueprint.md) Part 1 stays the sole
authority for that list and it is currently empty. Nothing here loses data or
exposes anything.

---

## What was actually run

**Nothing.** This is reading only, per `principles.md`. No suite was executed
and no command was run against a database while producing the findings; every
one below is a `file:line` that resolves. The repairs that follow it are a
different matter and carry their own evidence.

---

## The one-sentence diagnosis

**Every seam is between something built before there was a pattern and
something built after.** `/api/v1/`, the generated contract and
[`modules.md`](modules.md)'s charter all arrived after `Item` and `List`
already had working plumbing, and nothing went back. Money — the newest
domain — is the best-wired thing in the task core; the task, which the
application is named for, is the worst.

---

## Findings

### F1. Two sibling cards, two architectures

The Agenda's sidebar holds **"New area"** and **"New project"** next to each
other.

| | New area | New project |
|---|---|---|
| Mechanism | `<form method="post">` to a Django view, full page reload — [`AgendaWorkspace.tsx:899`](../frontend/src/AgendaWorkspace.tsx) | typed mutation + client-side navigate — [`AgendaWorkspace.tsx:184`](../frontend/src/AgendaWorkspace.tsx) |
| Endpoint | `POST /areas/new` (Django form view) | `POST /api/v1/projects` |
| First child required | **yes** — `text` is `required` ([`forms.py:20`](../src/lists/forms.py)) | no |
| On validation failure | a standalone Django page outside the SPA, whose only way back is a "Cancel" link to the dashboard ([`new_list_form.html`](../src/lists/templates/new_list_form.html)) | inline error |

`new_list` is `@require_POST` ([`views.py:67`](../src/lists/views.py)), so that
template is **only ever seen as an error state**.

**There is no `POST /api/v1/areas`.** The only API path that makes an Area is
`POST /projects/{id}/areas`, which cannot make a standalone one.

**And the domain layer is not the problem.**
[`services.create_area`](../src/lists/services.py) already exists, already takes
`project=None`, and its own docstring says *"create_list_with_item's first-task
requirement was never a domain rule"*. The split is entirely in the surface.

### F2. Three write paths, three clients

| Path | Client | What goes through it |
|---|---|---|
| `/api/v1/` — Ninja, typed, generated contract | `apiV1` | Money, projects, areas (read/rename/delete), review, day, routines, nav |
| `/api/` — hand-rolled [`lists.api`](../src/lists/api_urls.py) | [`api.ts`](../frontend/src/api.ts), hand-written | **every task write**, checklist steps |
| Django form POST | plain `<form>` | area creation (F1) |

`/api/v1/` has exactly one task endpoint —
`GET /tasks/{item_id}` ([`api_v1.py:1193`](../src/lists/api_v1.py)). Create,
rename, due date, priority, move area, tags, recurrence, cadence mode, notes,
lead days, bill, status, delete, reorder and all six checklist operations go
through the hand-rolled path. The code already says so, at
[`api_v1.py:1102`](../src/lists/api_v1.py): *the write actions the Agenda page
performs live on the hand-rolled lists.api views*.

**The consequence is not tidiness.** `dump_openapi_schema` +
`pnpm generate:api` + the build's `tsc --noEmit` — the mechanism `CLAUDE.md`
describes for keeping the SPA honest against the schema — **covers Money
completely and the core noun not at all.**

**What this finding did not say, and should have**: the SPA is not the only
client of that hand-rolled path. `android/` reads urls out of the agenda
payload and posts to them, which is why repairing this became
expand–migrate–contract rather than a replacement. See increment 2 below.

### F3. What you can do to a task depends on which page you met it on

| Surface | Task mutations available |
|---|---|
| `/tasks/:id` detail | 11 field edits + checklist — **not delete** |
| Area (`TaskWorkspace`) | create, reorder, text, due date, recurrence, tags, status |
| Agenda | create, due date, status |
| Day | due date, status |
| Archive | status, **delete** |

The subsets are not nested, they are arbitrary. Priority, notes, move-to-area,
lead days, bill and cadence mode are detail-only.

**A task can only be deleted from the Archive** —
[`ArchiveManager.tsx:106`](../frontend/src/ArchiveManager.tsx) is the only
`deleteTask` call site in the tree. So removing a task means archiving it first
and then finding it again, and the page that can change eleven of its fields
cannot remove it.

**Why, found while repairing it**: not a missing button. `GET /tasks/{id}`
excluded archived tasks and `delete_archived_item` refuses anything that is
not archived, so **the only tasks the page could show were the only tasks that
cannot be deleted.** Two correct rules, one hole between them.

**And this table is the wrong instrument for the other thing that was wrong.**
It counts what each surface can *do* to a task; it cannot see that the detail
page could not *show* an unfiled one, which had been true since `Item.list`
went nullable on August 14, 2026 and rendered `Loading…` for ever. A matrix of
verbs has no row for a task that never arrives.

### F4. The page holding almost every capability is reachable from two of five surfaces

The Day links to it with a plain `<a href>`
([`DayRoute.tsx:216`](../frontend/src/app/routes/DayRoute.tsx)). The Agenda
links to `task.edit_url`
([`AgendaWorkspace.tsx:550`](../frontend/src/AgendaWorkspace.tsx)), which is a
Django view that redirects to the same SPA path
([`views.py:89`](../src/lists/views.py)) — two round trips to reach a route the
client router already has. **The Area page and the Archive have no route to it
at all.**

This project has already written the rule, in
[`ViewNav.tsx:47`](../frontend/src/app/ViewNav.tsx): *"A route reachable from
exactly one other page is not the same as a surface."*

### F5. Three vocabularies for two objects

| Object | Model | UI | URL | Payload key |
|---|---|---|---|---|
| container | `List` | "Area" | `/areas/` | `list` — [`api.ts:118`](../frontend/src/api.ts) sends `{ list: listId }` to move a task |
| commitment | `Item` | "task" | both | — |

Both spellings sit in one file: `/api/areas/<id>/items/` two entries above
`/api/tasks/<id>/checklist-steps/`.
[`api_urls.py:6`](../src/lists/api_urls.py) already names it — *"Two
vocabularies in one path is untidy"* — and defers it to avoid two renames in
one commit. **The deferral is honest and the trigger is nameable**: it clears
the moment task writes move onto `/api/v1/`, because that is the rename.

### F6. The second-factor enrolment page has no front door

`/accounts/security/` — shipped as `petrel`, all four increments of
`admin-mfa-plan.md` — is linked from **exactly one place in the tree**:
[`verify.html:69`](../src/accounts/templates/accounts/verify.html), the
challenge page you only reach **if you already have a device**.

Preferences links to password change and access tokens
([`PreferencesRoute.tsx:308`](../frontend/src/app/routes/PreferencesRoute.tsx))
and not to this. A person who wants to *turn on* a second factor has to type
the URL.

**This is `principles.md`'s *built and dark* rule in its mildest form** — the
page works and one caller reaches it — but the caller is the one population
that does not need it.

### F7. A signed-in person still has no support path

The Contact link sits in the **logged-out branch** of the app bar
([`_app_bar.html:110`](../src/lists/templates/_app_bar.html)), with a comment
correctly explaining why it must be there. Nothing puts it in the other branch.

[`roadmap.md`](roadmap.md)'s *Support for people who are signed in* already
says the promoter for this fired — B4, production error monitoring — *"and
nobody noticed"*. It has been promotable rather than deferred since then.

### F8. Routines can only be met inside somebody else's page

Confirmed rather than re-found: [`modules.md`](modules.md) already records that
`routines` appears in the SPA route table, `ViewNav` and `SideNav` zero times.
**What this audit adds is that the charter's reading survives contact**: there
*is* a create form, folded into the Day page
([`DayRoute.tsx:612`](../frontend/src/app/routes/DayRoute.tsx)), and the API
carries log, skip, enough, pause and resume. So the zero rows are **evidence of
no demand rather than of no access**, which strengthens the input-ratio refusal
instead of undermining it.

**No repair proposed.** Recorded so the next person to notice the missing nav
entry finds the answer rather than the question.

### F9. The file layout is a fossil of the build order

`TaskWorkspace`, `AgendaWorkspace` and `ArchiveManager` sit at
`frontend/src/`; every other route component lives in `frontend/src/app/routes/`.
Nothing depends on it. Recorded because it is the cheapest possible evidence
for the diagnosis at the top, and because moving them is a rename nobody should
do in the same commit as behaviour.

---

## What is coherent, in fairness

An audit that only finds fault is one nobody can calibrate against.

- **The app bar and `ViewNav` are the best-reasoned things in the tree.** The
  two-level split — bar says which *core*, sub-nav says which *surface* — is
  stated, defended and consistently applied, and the placement of Search
  deliberately outside the Cores nav is the kind of decision most codebases
  make by accident.
- **Money is fully typed end to end**, and reads *works* in
  [`module-score.md`](module-score.md).
- **The Review page is 1,927 lines and is not a seam.** One surface, one API,
  every section documented. That is a file-size question, and a different one.
- **`services.py` is in better shape than the surfaces that call it** — F1's
  repair is an endpoint, not a domain change.

---

## The repair list

**One write path** subsumes F1, F2, F5 and most of F3–F4. Ordered so each
increment is provable on its own and the cheap ones come first.

- ~~**0a. A front door for the second factor**~~ — F6. **Done August 30,
  2026.** Preferences links `/accounts/security/` beside password and
  tokens.
- ~~**0b. A support path for signed-in people**~~ — F7. **Done August 30,
  2026.** Contact is in both branches of the app bar; the form stops asking
  somebody with a session who they are, and the rate limit is keyed on the
  account rather than the address.
- ~~**1. `POST /api/v1/areas`, and retire `new_list`**~~ — F1. **Done
  August 30, 2026.** Both cards are mutations, the first-task field is gone
  from the Agenda's, and `new_list` with its view, url, form and template is
  deleted. **The estimate it was sequenced to produce**: two callers, one
  endpoint, four test files, and the type check caught a name collision the
  moment the client was regenerated — which is increment 2's whole argument,
  in miniature.
- ~~**2. Task writes onto `/api/v1/` as a typed router; retire `api.ts`**~~ —
  F2. **Done August 30, 2026**, in three commits: the typed router and the
  client, `lists/api.py` cut from 543 lines to 208, and the Kotlin moved over.
  `api.ts` is a wrapper layer over `apiV1` rather than a second client; its
  hand-rolled `fetch`, envelope, `ApiError` and CSRF header are gone.

  **This increment found the thing the audit had missed, and it changed the
  shape of the work.** F2 said *retire the hand-rolled path*, and that could
  not be done: the shipped Android build reads `url` off every task in the
  agenda payload with `getString`, so removing it breaks the agenda *screen*
  rather than only its writes — and no signed release can replace that build,
  because `android-release-signing-plan.md`'s keystore does not exist. **The
  audit was written by reading the task core and never looked at `android/`**,
  which is exactly the seam-crossing this document exists to notice, committed
  by the document itself. `CLAUDE.md` already carries the general form — *a
  seam that is not switched on is not a seam; check the build configuration* —
  and this is its mirror: **a caller you did not look for is still a caller.**

  So it became expand–migrate–contract, which is what `principles.md` asks
  for. What is left of `lists/api.py` is a **declared** compatibility surface
  with a named trigger, rather than an undeclared second architecture: two
  views, two fields, no `DELETE`, and a docstring saying what retires it.

  **Its retirement is now gated on one thing that is not code** — a signed
  Android release. When that lands, `lists/api.py`, `lists/api_urls.py`, the
  `/api/` mount and `TaskOut.url` go together.
- ~~**3. One task editor, reachable client-side from every surface; delete
  lives with the task**~~ — F3, F4. **Done August 30, 2026.** All four
  surfaces link client-side; `edit_url` and `lists.views.edit_item` are
  deleted; an archived task has a page for the first time, carrying Restore
  and Delete permanently behind a confirmation.

  **The delete half turned out to be a different repair than F3 described.**
  F3 said *the page that can change eleven of a task's fields cannot remove
  it*, which read as a missing button. The actual cause was one line up:
  `GET /tasks/{id}` excluded archived tasks, and `delete_archived_item`
  refuses anything that is not archived — so the page could not offer delete
  because **the only tasks it could show were the only tasks that cannot be
  deleted.** The two rules were individually right and jointly made a hole.
  Nothing about the domain changed to close it.

  **It also turned up a production defect this audit had walked straight
  past.** `Item.list` became nullable on August 14, 2026 and this page's render
  guard still required an area, so an unfiled task rendered `Loading…` for
  ever. F3 counted what each surface could *do* to a task and never asked
  which tasks each surface could *show* — and both gaps found here were of the
  second kind. **An affordance matrix is a table of verbs, and it cannot see a
  missing row.**
- **4. Finish the `Item` → task rename in the URL layer** — F5. **Half done
  August 30, 2026 and the other half is refused.** The new endpoints say
  `tasks` and `area_id` throughout, so the rename landed where it could be
  free. The two surviving legacy paths keep `items` and cannot be renamed:
  they are frozen by a shipped binary, and renaming them is precisely what
  would break it. ~~Gated on 2 by `api_urls.py`'s own reasoning.~~ That
  reasoning — *finishing the second rename here would put two renames in one
  commit* — expired when increment 2 removed everything else from the file.

**Increment 1 was deliberately sequenced before 2** as the smallest complete
instance of the same pattern — one endpoint, two call sites, one retirement —
so that the cost of 2 is estimated from a landed example rather than from this
document.

**What the estimate was worth, measured.** Increment 1 predicted the *shape*
correctly — one endpoint, its callers, a retirement — and every part of that
held. What it could not predict was the constraint, because increment 1's
endpoint had no clients and increment 2's had one nobody had counted. **The
lesson is not that estimating failed; it is that the estimate and the audit
were drawn from the same blind spot**, so agreeing with each other proved
nothing. A second client is the kind of fact that has to be looked for
directly.

---

## Where the facts live

This file owns **nothing**. It is a dated observation, like the two code
reviews. If a finding here becomes work, it becomes work in
[`roadmap.md`](roadmap.md); if it becomes a defect, it becomes one in
[`commercial-blueprint.md`](commercial-blueprint.md) Part 1; if it changes what
a surface must satisfy, that is [`modules.md`](modules.md)'s. **The repair list
above is the exception and is deliberately kept here**, in the shape
`code-review-2026-08-21.md` used: struck as each lands, so the file becomes a
pure record when the last one does.
