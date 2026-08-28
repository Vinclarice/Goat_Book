# Modules — the charter for surfaces

Vince · standing authority · written August 27–28, 2026

**This file never becomes a stub, and that is the thing to know before reading
it.** [`README.md`](README.md)'s stub rule reduces a plan to four lines once its
work ships, because a plan is *about* work. This is a charter: the sibling of
[`architecture-trajectory.md`](architecture-trajectory.md) §4, which asks what a
new **model** must satisfy, where this asks what a new **place** must satisfy.
§4 has never stubbed and neither will this. **Each module still gets its own
focused spec** — [`money-module-plan.md`](money-module-plan.md) is the first —
and this governs them and outlives all of them.

**It never overrides §4.** A module is permission to make a place, never
permission to skip the model charter.

## Why it exists

**Money was not a feature. It was the first instance of a shape this repository
had no word for**, and it was got right by Vince describing it out loud, sixteen
commits, and three rounds of looking at it — including a whole phase that
existed only because he saw the page. That is not a repeatable process, and the
second module would have paid for it again. Before this file, *module* appeared
in `design/` exactly once outside the Money plan: as a description of the Money
plan.

## What a module is — the containment test

Not the date in the address; `/agenda` and `/archive` are dateless too. The
discriminator was already written, in `lists/money.py`'s own docstring:

> *a read with its own vocabulary — putting it in the agenda would make the
> agenda answer a question about money.*

> **A view is a lens over the substrate every other view shares. A module is
> what would otherwise force a shared surface to learn a vocabulary that is not
> its own.**

Today, Agenda, Review, Calendar and Archive all read `Item`. Money reads
`MoneyLine` and `Account`, which exist for one domain only.

**The test is about vocabulary, not size.** A module is not *a big feature*.

## What a module is not — five boundaries

| | Does it end? | Own vocabulary? | Created by |
|---|---|---|---|
| **View** | No | No — a lens on the shared substrate | the product |
| **Area** | No | No — it only groups | the person |
| **Project** | **Yes** — three fields describe how | No — uses `Item` and Areas | the person |
| **Module** | No | **Yes** | the product, in code |

### Not a view — the product's second axis

**Every surface the task core had before Money slices by *time*:** Today, this
week's Review, this month's Calendar, the Agenda's horizon, the Archive's past.
Different windows onto one substrate. Nothing sliced by **domain** except Areas.

So *"everything is still sort of in silos"* — the feeling the Money work was
aimed at — was describing **the absence of a second axis** rather than the
presence of walls. **Views are horizontal. Modules are vertical.** That is why
they are not peers, and it is a better reason than *one has its own nouns*
because it says what the level is *for*.

### Not an Area — and this is where a module comes from

`lists.List` is an Area at the boundary: a user-created grouping of items, a
place per part of a life, made of data rather than code. So why was Money not
simply an Area called Money?

**Because an Area groups, and a module has vocabulary.** An Area can hold the
bills; it cannot hold an amount, a payee, a currency, a balance or a category.

> **A domain starts as an Area. It earns a module when it needs nouns the shared
> substrate cannot express.**

**This is the only thing that bounds how many modules there can be.** It makes
an Area the cheap default so a module is never the first answer; it gives
promotion a real trigger — *you want a field `Item` does not have* — rather than
a feeling; and it caps the count at *as many domains as have their own
vocabulary, and no more*. It is §4's test moved up one level: §4 says a concept
earns a **model** when it has a different life cycle; this says a domain earns a
**module** when it has its own words.

### Not a project — the difference is termination, not longevity

Vince's question, August 28, 2026. **`Project` answers it in its own fields**: it
carries `purpose` (why), `desired_outcome` — *"what would be true when it is
finished"* — and S10's still-unbuilt abandonment condition. **All three describe
how it ends.** A module has no such field and could not have one: nothing
completes the sentence *"Money will be finished when…"*

**Two framings more useful than the table.** A project asks *am I going to finish
this?* and a module asks *how do I stand in this part of my life?* And a project
is a **commitment** where a module is a **concern** — you can abandon a project,
which is what S10's third field is for, but a domain can only stop being looked
at.

