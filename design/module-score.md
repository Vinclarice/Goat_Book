# The module score

Vince · standing authority · opened August 28, 2026

**One line per module, against one question**, which
[`modules.md`](modules.md) states as the acceptance for any module:

> **Is the domain's central question answered by looking, rather than by
> arithmetic?**

**This file exists so that `product-stories.md` does not have to grow.** That
score measures the product against nineteen journeys through the three loops and
the second brain, and its denominator is deliberately stable — v4 refused to move
it when S19 was refused. Modules are a different axis, and adding a journey per
module would make the score incomparable with itself. **So modules are a boundary
of that score rather than a blind spot in it**, and this is where they are
measured instead.

**A verdict is about the module, not its increments.** How far along a module is
lives in its own focused spec. This says only whether the place works.

## The score

| Module | Core | Central question | Verdict |
|---|---|---|---|
| **Money** | task | *How do I stand financially, and what needs paying?* | ~~**Works** — August 27, 2026~~ **Not yet** — corrected August 31, 2026 |

## Money — why it read *works*, and why it does not

**The first verdict is struck rather than rewritten**, because what it said was
true and what it measured was the wrong thing.

**What it said, and still true.** Before increment 8, `/money` showed one month
of bills, so answering *how am I doing* meant reading three lists and doing
arithmetic across them. A month view is not a module; it is a page. What
replaced it reads what is overdue across every month, what is due in the next
fortnight across month boundaries, what renews soon, what is owed and held with
the change since last month, and whether this month balances. All of that
works, and all of it was verified.

### Why it is *not yet*, corrected August 31, 2026

**Vince's own words, four days after it shipped**: *"obviously Money didn't
work."* He opened `/money`, found a landing page offering nothing to act on,
added a bill, tried to record a balance, and hit three dead ends in a row —
two screens telling him to add an account, neither able to, and a link between
them pointing at a third that could not either. `POST /money/accounts` had no
caller anywhere in the SPA. Then he clicked his own bill and landed on a page
headed *Task detail*.

**The central question was answered by looking — for somebody who already had
data.** Nothing in the module could make somebody into that person for
balances, and the front door could not tell *nothing recorded* from *nothing
pressing*, so it gave the reassuring answer to a person who had recorded
nothing. [`money-module-plan.md`](money-module-plan.md) has the four defects and
their repairs, all landed the same day.

**It stays *not yet* rather than going back to *works*.** The repairs are real
and verified in the running application, but the last verdict was wrong in the
direction of flattery and was taken by the person who had just built the thing.
The next one should be taken after use, by the person using it.

### What this file learns from being wrong

**The first verdict carried its own escape clause and it was not enough.** It
said the score was taken mid-construction and *"should be re-read once the
module closes"* — an accurate caveat that changed nothing, because a caveat is
not a trigger. Four days passed, the module did not close, and the row still
read **Works** while three of its six surfaces had no way in.

So, for every module scored here after this one:

- **A module is scored by using it, not by looking at it**, and specifically by
  walking the path a person starts from — with no data, from the front door.
  Every defect above sat on that path, and none of them was visible from a
  screen with data already on it.
- **The person who built it should not be the only one who scores it.** Both of
  Money's verdicts came from inside the work. The first was wrong; this one is
  a transcription of the owner's own sentence, which is the difference.
- **A verdict with a caveat about its own reliability is not a verdict.** If it
  cannot be scored yet, the row says so.

## Where the facts live

What a module is, and the acceptance this file applies, is
[`modules.md`](modules.md). What Money did, increment by increment, is
[`money-module-plan.md`](money-module-plan.md). How the *product* scores against
its journeys is [`product-stories.md`](product-stories.md), which this file
deliberately does not touch.
