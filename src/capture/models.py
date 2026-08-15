"""Nothing lives here any more.

`Capture` and `Idea` were deleted by Heron 4b on August 15, 2026 — the step the
crossover existed to reach. Every thought they held is a `Node` in `mind`,
carrying its original timestamp, its tags as confirmed concepts, and its link to
whatever it became; `migrate_inbox` moved them and retired with them.

**The app itself is deliberately still installed.** Django needs it in
`INSTALLED_APPS` for `migrations/0004_delete_idea_capture` to run, which is what
actually drops the tables. Removing the app in the same change would leave two
tables in production with no migration able to reach them and orphaned rows in
`django_migrations`. Removing it is a follow-up, once that migration has been
applied everywhere — which for a one-host deployment means the next deploy.

The reasoning these models carried is not lost with them. Why capture asks
nothing at the moment of writing is `design/principles.md` and the knowledge
core's own capture surface; why the Inbox went is
`design/one-capture-surface-plan.md`; what the migration cost is
`design/roadmap-history.md`.
"""