### Not a core — a core is a mode

**Vince's call, August 28, 2026, against this file's first argument.** That
argument was structural: `mind` has twenty-odd models and twenty-odd routes,
passes every required test below, and the only thing making it a *core* was that
it used to be a separate repository — so a core would be *a module large enough
to have grown its own view-level navigation*.

**What is true instead is that a core is a mode, not a vocabulary.** The task
core is for committing and doing; the knowledge core is for capturing and
connecting. That is a difference in what the person is *doing there*, which no
amount of shared structure collapses.

**The consequence is the useful part: modules live *inside* a core**, and which
core a module belongs to is a real question with a real answer.

### Not a Django app

**Money has no app.** It is `lists/money.py`, `lists/services.py` and four models
in `lists/models.py`. **`routines` is a full app with no module** — `models`,
`reads`, `services`, `periods`, `api_v1`, the §4 rule-4 split done properly — and
appears in `AppRoutes.tsx`, `ViewNav.tsx` and `SideNav.tsx` **zero times**.

> **A Django app is where code lives. A module is where a person goes.**

One of each mismatch is in the tree, so neither implies the other. Worth stating
because the obvious way to add a module is `startapp`, which produces the code
layout and no place.

## What a module is made of

Money has six parts and they do not carry equal weight. Pretending they do is how
a charter becomes a checklist.

### Required — without any of these it is a view, not a module

1. **Its own vocabulary**, by the containment test above.
2. **A landing read that stores nothing, and crosses the time-boxes every other
   read is keyed to.** *Precedent:* `money_landing`, and the whole of Money's
   increment 10 — `/money` showed August, so answering *how am I doing* meant
   reading three lists and doing arithmetic. *Cost later:* a module that is a
   month view is a page, and the person still does the arithmetic.
3. **More than one surface over those nouns.** One surface is a page.

### The constraint — a module adds a lens, it never extracts

**A place per domain sounds like more siloing, and what stops it is decision 4
of the Money plan**: *"Bills stay ordinary tasks elsewhere — day, agenda,
lists."* A bill is on Money **and** on the Day **and** on the Agenda. The module
did not take bills out of the flow; it added somewhere to see them together.

> **A module may not remove anything *actionable* from the shared surfaces.**

**The word *actionable* is load-bearing and Money proves why.** Income *is*
excluded from the day and the agenda — one clause at `agenda.open_items_for` —
because you do not tick off being paid. It left because it is not a task, **not
because it belongs to Money**. Without the qualifier the rule forbids a correct
exclusion; without the rule, the second module quietly becomes the silo the whole
exercise was aimed at.

### Observed in Money — the questions to ask of the next one, not requirements

4. **A person-owned taxonomy.** `MoneyCategory` earns a table because it is
   created, renamed, reordered and deleted on its own schedule — §4's life-cycle
   test met rather than argued around. **Seeded, not empty**: an empty list plus
   a form is a chore handed to somebody who came to look at their bills.
5. **A ritual gets one transaction.** The monthly balance pass. An untouched box
   means *skip me*, never *blank me*, and the boxes start empty with last month
   beside them, because pre-filling makes an untouched box look considered.
6. **A series, not a field.** `BalanceReading` and `paid_amount`. A field
   overwritten monthly keeps no series to answer *is this going down* with — the
   same argument twice in one build, which is why it is written here once.

## The input ratio — what decides whether a module survives

**This repository has said the same thing three times and never named it.** Money
refused bank transactions on preference — *"I never really liked that and found
it too difficult to really use"*. The Money plan's only remaining open item asks
of investments *"whether balances would actually get typed in"*. And `routines`
has **zero rows** in a development database holding five users, fifty items and
thirty-six nodes.

> **The input ratio: how much typing per unit of answer. A module survives when
> one entry keeps paying out for years. It dies when it needs feeding.**

Money is the good case, and good by this measure rather than by ambition: a bill
is entered once and recurs forever, and balances are twelve entries a year.
**The refusal of bank feeds is this rule already applied once**, before anybody
wrote it down — which is why it is recorded here rather than argued.

