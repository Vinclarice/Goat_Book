# The second mind — discovery pass

Vince · brief · written August 7, 2026

## 1\. Trigger, stated honestly

`roadmap.md`'s Reference/Idea search candidate names its own promotion
condition: "enough retained material that finding something again is a felt
problem rather than an anticipated one." That has not happened. There are
effectively no Ideas of substance in production, and
`daily-operating-system-vision.md` is explicit that the discovery pass
should precede the search work regardless — so the trigger for *search*
not having fired does not block *this*.

This is not that trigger firing retroactively. It's Vince choosing to open
Release F with the definitional work now, ahead of the pain that would
otherwise force it — the same kind of call `ui-second-pass-plan.md` §4
step 3 made when it asked directly rather than waited for more evidence.
Recorded as a deliberate choice, not a discovered need, because this project
does not quietly rewrite "not yet" into "now" without saying so.

## 2\. What the discovery pass turns out to already be answered

The vision document's second\-brain section asks to "define the boundary
between an idea, reference, project, task, and routine" before more
features ship. Reading the current models against
`architecture-trajectory.md` §4's charter — **a concept earns its own
model when it has a different life cycle, not when it has a different
name** — finds most of that boundary already settled, as a side effect of
releases that were not about this at all.

- **Idea vs. reference.** Already one model. `capture.Idea` carries a
  `status` of `exploring | reference | promoted` rather than two tables —
  its own docstring gives the reason: "an idea I want to explore" and "a
  concept I want to be able to find again" are the same shape of object,
  differing only in lifecycle stage. The charter test agrees: same fields,
  same queries, no different life cycle. Nothing to design here.
- **Idea vs. task.** Already settled, and has been since before Dunlin.
  `Idea.promoted_task` is a one\-way FK; promotion is one\-directional and
  irreversible in the model (an Idea does not un\-promote), and a promoted
  Idea's text stays put rather than migrating — `Idea` is `text`, `notes`,
  `status`, `created_at`; nothing about it changes shape once a task exists
  downstream of it.
- **Task vs. project vs. area.** Settled by Dunlin under this exact charter
  test, recorded in `lists/models.py`'s own `Project` docstring: "a project
  earns its own model against a List because it has a different life
  cycle, not a different name." Not open.
- **Routine vs. task.** Settled at Crane 0: a routine measures repeated
  practice toward a target; a task is discrete and either done or not. Two
  tables, not open.

So the boundary work `daily-operating-system-vision.md` worried would need
a dedicated pass mostly doesn't, anymore. That's worth recording as a
finding in its own right — four releases of unrelated work already answered
it as a byproduct of taking the charter seriously each time.

## 3\. What's actually still undefined

Two questions, and they're narrower than "define the domain":

**3a. Does a relationship between two ideas earn its own model?**
Apply the same charter test. A "related idea" link has no due date, no
completion, no status of its own, produces nothing worth a snapshot, and
doesn't recur. By the charter's own rule — "when the answer is no, the
concept is a field, a status, or a word in the interface" — this is not a
model. It's a plain link. The vision document already argues past this
question and shouldn't be re\-litigated: ship a manually selected link,
render it as an ordinary chip, and let real use decide what "related"
usually turns out to mean before naming it. Deciding that meaning up front
is exactly the kind of decision `principles.md` says to defer until
evidence exists to justify it.

**3b. Are links and sources plain text or structured data?**
Currently, unambiguously plain text, everywhere. `Idea.notes` is a
`TextField`; `Capture.text` is a `TextField`; Android's share target
(`bittern-plan.md` M5) already produces "a headline plus a URL" as one
string, deliberately, because a subject already contained in the body isn't
repeated. There is no `url` or `source` column on anything in this domain.
This question has no evidence behind it yet — no corpus of captured links
to look at and ask what a structured field would actually need to hold —
and per `principles.md`'s own instruction to measure before optimizing, it
should stay plain text until that evidence exists rather than be designed
from the shape of one Android share intent.

**3c., named so it isn't silently assumed:** a capture's tags do not carry
forward onto the Idea or task it becomes. `capture-tags-plan.md` §3 named
this as the real follow\-on and explicitly left it "for whichever of
Reference/Idea search or the receiving\-side work in `roadmap.md` picks it
up." This is that pickup. Idea itself has no tags field at all today —
`capture.Idea` carries no `ManyToManyField`, unlike `Capture`, which gained
one in the same brief.

## 4\. The first slice

Thinnest possible, per `principles.md`'s vertical\-slice and reversible\-decision practices — additive, reuses existing precedent twice over, and answers nothing that isn't already decided above. Three independent, additive changes; order matters only in that 4.1 has to land before 4.2 has anything to carry.

### 4\.1 `Idea.tags`

