# Temporal substrate and contextual retrieval — focused spec

Vince · **shipped and closed August 22, 2026 as `nightjar`** · the narrative,
what it taught and the verification actually run are in
[`roadmap-history.md`](roadmap-history.md)

**What it was.** Making memory a memory, in four parts and five tracks: what
memory can see (the time axis), how it gives things back (contextual
retrieval), what it notices (structured observations) and what it holds
(intake). **Every increment across Tracks A, B, C, D and E is shipped.**

**A stub rather than a deletion**, because seventeen code comments cite this
file by name and eleven of them by track — the file has to resolve, its
thousand lines do not.

~~**The decisions below survive the stub**~~ — **all six were answered on
August 22, 2026, and the stub is now a stub.** They are kept below with their
answers rather than deleted, because what each turned out to be is the useful
part: two of the six were largely already decided and nobody had noticed, and
two more were hiding live defects.

**The order mattered.** D16 named whose clock a day is on; D17 could not have
built the cyclic axis without it; D5 could not have counted *days you were
recording* without it; D15 could not be folded into a Resurfacing mode that D17
had to build first. Four of the six are one dependency chain, discovered by
answering them rather than by planning them.

## The decisions still open

~~**None. All nineteen are answered**, the last six on August 22, 2026.~~
**One. Eighteen of the nineteen are answered** — corrected August 26, 2026.
**D18 is open**, and was open when this line was written; `osprey`'s tag makes
the same overcount, closing with *"all nineteen substrate decisions closed."*
[`clarice/recall.py`](../src/clarice/recall.py) still carries
`DEFAULT_WINDOW = timedelta(hours=6)`, which **is** the clock-bounded proxy D18
exists to question, so the code was never ambiguous about it.

**Worth keeping rather than quietly renumbering**, because of how it happened:
the five answered on August 22 were a dependency chain, the chain was the
interesting part, and the summary was written about the chain rather than about
the list. A count is not a story and should not be written from one.

The answered eighteen stay listed below with what each turned out to be, because
*what the question was actually hiding* is the part worth keeping — the
reasoning for all of them is in
[`roadmap-history.md`](roadmap-history.md).

5. ~~**D5. Can the log answer absence?**~~ **Answered August 22, 2026: yes, and
   it needs no new row.** The log's own other events are the proof it was
   looking. `MAINTENANCE_RAN` is the precedent for a *machine* proving it ran,
   and it had to be written down because a pass that finds nothing leaves no
   other trace — **a person leaves traces constantly**, so a heartbeat beside
   them would be a row a read could have produced.
   `recall.attendance_between` counts the days in a window the log holds
   anything for, and the note page now says whether *nothing came of this* is a
   fact about the note or about the log.

14. ~~**D14. Does the semantic index get switched on, and how?**~~ **Answered
    August 22, 2026, and two of its three options were already closed.** The
    **API is refused by standing ML policy** in `mind/embeddings.py` —
    *self-hosted, deterministic, no external call, no per-use cost, nothing
    generative*. D14 said this escalates if it is ML policy rather than
    deployment: it is, and the policy already said no. **A smaller model is the
    same option cheaper**, since torch is what makes the dependency large and
    every self-hosted encoder pulls it in. The dependency itself was deferred on
    **August 18** (D4 of `planning-assistant-plan.md`).

    **What was still open is that the gate was not checkable.** *A corpus large
    enough for the detector to have something to say* is a feeling; it is now
    250 live notes, reported on `/mind/numbers/` with the distance to it — and
    that line no longer tells production to run `embed_nodes`, **a command that
    cannot run there.**