**A domain is not automatically all-in, and splitting one by input ratio is a
legitimate move.** Health is the clearest case: appointments, prescriptions and
a six-monthly dentist reminder have Money's ratio, while weight and sleep
readings have routines'. Taking the low-input half and refusing the other
outright is exactly what Money did to transactions.

**The corollary is about build order.** A history surface is a read over rows
somebody logged. Bills at least *had* rows before Money made them usable;
building trends for a domain nobody feeds is the stale-investments-tab failure
with a different noun on it.

## The acceptance, for any module

> **The domain's central question is answered by looking, rather than by
> arithmetic.**

Vince's own sentence turned into a test: *"if I need to check on financial
information, I know exactly where to go."*

## How a module reaches work it does not own

*Learn Indonesian* and *Learn Blender* are projects a Learning module would
**show** — exactly as Money shows bills that `Item` owns. **Containment is a
reading, not a structure**, and it has to be, for two reasons. The lens rule
requires it: a module owning its projects would remove them from the Projects nav
and the Agenda. And **one project can sit in several modules** — *renovate the
kitchen* is Home, Money and arguably Learning — where strict containment would
force a filing decision with no right answer. **Money proves no foreign key is
needed**: there is no `MoneyLine.module` field, because the module *is* the read.

**But a module recognises its records through its own vocabulary.** Money knows a
bill because it has a `MoneyLine`. **Nothing tells Learning that *Learn
Indonesian* is a learning project**, and that link is the hard part.

> **A module's link to work it does not own is made by the module's own create
> path. Anything attached afterwards is a seam, and seams die.**

**Money did not add a link and hope — `create_bill` writes the `Item` and the
`MoneyLine` in one transaction, from the module's own form.** Membership cannot
be forgotten because the only path that makes the record is the module's own.
That is also what predicts `paid_by`'s death exactly: it was an *afterwards* link
— attach an account to a bill that already exists — and no moment in any flow
demanded it. It was written, accepted by the service, called by nothing, and
deleted on August 27, 2026.

The alternatives, ranked, so they are not re-derived:

- **A nullable FK plus a moment in the flow that sets it.** Works only if the
  moment is natural — *"part of something you're working on?"* on the add-a-book
  form. If the answer is a settings screen, it is `paid_by` again.
- **A person-owned category on `Project`.** Reuses `MoneyCategory`'s argument,
  and has one advantage the others lack: **one field serves all six modules**
  rather than six foreign keys. The cost is a filing decision, which this charter
  elsewhere declines to charge. `lists.Tag` may already be most of it.
- **Derivation, with no stored link.** The house preference when existing facts
  answer the question — the node-to-day relationship shipped as a read on Part
  1's *facts, not derivations*. ~~**Unavailable here**: nothing currently
  connects a project to a source.~~ **Wrong, and corrected August 28, 2026 by
  the first plan written against this file.** The chain **`Source` → `Node` →
  confirmed actionable `Facet` → `Item` → Area → `Project`** is live end to end,
  and `mind.services.what_grew_from` already walks the first three hops. **So
  derivation is available**, and it is the right answer for *what work came out
  of this reading*.

  **What it cannot answer is the reverse.** A project with no source behind it —
  a Blender course you are simply doing — is reachable from nothing, because the
  chain starts at a thing you read. **Derivation covers reading that produced
  work; it does not cover work that is learning.** Those need different answers
  and the distinction is easy to miss.
- **Refuse it.** **Money shows no projects and is fine.** A module may legitimately
  show only its own nouns. This is the option that costs nothing and should be
  taken whenever no natural creation moment exists.

**One blind spot to know about.** `test_the_list_is_the_whole_list` discovers
dark code by iteration rather than from a hardcoded list — but it covers
**services, and only inside `mind/services.py`**. An unused *field* in `lists` is
invisible to it, which is how `paid_by` survived long enough to need deleting. A
new foreign key here has the same blind spot and no guard behind it.

## Navigation — four concepts, three levels

| Level | Says | Where it lives |
|---|---|---|
| **Core** | task core or knowledge core | the app bar, `_app_bar.html` |
| **View** | which lens over the core's shared substrate | `ViewNav` |
| **Module** | which domain | **borrowed `ViewNav`** |
| **Sub-surface** | which surface within a module | **borrowed `SideNav`** |