- **Model:** `tags = models.ManyToManyField("lists.Tag", blank=True, related_name="ideas")` on `capture.Idea` — the same field `Capture.tags` already is, same app\-boundary rule (`capture` depends on `lists`, never the reverse).
- **Migration:** additive, in `capture/migrations/`. Every existing Idea keeps zero tags.
- **Service:** wherever an Idea is created or edited directly (not through promotion — that's 4.2) gains an optional `tags` argument, resolved through `list_services.resolve_tags` exactly as `create_capture` already does.
- **API contract:** `IdeaOut.tags: list[str] = []` on read. An editable surface needs a way to accept `tags` on write too — worth naming plainly: Idea today has no general\-purpose edit endpoint, only `status` and `notes` change after creation, so this may be the first time a request body needs to touch an Idea's tags at all rather than just its lifecycle. Regenerate the OpenAPI contract and the frontend client per `CLAUDE.md`'s "Changing an API schema" section.
- **Frontend:** the Idea library page renders tag pills — matching whatever pattern the Inbox already uses for `Capture.tags` (`capture-tags-plan.md` §4.5): small pills under the text when present, nothing when absent.

**Shipped August 10, 2026, with one correction to the assumption above.**
`capture.Idea` has no Ninja endpoint at all — the `IdeaOut` schema already in
`frontend/src/api/schema.ts` belongs to `review`'s weekly summary (`idea_id`,
`text`, `status`, `added_on`, no `tags`), a different, read\-only shape for a
different app. Idea's only write surface is `edit_idea`
(`capture/views.py`), a Django form covering `text` and `notes`, and
`Capture.tags` itself is never browser\-editable either — it arrives only
through the mobile API. So there was no existing or needed request body for
this slice to extend: `tags` gains no write path yet, arrives only via 4.2's
promotion copy, and renders read\-only on the Ideas page the same way
`Capture.tags` renders read\-only on the Inbox. Nothing above about the
model, migration, or render pattern needed to change; only the "Service" and
"API contract" bullets' premise of an existing write surface didn't hold up
against the actual code. A tags\-editing surface for a standalone Idea is
still a reversible decision away, not ruled out — it just isn't evidence\-backed
yet, per `principles.md`'s own instruction not to build ahead of it.

### 4\.2 Carry a capture's tags onto the Idea or task it becomes

