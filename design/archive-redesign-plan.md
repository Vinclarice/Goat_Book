# Archive redesign — the last Tailwind migration

**Shipped August 11, 2026** (`85154a8`), retiring `site.css` outright. The 44px
touch-target fix was applied per call site rather than in `button.tsx`, so the
primitive is still 32px — recorded because it is the kind of thing that reads as
done and is not.

This is a stub. The narrative is in
[`roadmap-history.md`](roadmap-history.md) under *The Bootstrap → Tailwind arc*.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