**Money did not add an entry to a level. It added a level**, and then borrowed
the rows above and below it. That is why both now say two things: `ViewNav` lists
one place among five lenses, and `SideNav` grew a
`location.pathname.startsWith("/money")`.

## How a module is measured

[`module-score.md`](module-score.md) — one line per module, against the
acceptance above. **[`product-stories.md`](product-stories.md) keeps its nineteen
journeys and its denominator**, which v4 refused to move for S19 on the same
reasoning. This converts a blind spot into a boundary of that score **without
leaving module quality unmeasured**, which was the only option that could do
both.

## Decisions taken

1. ~~**Does a module keep its sub-navigation in the shared rail, or own it?**~~
   **The rail keeps it** — August 27, 2026. Months on Money read well and the
   alternative was rebuilding navigation that works. **What it costs is honesty
   in one docstring**: `SideNav`'s says the rail is contents-only, and the rail
   has been contextual since that morning. **The rail is contents *and* the
   current module's own surfaces**, and it should say so. The escape hatch in
   `SideNav.tsx` — *"if it starts feeling wrong, the fix is a column on the Money
   page itself"* — **stands unfired rather than deleted.**

2. ~~**How does a module get measured?**~~ **Its own file, one line per
   module** — August 27, 2026. See above.

3. ~~**Is the knowledge core really just the largest module?**~~ **No — it
   remains a distinct core** — August 28, 2026. A core is a mode. See *Not a
   core*.

4. ~~**How does a module link to a project?**~~ **By its own create path, or not
   at all** — August 28, 2026. See *How a module reaches work it does not own*.

## Open decisions

**D1. Does `ViewNav` distinguish a place from a lens?** It lists Today, Agenda,
Review, Calendar, **Money**, Archive — one place among five lenses at equal
weight. A separator or grouping is cheap and says the difference; doing nothing
means the row grows undifferentiated, one line per module *and* per view. **Not
answered by decision 1**, which was about the rail below it. Cheap either way,
and worth answering before the second module.

~~**D2. Which of the six is next, and in what order?**~~ **Learning is next —
August 28, 2026**, specced in
[`learning-module-plan.md`](learning-module-plan.md), which is the first
document written *against* this file. **It corrected two things here on contact**
and both are struck below. The remaining order is open. Ranked by the input
ratio, which is the ranking that matters:

| Module | Core | Its own vocabulary | The question it answers | Input |
|---|---|---|---|---|
| **Home & possessions** | task | appliance, model and serial, purchase date and price, warranty expiry, service interval, who serviced it | *What needs attention, and when was the boiler last done?* | Enter once, pays out for years |
| **Documents & travel** | task | passport, visa, licence, insurance — each with an expiry; trips with dates | *What expires before my next trip?* | Enter once, pays out for years |
| **Vehicle** | task | insurance and inspection dates, service history, mileage readings | *What is due, and what is it costing per mile?* | Once, plus an occasional reading |
| **Learning** | **knowledge** | a sidecar on `mind.Source`: progress, status, finished-on, verdict | *What am I in the middle of, and what did I finish this year?* | Occasional |
| **Health** | task | appointments, prescriptions, renewals — **and** weight, blood pressure, sleep | *What is due?* · *How am I trending?* | **Splits — see the input ratio** |
| **People** | knowledge | last contacted, birthday, how you know them | *Who have I not spoken to in too long?* | Needs feeding |

**The top three are strong for one reason: low-frequency, high-forget.** Nobody
holds *the boiler was serviced in March 2024* or *the passport expires in eleven
months* in their head, and neither has any home in the product. They are also
where **`Item.lead_days` pays out immediately** — machinery Money's increment 7
found already built and unreachable — because *warn me before it lands* is the
entire feature.