- `capture.services.promote_to_idea` and `promote_to_task` don't touch `capture.tags` today. Both need `.tags.set(capture.tags.all())` on the record they create — a copy, not a move; the capture row keeps its own tags afterward, since it remains as history.
- **Task side:** `lists.Tag` already backs `Item.tags` (per `capture-tags-plan.md` §2's own note), so `promote_to_task` needs no schema change, only the copy. **Shipped** ahead of this brief's review.
- **Idea side:** depends on 4.1 shipping first. **Shipped August 10, 2026** — `promote_to_idea` calls `idea.tags.set(capture.tags.all())` right after creating the row, same copy\-not\-move shape as the task side. `capture` and `lists` suites plus the full backend run (841 tests) green.

**4.2 is now fully closed on both sides.** No deviation from the brief this time — the plan's own note that "Idea side depends on 4.1 shipping first" held exactly as written.

### 4\.3 `Idea.related_ideas`

- **Model:** `related_ideas = models.ManyToManyField("self", blank=True, symmetrical=True)`. Symmetrical because "related to" has no direction here — the vision document's "manually selected 'related idea' link" doesn't imply a source and a target, and a symmetrical M2M means adding the link from either idea shows it on both without a second write path that could drift out of sync.
- **Migration:** additive.
- **Isolation, the one rule a plain `ManyToManyField("self")` doesn't enforce on its own:** a service\-layer guard rejecting a link between two ideas that don't share an owner. Not expressible as a `CheckConstraint` — it's a cross\-row check — so it needs the same shape every other owner\-scoped mutation in `capture.services` already takes, and it needs its own isolation test rather than inheriting one from elsewhere.
- **API contract:** smallest version is `IdeaOut.related_ideas: list[int] = []` (ids) plus two service functions, `link_ideas(owner, idea_id, other_id)` and `unlink_ideas(owner, idea_id, other_id)`, both raising the same not\-found/not\-yours error an isolation test expects of every other owner\-scoped lookup in this codebase.
- **Frontend:** chips on the Idea's own page, an add\-by\-search\-or\-id affordance, no separate page and no graph view — per §5 below.

**Shipped August 10, 2026, with the same correction as 4.1: no Ninja API,
so no `IdeaOut` and no owner\-plus\-id service signature.** `link_ideas` and
`unlink_ideas` (`capture/services.py`) take two already\-owned `Idea`
instances, matching every other function in that file — `promote_to_task`
takes a resolved `capture` and `for_list`, not ids. The owner\-mismatch
guard the brief called out still exists exactly as specified: not
expressible as a `CheckConstraint`, its own isolation test
(`test_related_ideas.py::LinkIdeasTest.test_cannot_link_two_ideas_with_different_owners`)
calls the service directly with a cross\-owner pair to prove the guard
holds independently of the view, which can't actually construct that pair
in the first place — both `idea_id` and the POSTed `related` id are looked
up owner\-scoped in `views.link_idea`/`unlink_idea`, 404ing before the
service is ever reached (its own isolation tests, `LinkIdeaViewTest` and
`UnlinkIdeaViewTest`, cover that boundary). A self\-link guard
(`SELF_LINK_ERROR`) was added too — not in the brief, but a one\-line
invariant the plain `ManyToManyField("self")` doesn't enforce either, in
the same spirit as the owner guard.

"The Idea's own page" doesn't exist as a concept in this codebase — Idea
has no detail route; every idea (edit form, promote button, delete button)
already renders inline on the shared `ideas.html` list, so the chips and
the add\-by\-select control landed there instead, per\-idea, matching where
everything else about an idea already lives. "Search" in "add\-by\-search\-or\-id"
was thinned to a plain `<select>` of the owner's other ideas — the same
choice 3a already made deferring a fancier picker until real use says what
"related" needs, and consistent with Reference/Idea search's own trigger
not having fired yet (§1). `capture` and `lists` suites plus the full
backend run (856 tests) green. Verified through the Django test client's
real template rendering, not a live browser — this is server\-rendered
Django with no routing, session, or static\-asset surface touched, the
exact carve\-out `CLAUDE.md`'s browser smoke suite section names.

## 5\. What this deliberately does not do

- **No structured source/URL field.** 3b's answer is "not yet, on
  evidence," not "no." Revisit once there's a real corpus of captured
  links to look at rather than one Android share shape.
- **No Reference/Idea search.** Its own trigger — retained material making
  retrieval a felt problem — still hasn't fired, and tags plus manual links
  are cheap groundwork for it regardless of when it does; `Idea` already
  carries the index that query will need (`architecture-trajectory.md` §4
  rule 7), added ahead of time for exactly this.
- **No AI\-assisted linking or resurfacing.** Unchanged from
  `daily-operating-system-vision.md`\: needs real information volume and a
  trustworthy manual version first.

## 6\. Verification

**Django, `capture` and `lists` suites:**

- A tags test mirroring `capture-tags-plan.md`'s own: creating an Idea with
  tags resolves them the same way a capture does.
- Two promotion tests, one per direction: promoting a tagged capture to an
  Idea carries its tags onto the Idea; promoting a tagged capture straight
  to a task carries them onto the task. A third, the regression that proves
  the first two aren't vacuous: promoting an *untagged* capture produces no
  tags on either side, so a bug that always attaches some default tag would
  still fail it.
- A related\-ideas test that linking two of the same owner's Ideas is
  symmetric — visible from both sides after one write, not two.
- An isolation test that linking to another owner's Idea is rejected, in
  the same shape every other owner\-scoped mutation in this codebase is
  tested.
- An API test posting and reading back `tags` and `related_ideas` on the
  Idea endpoint.

**Frontend:** an Idea\-library\-page test asserting tag pills and
related\-idea chips render when present and nothing renders when absent —
the render/no\-render pair `ui-second-pass-plan.md` used throughout, not
just the positive case.

This crosses an API contract, so `principles.md`'s rule applies: the
broader suite is the mandatory run before calling it done, not just the
new tests passing in isolation.

## 7\. Where this stands

Per this project's own practice, work begins once a brief is reviewed;
splitting 4.1–4.3 into three smaller commits, per `principles.md`'s "slice
the work, split the commits," rather than one — nothing forces them
together, and the only ordering constraint is 4.1 before 4.2.

**4.1 shipped August 10, 2026** — `Idea.tags`, additive migration, read\-only
pills on the Ideas page, `capture` and `lists` suites plus the full backend
run (839 tests) green. See the note under §4.1 above for the one correction
against the brief's assumption: **no editable\-Idea\-fields endpoint exists**
beyond `edit_idea`'s `text`/`notes` form, so `tags` did not ride an existing
write surface and did not gain a new one either — it stays read\-only until
4.2 gives it a source. That answers this section's second open question from
the original brief.

**4.2 shipped in full August 10, 2026**, both the task side (ahead of this
brief being reviewed) and the Idea side (`.tags.set(capture.tags.all())` in
`promote_to_idea`, once 4.1 unblocked it) — see `capture/services.py`.

**4.3 shipped August 10, 2026** — `Idea.related_ideas`, additive migration,
`link_ideas`/`unlink_ideas` with the owner\-mismatch and self\-link guards,
chips and an add\-by\-select control on the Ideas page. See the note under
§4.3 above for the same API\-assumption correction 4.1 already made, plus
one addition: this codebase has no per\-Idea detail page for chips to live
on, so they landed inline on the shared Ideas list instead, and "search" in
"add\-by\-search\-or\-id" thinned to a plain select, consistent with §3a and
§1's search trigger still not having fired.

**§4's first slice is now fully shipped.** All three items — 4.1, 4.2, 4.3
— are done, tested (`capture` and `lists` suites plus the full backend run,
856 tests, green throughout), and recorded above with every place the
brief's assumptions didn't match the actual codebase. Nothing from this
brief is still open; the next work this discovery pass named but explicitly
deferred is §5's list — Reference/Idea search and AI\-assisted linking —
neither of which has its trigger fired yet.
