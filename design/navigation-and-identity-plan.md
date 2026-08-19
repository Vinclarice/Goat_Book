# Navigation and visual identity — plan

Vince · designed August 18, 2026 · **not started**

Deliberately short. [`commercial-blueprint.md`](commercial-blueprint.md) Part 8
refuses "another long planning document", and it is right; the mockups carry
the design and this file carries only the decisions and the order.

Two comps: [`landing-mockup.html`](landing-mockup.html) is the signed-out page,
[`shell-mockup.html`](shell-mockup.html) is the navigation and the re-theme on
an application surface. Open them. Everything below assumes you have.

## What is wrong now

**Three navigations that disagree.** [`base.html`](../src/lists/templates/base.html)
has a top bar, [`SideNav.tsx`](../frontend/src/app/SideNav.tsx) has a left rail,
[`mind/base.html`](../src/mind/templates/mind/base.html) has its own top bar in
its own CSS. Measured consequences:

- **"Review" names two unrelated things** — the weekly task review, and the
  knowledge core's pending queue.
- **"Today" resolves to two destinations.** base.html's goes via `/dashboard/`,
  which reads `landing_surface` and may land on the Agenda; SideNav's is always
  `/day`.
- **`/mind/` is a one-way door.** Both other navs link in; its nav has no link
  out.
- **Three paths to one Preferences screen**, one of them a server round trip
  through [`account_settings`](../src/accounts/views.py).
- **Two logout controls** with different mechanics.

**Three visual identities, one of which ignores the user.** The task core is
navy and mint; `/mind/` is warm paper and forest green in hand-rolled CSS; and
**no `mind/` template calls `theme_resolution_script`** — zero of eight — so it
reads `prefers-color-scheme` only and the theme toggle silently does not apply
to a third of the application.

**`--font-sans` names Inter and nothing loads it.** One declaration in the tree,
no `@font-face`, no link tag. Every page renders in the system fallback.

**The signed-out home page is the login form.** `/` is `LandingLoginView`.
[`product-stories.md`](product-stories.md) already scored this: S1 is
*impossible*, and its requires-line ends "a landing page that is not a login
form." The current copy greets a stranger with *"Welcome back."*

## The three decisions taken

Vince, August 18, 2026, in session:

1. **Full re-theme.** Token architecture survives; every value does not.
2. **The wedge is A+B** — the honest week, plus quantified practice.
   `commercial-blueprint.md` Part 9 #2 recorded this as open; this settles it
   **for the landing page's positioning only**. #1, whether Clarice is a
   business, is still open and still gates Phases 3–5.
3. **One app bar plus a contextual sub-nav**, not three reconciled navs.

## Navigation

**One bar, server-rendered, identical everywhere** — inside the SPA shell, on
the Django account pages, and at `/mind/`. It carries the wordmark, the two
cores, and the account. Nothing about it changes between surfaces; that is the
entire property being bought.

**A sub-nav below it**, per core. Tasks: Today · Agenda · Review · Archive.
Second Mind: Capture · Concepts · Pending · Search · Numbers.

**The rail becomes contents, not navigation.** Areas and Projects are things
the task core *holds*; where you can *go* is the bar. The knowledge core has no
such list and gets no rail.

Two renames, both of which remove a collision rather than improve a word:

- `/mind/`'s **Review → Pending.** Tasks already has a Review and they are
  unrelated.
- `/mind/`'s **Things → Concepts**, which is what its URL, its view and its
  template have always been called.

And "Today" must resolve identically from both entry points, which means the
bar links to the core and the sub-nav links to the surface.

**The bar has to be server-rendered to work at all.** `/mind/` carries no
JavaScript by design — it is phone-first capture and its value is that it loads
instantly. A React bar would either not appear there or cost it that property.

## Identity

**One paper, one ink.** The first draft gave each core its own accent and it
was cut: the complaint is that the two cores look like two products, and two
accents is a milder version of that mistake.

Ledger stock, not cream — accounting paper was tinted to cut glare, and it is
the one warm neutral that is not the cream currently on every other landing
page. Values are in the comps' `:root`; they become `tailwind.css`'s `@theme`
block, and the Django templates and `/mind/` read the same ones.

**Cinnabar is reserved for arithmetic** — the margin rule and the figure. Never
a button, never an outcome. Red in a ledger means *look at this number*.

**Three outcome states, two colours.** `kept` and `released` are marked; `open`
is unmarked, because that is the honest rendering of a decision nobody has made
yet. `released` reads calm rather than red on purpose: `released_at` records a
decision, and colouring it as failure would contradict the data model.

**Type is a rule, not a palette.** Sans (Archivo) is machinery — controls,
labels, navigation. Serif (Spectral) is the record — anything a person wrote or
is being told. Mono (IBM Plex Mono) is anything that has to add up. The
interface is equipment; your words are not.

## The signed-out page

The page is a ledger sheet and the pitch is written in its margin, against the
red margin rule that ruled paper actually has. The hero is a real week —
8 chosen, 5 kept, 1 released, 2 open — with the arithmetic done in front of the
reader and the number a conventional app would have reported instead.

**It opens with 71%, and that is the risk.** Every competitor's landing page
shows a perfect week. Showing an imperfect one is the wedge stated as an image:
the number is trustworthy *because* it is not flattering. Vince's call.

