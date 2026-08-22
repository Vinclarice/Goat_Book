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

**The decisions below survive the stub**, and that is the one departure from
the usual shape. They are not open *work*; they are open questions about
behaviour that is now live, and a four-line stub would have quietly dropped
them. ~~**D16 is the one with a clock running.**~~ **D16 answered August 22,
2026** — the clock is the person's, and answering it turned up a live defect in
S14. Five remain.

## The decisions still open

**Five, and they survive the stub deliberately.** They are not open *work* —
every increment shipped — but open questions about behaviour that is now live,
and a four-line stub would have quietly dropped them. The fourteen that were
answered are in [`roadmap-history.md`](roadmap-history.md) with their
reasoning.

5. **D5. Can the log answer absence?** *"Since then, nothing has been recorded"*
   is honest only if the log can prove it was looking. `MAINTENANCE_RAN` is the
   precedent. **Part 3's sobriety refusal is the same decision** in the place a
   person will feel it.

14. **D14. Does the semantic index get switched on, and how?** Registered
    August 21 from
    [`code-review-2026-08-21.md`](code-review-2026-08-21.md)'s examination:
    Part 2's pipeline names the semantic index among its candidate generators,
    but `semantic_echo` has **never run in production** —
    `sentence-transformers` is dev-only by deliberate, documented refusal
    (`run_mind_maintenance.py`), so the fifth detector and the HNSW index are
    dark. The options are a decision, not engineering: accept the dependency,
    embed via an API (a new processor, touching `/privacy/` the way D9 does),
    or a smaller model. If this is ML policy rather than deployment, it
    escalates to `design-concept.md`.

15. **D15. The dormant review loop: wire it, fold it into the modes, or
    delete it.** `mark_reviewed` has no production caller, so the spaced
    resurfacing schedule has never run for a real note and `attention_tier`'s
    review-candidate tier is reachable only through open hypotheses — evidence
    in [`code-review-2026-08-21.md`](code-review-2026-08-21.md) Part 3.
    Part 2's Resurfacing mode is the natural home for the decision; the one
    wrong option is leaving built machinery dark and undecided, per the seam
    rule. Registered August 21.

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

17. **D17. Does Resurfacing include cyclic cues?** The time axis as drafted
    is linear — `around()`, `since()`, windows — but human temporal cueing is
    substantially cyclic: *this time last year*, anniversaries, the same
    Sunday evening. An on-this-day read over `occurred_at` and `captured_at`
    is pure derivation from recorded facts — no ML, no floors, no budget —
    and is exactly Resurfacing's "cued by the person's present," where the
    present includes the date. Leaving the axis linear leaves the cheapest
    honest resurfacing unbuilt. Registered August 21.

18. **D18. Is a neighbourhood clock-bounded or episode-bounded?** The ±6h
    window is a proxy: episodes in a life are bounded by gaps in activity,
    which the log itself shows. Expanding from the instant until a lull gives
    "that morning" its real edges — tight on a busy day, wide on a quiet one
    — derived at read time, so the facts-not-derivations line holds. Bears on
    increment 4's API before it hardens. Registered August 21.