15. ~~**D15. The dormant review loop: wire it, fold it into the modes, or
    delete it.**~~ **Answered August 22, 2026: wire it, into the mode** — both
    right options at once, and not available until that morning. D15 named
    Resurfacing as the natural home while Resurfacing was itself a
    `NotImplementedError`; **D17 built it**, and a mode with a page is a caller.
    `/mind/this-time-before/` now offers *keep* and *less often*, which is the
    one thing the loop lacked, and notes whose schedule has come round are a
    second Resurfacing generator beside the anniversary.

    **Deleting it was the real alternative and was rejected on evidence**: the
    schedule is derived from an append-only log rather than a mutable column,
    and *burying* stretching six times faster than *keeping* is designed
    behaviour with nowhere to happen — not speculative machinery.

16. ~~**D16. Whose clock is a morning?**~~ **Answered August 22, 2026: the
    person's**, which was already decided —
    [`per-user-time-zones-plan.md`](per-user-time-zones-plan.md) settled it on
    August 1 and `User.time_zone` has been the only place it is stored since.
    The knowledge core inherited it rather than being given a second one. The
    rule is [`clarice/clocks.py`](../src/clarice/clocks.py) and it is
    deliberately **not** `timezone.localdate()`; the reasoning and the S14
    defect it uncovered are in
    [`roadmap-history.md`](roadmap-history.md).

    **This entry's stated symptom was wrong**, which is worth leaving visible:
    it said *every observation Track C records is stamped UTC*, and Track C's
    days were always the person's, because they key on `DailyEntry.date`. The
    clock was running two modules over.

17. ~~**D17. Does Resurfacing include cyclic cues?**~~ **Answered August 22,
    2026: yes**, and it built the mode. The read is
    [`recall.this_time_before`](../src/clarice/recall.py) and it derives from
    `occurred_at` alone, so there was no row to write and nothing to backfill.
    **`Mode.RESURFACING` had raised `NotImplementedError` since Track B
    increment 8**, for want of *"a present"* — and the present turns out to be
    the date, which everybody already has. Surfaced at `/mind/this-time-before/`.

    **It needed D16 first**, which is why the ordering mattered: an anniversary
    is a claim about a calendar day, and a calendar day does not exist until
    somebody says whose clock it is on. Narrative in
    [`roadmap-history.md`](roadmap-history.md).

18. **D18. Is a neighbourhood clock-bounded or episode-bounded?** The ±6h
    window is a proxy: episodes in a life are bounded by gaps in activity,
    which the log itself shows. Expanding from the instant until a lull gives
    "that morning" its real edges — tight on a busy day, wide on a quiet one
    — derived at read time, so the facts-not-derivations line holds. Bears on
    increment 4's API before it hardens. Registered August 21.

    **Still open as of August 26, 2026, and the only one that is.** Twice
    reported closed and never was — once by the summary above, once by
    `osprey`'s tag.

    **Its trigger has partly gone**, which is the thing to notice rather than
    the miscount: it was registered to be answered *"before increment 4's API
    hardens"*, and that API shipped on August 22 and has been live since.
    `DEFAULT_WINDOW` is overridable per call, and
    [`recall.py`](../src/clarice/recall.py) already says why — *the right window
    is a property of the question and not of the log* — so the API did not
    harden around the proxy the way the decision feared. **What is left is a
    read-time question with no deadline**, and by `principles.md`'s rule it now
    needs either a trigger that can fire or a refusal.

    **Given a trigger by the declare-or-refuse sweep, August 26, 2026: one
    neighbourhood that reads wrong.** Not a count and not a date — the ±6h
    window is a *proxy for an episode*, and the only evidence a proxy is wrong
    is a specific occasion where it was: a morning cut in half, or a quiet day
    where six hours swept in three unrelated things. **One recorded example is
    enough**, because one is something to argue from and none is not.

    **Deliberately not a refusal**, though that was the easier call. The window
    is already overridable per call and the module already says the right window
    belongs to the question — so the design is **half-way to episode-bounding
    already**, and what remains is only whether any caller should ask for it.
    That is a question one user can answer from ordinary use, which is what
    separates it from the ones this sweep refused.