**The arithmetic on that page is the product's, and it was wrong in the first
draft.** It read 5/8, which puts the released commitment in the denominator —
the exact thing [`review/reads.py`](../src/review/reads.py)'s `Planned` refuses,
and a direct contradiction of the marginalia three inches to its left.
`Planned.total` is `met + unfinished`; `set_aside` is outside it. The figure is
**5/7**, and the released count now sits visibly apart from the sum. Any future
edit to these comps has to keep that property: **the page's numbers are a claim
about the code and have to be checked against it.**

**The CTA says "Request access", not "Create account", because signup does not
work.** `accounts/forms.py` creates the account `is_active=False`, approval is
an admin checkbox, and none of `accounts/emails.py`'s six functions tells the
person they were approved. A "Create account" button would be a front door onto
a dead end. Either the copy stays honest or S1's signup path gets built first —
that ordering is open.

## Sequencing

Each step is independently shippable and independently revertable.

1. **Load the fonts and land the tokens.** `tailwind.css`'s `@theme`, self-hosted
   subsets. Nothing moves; everything changes colour. `test_frontend_style_contract.py`
   guards the token names and will need its expectations moved with the contract —
   which is a real contract change, per [`principles.md`](principles.md).

   **Raise `button.tsx` to a 44px floor in the same step.** The primitive is
   `h-8` (32px) by default, `h-9` (36px) at `lg`, `size-8` for icons; every 44px
   fix so far has been applied per call site, so each new call site re-inherits
   32px. `product-stories.md` S2 names this. **This step is the only cheap
   moment for it** — the styling tests are already being moved, and doing it
   later means touching every surface a second time.

2. **Give `/mind/` the tokens and `theme_resolution_script`.** Fixes the theme
   toggle's silent third. No layout change.

3. **The app bar**, server-rendered, on all three surfaces. The renames land here.

4. **Demote the rail to contents** inside `/app/`. Touches `SideNav.tsx`,
   `AppLayout.tsx`, `sidenav.module.css` and their tests.

5. **The signed-out page**, and with it **the metadata the task core has never
   had**: favicon, `apple-touch-icon`, Open Graph and a web manifest. `/mind/`
   has all four and the main application has none — so the page whose whole job
   is being shared as a link currently previews as a bare URL. Cheap, and
   visible the first time anyone posts it.

6. **The first-run empty state**, which is the other half of S1. A landing page
   that works delivers a stranger to `/app/day`, and today's empty state reads
   *"Choose from your action items below to plan the day"*
   ([`DayRoute.tsx:78`](../frontend/src/app/routes/DayRoute.tsx)) — which
   assumes action items exist. Someone arriving with nothing has no designed
   state at all. **Shipping 5 without 6 makes the blank page better attended.**

Steps 3 and 4 cross routing and the app shell, so the browser suite is mandatory
for both — build the bundle first or the tests run against stale JavaScript.

**Step 3's known hazard.** [`AppLayout.tsx`](../frontend/src/app/AppLayout.tsx)
holds its `<details>` open above 761px on purpose: Firefox does not render a
closed disclosure's contents, and relying on how an engine treats one is what
shipped an empty-gutter bug before. Moving the mobile nav from a disclosure to a
bar rewrites exactly that machinery, and the breakpoint is currently mirrored in
two places — `AppLayout.tsx`'s `WIDE` and `sidenav.module.css`'s media query,
each documented as having to move with the other. Neither the bug nor the
mirroring is a reason not to do it; both are reasons the browser suite is the
acceptance condition rather than a formality.

## Two constraints on the re-theme

**The error states are not a surface to redesign.** `NotFoundRoute` distinguishes
"there was never a page here" from "the thing you asked for is gone", and says
plainly that nothing has been deleted; `RouteFailure` treats 401, 403, 404 and a
dead connection as four situations needing opposite things. That is better than
most shipped products and it was reasoned about in `bittern-plan.md` B2.1.
**Re-colour them; leave the copy alone.**

**Three families is a real payload.** Archivo, Spectral and IBM Plex Mono, self
hosted and subset, variable where available. If one has to go it is Archivo:
Spectral holds up at small sizes and the mono is load-bearing, since the whole
identity rests on figures that line up.

## Three states was wrong — it is four, under one rule

The comps first showed a three-mark vocabulary: kept, released, open. That
covers tasks and **does not cover routines**, which have four outcomes —
`COMPLETED`, `SKIPPED`, `PARTIAL` ("Enough") and `OPEN`
([`routines/models.py`](../src/routines/models.py)), and `PARTIAL` is
*deliberately* not folded into `SKIPPED`.

The rule that does cover both is the one [`review/reads.py`](../src/review/reads.py)
already states, and it is better than the one it replaces: **not "how did this
end" but "did you decide, or did it merely run out."** A decommitment and an
"that was enough" are both decisions and both leave the denominator; a period
that elapsed does not. So:

- **green** — met
- **slate** — decided (released · skipped · enough)
- **unmarked** — elapsed, or not yet answered

Two colours, four outcomes, one rule — and the rule is the product's own.

## What is not decided

- **Whether this becomes an active roadmap item**, and against what priority.
  `roadmap.md` owns that; this file does not claim it.
- **Whether signup gets built before or after the landing page** (see above).
- **Whether the three-mark vocabulary reaches the application's own surfaces**,
  or only the marketing page. The comps show it on both, which is a proposal.
- The comps were verified for structure and computed tokens, **not for
  appearance** — the browser pane on this machine does not composite. Somebody
  has to actually look at them.
