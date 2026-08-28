# Learning — what you are in the middle of

Vince · focused spec · written August 28, 2026 · **status is the strikes below**

**The first module built against [`modules.md`](modules.md) rather than to
produce it**, which is the only way to find out whether that charter is any good.
It has already corrected the charter twice — see *What the charter got wrong*
below — and both corrections made this cheaper than predicted.

**A knowledge-core module.** Decision 3 of the charter: a core is a *mode*, not a
vocabulary, and reading is capturing rather than committing. It lives under
`/mind/`, behind the nav entry that already says **Read**.

## What is actually wrong, measured

Verified by reading, August 28, 2026 — `mind/views.py`, `mind/models.py`,
`mind/templates/mind/sources.html`, and a count against the development database.

1. **`/mind/sources/` is a list of things you started, with no way to say you
   finished one.** The template renders a title, an author and the date you
   *added* it. That is the whole surface.
2. **`Source` has no state.** `title`, `url`, `author`, `created_at`, and
   nothing else. There is no field meaning *reading*, *finished* or *given up
   on*.
3. **So *what am I in the middle of* is unanswerable**, because nothing records
   that you are in the middle of anything.
4. **And *what did I read this year* is unanswerable.** `created_at` is when you
   recorded the source, not when you read it — a book added in January and
   finished in June is a January row, and one added and abandoned the same week
   is indistinguishable from one finished.
5. **There is no landing read at all**, so charter requirement 2 fails outright.
   The list is ordered by when you added things and answers no question above
   the level of one row.
6. **Two sources exist in a development database holding thirty-six notes.**
   Small, and it cuts both ways — see *The input ratio* below.

**Nothing here is a missing capability, which is the third time that sentence
has been the diagnosis.** `Source` is live and `record_source` writes it.
`Node.came_from` is live, and the capture box sits on the source page
deliberately — *"without this `came_from` would be a column no surface could
set."* `what_grew_from` already walks `Source` → `Node` → confirmed actionable
`Facet` → `Item`. **Every part is built. What is missing is a state and a read
over it.**

## What the charter got wrong, and it was cheap both times

**1. `Source` does not want a sidecar.** [`modules.md`](modules.md) predicted
`MoneyLine`'s shape — a sidecar hanging off an existing record. **That was an
analogy rather than a test.** A sidecar exists so a *general* record is not
burdened with a special case: `Item` is general and a bill is a subset of it.
**`Source` is already the special case.** Every source is something you read or
mean to read; there is no source that is not. So the state goes **on `Source` as
fields**, and this module adds **no new model at all**.

**2. Derivation was called unavailable and is not.** The charter said nothing
connects a project to a source. The chain `Source` → `Node` → `Facet` → `Item` →
Area → `Project` is live end to end and three hops of it are already walked.
**What work came out of this reading is derivable today, with no new column.**

**What is genuinely unavailable is the reverse**, and it is the whole of D1: a
project with no source behind it — *learn Blender* — is reachable from nothing,
because the chain starts at a thing you read.

## The input ratio, which decides the shape of this

**This module has the worst input ratio of the three the charter ranked above
it**, and the design has to fight for it rather than assume it. The rule:
*a module survives when one entry keeps paying out, and dies when it needs
feeding.*

| Entry | How often | Verdict |
|---|---|---|
| Adding a source | once, and it already exists | keep |
| Marking it finished | once, at the end | **keep — it is the entry every read depends on** |
| Status: meaning to / reading / finished / given up | two or three touches in a source's life | keep |
| **Progress — page 120 of 400** | continuously | **refused** |

**Progress is the routines trap wearing a book jacket.** It is the one field
everybody expects and the one that has to be fed forever, and *what am I in the
middle of* is answered by a status without it. **Refusing it is this module's
version of Money refusing bank transactions**, and for the same stated reason:
most of the value for one person, without the part that makes it work to keep.

**And the two-sources count cuts both ways.** It is thin evidence that reading
gets recorded here at all — the honest reading of `routines`' zero. But unlike
routines, **the write path is already reachable and used**, and the missing
entry is one click at the end rather than a daily log.

## The §4 question

**No new model, and the charter is not being skipped to reach that.** §4's test
is a different life cycle. A *reading* does have one — begun, then finished or
given up — but it is not a life cycle *separate from the source*: it is the
source's own, and a source with two readings is a re-read rather than a second
record. Fields on `Source`.

- **Rule 3, snapshot what meaning depends on.** Nothing to snapshot; a status
  and a date are their own meaning.