~~**Learning is a sidecar, not a primitive.**~~ **Neither — corrected August 28,
2026 on first contact.** `mind.Source` is *"something you read, which notes can
come out of"* and holds title, url and author, with **no status and no dates**;
the reasoning that it therefore wants a sidecar was `MoneyLine`'s shape applied
by analogy rather than by test. **A sidecar exists so a *general* record is not
burdened with a special case** — `Item` is general and a bill is a subset of it.
`Source` is already the special case: **every source is something you read or
mean to read**, so the state belongs on it as fields. **It needs no new model at
all**, which is less than the analogy predicted, not more.
[`learning-module-plan.md`](learning-module-plan.md) carries the §4 working.

**Some of these should blend with the knowledge core, and that is a feature of
the split rather than a violation of it** — Vince, August 28, 2026. Learning and
People are knowledge-core modules outright. The strain is a course with
assignments: those are real commitments, stay `Item`s in the task core, and are
read by the module the way Money reads bills. **`confirm_actionable` writing a
node, a facet and a task in one transaction is the precedent** — `CLAUDE.md`
calls it the merger's payoff rather than a violation of it.

~~**The repository's own candidate is `routines`.**~~ **Set aside August 28,
2026, on evidence rather than taste.** It argues for itself in three places —
[`daily-operating-system-vision.md`](daily-operating-system-vision.md) is headed
*"Routines are their own domain"*; §4 rule 3 made `RoutineOccurrence` snapshot
`target_quantity` and `unit` so history could not be rewritten, **and nothing
reads that history as a series**; and §4's *what the charter buys* names the
reads and says *"one review-and-analytics read module can serve all of them."*
**But it has the worst input ratio of anything considered, and zero rows in a
populated development database.** It is the exact inverse of Bills — Bills had a
read and no writes, `routines` has every write and only a today-read — and the
missing piece is the logging, not the history surface. **Revisit if routines are
ever actually logged**; production is the number that would settle it and has not
been checked.

**D3. Does a module ever earn its own Django app?** Money did not and is fine.
The honest answer is probably *when its models outgrow the host app's own
vocabulary*, but two instances are not enough to write that rule with, and a
premature answer here would be the framework this file refuses.

## What is left to do

1. ~~**The charter is written down and pointed at.**~~ **Done August 27–28,
   2026.** This file, a row in [`README.md`](README.md), and an entry in
   [`roadmap.md`](roadmap.md) — **which covered Money as well, because it had
   none.** Sixteen commits shipped fourteen increments on August 27 and the sole
   authority on *what is active* mentioned none of it, while `README.md` told
   readers the scoring gap was "noted in `roadmap.md`", where it was not. **The
   consequence was concrete: the closing ritual's step 2 had no item to strike.**

2. **The rail stops contradicting itself.** `SideNav`'s docstring says it
   *"navigates and nothing else"* and lists what is in here; the code also
   renders the current module's surfaces. Decision 1 makes that correct rather
   than a lapse, so the docstring should say it. **A comment a reader can
   disprove from the code beneath it is worse than no comment.** Not done: that
   file is being edited by another session.

3. ~~**The module score exists, with Money as its first line.**~~ **Done August
   28, 2026** — [`module-score.md`](module-score.md).

4. **The second module.** **Six candidates are settled and the order is not** —
   D2. Whichever goes first, it is the first build to run *against* this charter
   rather than to produce it, which is the only way to find out whether the
   charter is any good.

## What this refuses

- **A framework for modules.** No abstract base class, no registry, no shared
  `Module` type. §4 rule 8 already argues this for occurrence tables — *keep it a
  documented convention rather than an abstract base class, because a shared base
  invites putting more on it* — and two instances do not earn machinery.
- **A module as a licence for a model.** §4 governs, unchanged.
- **A Django app per module.** Money has none and is the better of the two.
- **Retrofitting the pattern onto the views.** Today, Agenda, Review, Calendar
  and Archive are lenses and are correct as lenses.
- **A module that removes actionable records from the shared surfaces.** The
  constraint above, stated as a refusal because it is the failure mode that would
  undo the reason any of this exists.

## Where the facts live

What is active is [`roadmap.md`](roadmap.md). What a new **model** must satisfy
is [`architecture-trajectory.md`](architecture-trajectory.md) §4 — **this file
never overrides it.** How each module scores is
[`module-score.md`](module-score.md). What Money did, increment by increment, is
[`money-module-plan.md`](money-module-plan.md), and it is not restated here.
