# Optional tags on a capture

Vince · brief · written August 3, 2026

## 1. Trigger

Stated directly, not inferred: captures about a game in development and a
movie to watch are landing in the same Inbox with nothing to tell them
apart later. The ask is narrower than it could be — tags at capture time,
on the Android app specifically, and explicitly *not* the broader
triage/Daily-Page work that would come after. "Work on the capture part
first before moving to turning it into receiving stuff."

## 2. What this reuses, and why

`lists.Tag` — owner-scoped, unique `(owner, name)` — already backs
`Item.tags` and `RecurringCommitment.tags`. A capture tag is the same
concept: a person's own word for something, not a controlled vocabulary.
Reusing the model rather than inventing a parallel one is `principles.md`'s
"one rule, one authoritative definition" — a tag typed on the phone and one
typed on a task should collide if they're spelled the same, not live in two
separate namespaces that happen to look alike.

`Capture`'s own docstring already establishes the direction this can point:
"No FK *into* capture from lists... The FKs below point the other way."
`capture.tags` pointing at `lists.Tag` is the same shape as the existing
`promoted_task` and `promoted_idea` FKs — capture depending on lists,
never the reverse.

## 3. What this does not do, and why

**Triage does not gain a tags field.** `promote_to_task`'s own comment is
explicit: "Due date, tags and the rest get set afterwards through the
normal task UI... making it also be the moment you schedule it would put
the friction back that capture exists to remove." That reasoning is about
triage, not capture — tags typed *while writing the thought down* are a
different moment and don't reintroduce that friction. But this slice does
not carry a capture's tags forward onto the task or idea it becomes. That
is a real follow-on (it's the only way the tags outlive the Inbox), named
here so it isn't silently assumed rather than decided, and left for
whichever of Reference/Idea search or the receiving-side work in
`roadmap.md` picks it up.

**The web Inbox gets read-only display, not an editing UI.** Capturing
tags somewhere a person can never see them again would be F2's defect
again — a deliberate act with no visible outcome. Displaying them costs a
template change; editing them is a second surface for a rule the phone
already owns, and isn't asked for here.

## 4. The slice

1. **`lists.services._resolve_tags` becomes `resolve_tags`.** The only
   change needed to reuse it from `capture.services` without reaching into
   a private name.
2. **Migration:** `Capture.tags = ManyToManyField("lists.Tag", blank=True,
   related_name="captures")`. Additive; every existing row keeps zero tags.
3. **`capture.services.create_capture` and `create_capture_idempotent`**
   take an optional `tags` argument. The idempotent path only sets tags on
   the branch that actually creates a row — a retry that finds an existing
   row returns it as recorded, the same rule the function already states
   for text.
4. **API contract:** `CaptureIn.tags: list[str] = []`, `CaptureOut.tags:
   list[str] = []`. Regenerate `openapi.json` — no web client reads this
   endpoint today, but the contract stays honest anyway.
5. **Inbox template:** tags render as small pills under the capture text
   when present; nothing renders when absent.
6. **Android:** the compose screen gets a second, optional text field —
   "Tags (optional, comma separated)", matching the phrasing already used
   on the Area page and task detail forms rather than inventing new copy.
   Wired through `ClariceApi.capture()`, and — the part that actually
   needs care — through the encrypted queue: `PendingCapture` gains a
   `tags` field so a queued-while-offline capture doesn't lose them between
   being written down and finally being sent, the same durability guarantee
   `text` already has.

## 5. Verification

Django: a test that `create_capture_idempotent` with tags produces a
`Capture` whose `tags` match, a test that a replay does not touch tags on
the existing row, an API test posting `tags` and reading them back, and an
Inbox-template test (or the equivalent smoke check) confirming a tagged
capture renders its pills and an untagged one renders none.

Android: `CaptureQueue`/`EncryptedQueueStorage` round-trip tests confirming
tags survive a save/load cycle, and a `ClariceApi` test (MockWebServer)
confirming the request body carries `tags`. No new instrumentation test —
the compose screen's existing coverage extends the same way the due-date
and tag fields already did on the web side.