- **Rule 5, reference never copy.** This is why there is **no verdict field**.
  What a book was worth is a note, the source page already captures notes with
  `came_from`, and a summary field beside them would be a second copy free to
  disagree. **The notes are the verdict.**
- **Rule 6, the deletion decision.** Unchanged — `Source` has no delete path and
  gains none here.

## Increments, in order

1. **A reading has a state.** `Source.status` — *meaning to*, *reading*,
   *finished*, *given up* — and `finished_on`, set when the status becomes
   finished. The list shows it and can set it in one click. **This is the entry
   every other increment reads**, and worth doing whatever happens to the rest.

2. **The landing read** — charter requirement 2, and what makes this a module
   rather than a better list. `/mind/read/` answers, all of it read rather than
   stored: **what you are in the middle of**, **what you finished this year**,
   **what you gave up on**, and **what is waiting**. It crosses the year
   boundary, which nothing here can do today.

3. **Stalled, and it costs no input at all.** A source marked *reading* whose
   notes stopped months ago is the most useful row on the page and is pure
   derivation — `captured_at` on the notes that came from it already answers it.
   **The best input ratio in the module: zero.**

4. **What the reading produced.** `what_grew_from` already returns the notes and
   the tasks; the landing shows the year's yield rather than one source's.
   **Derived, per the correction above, and needing no column.**

5. **Courses and projects** — gated on D1, and deliberately last.

## What this refuses

- **Progress through a thing.** The input ratio, above. Status answers the
  question without it.
- **A verdict, rating or stars field.** §4 rule 5 — the notes are the verdict,
  and they already exist with a surface that writes them.
- **A new model.** Fields on `Source`.
- **Fetching a URL.** D7 already refused it, on SSRF surface on a one-host
  deployment, and nothing here reopens it.
- **Taking reading out of the rest of the knowledge core.** The charter's
  constraint: notes that came from a source stay in Capture, in Search and in
  Then, and tasks that grew from them stay in the task core.

## Open decisions

**D1. Does Learning cover courses, or reading only?** Vince named *learn
Indonesian* and *learn Blender* as the projects a Learning module would hold, and
**neither is a thing you read.** Three answers, and the plan does not pick one:

- **Reading only.** Cleanest, and increments 1–4 are complete without it. A
  course stays a `Project` in the task core, where it already works.
- **`Source` gains a kind** — book, article, course, video. Small, but it widens
  a model whose docstring says *"something you read"*, which is the §4 collapse
  this project watches for: a record renamed after its module until the module's
  whole vocabulary has to fit inside one noun.
- **The module shows learning projects too**, which needs D2.

**D2. If courses are in, how does a project become a learning project?** The
charter's decision 4 allows exactly two answers: **the module's own create path**
— starting *learn Blender* from the Read page, which writes the `Project` and the
module's own record in one transaction — **or refuse it.** Anything attached
afterwards is `paid_by` again, and this repository has now paid for that shape
twice.

**D3. Is `/mind/read/` a new address or the existing one, promoted?** The nav
already says **Read** and points at `sources`. Promoting it in place costs no
navigation change and no redirect; a new address costs both. **That this question
is even close is worth noticing** — see below.

## The honest caveat: this is the smallest thing that qualifies

**It passes the charter on the letter.** Own vocabulary — `Source` is a noun the
task core cannot express. Three surfaces — the list, the detail, and the landing
increment 2 builds. A landing read that stores nothing and crosses the year.

**But it is close to the line, and the charter should not be used to inflate
every page into a module.** The strongest counter-reading is that this is a
*surface repair* of `/mind/sources/` in exactly the way Money was a surface
repair of Bills — and that Money earned the word by growing four sub-surfaces and
two new models, where this adds two fields and one page.

**Recorded rather than resolved**, because the distinction does not change a
single increment above. What it changes is whether
[`module-score.md`](module-score.md) gains a line for Learning or Money keeps the
file to itself, and that is answerable when increment 2 is on screen rather than
now.

## Where the facts live

What a module is, is [`modules.md`](modules.md). What a new model must satisfy is
[`architecture-trajectory.md`](architecture-trajectory.md) §4 — **this module
adds none.** What is active is [`roadmap.md`](roadmap.md). The knowledge core's
design authority is `docs/design-concept.md` at `C:\dev\Clarice_secondmind`, and
S15 — *reading produces work* — is [`product-stories.md`](product-stories.md)'s.
