# A second factor on the accounts that can read everything

**Shipped August 19–23, 2026 as `petrel`.** All four increments: `django-otp`
and the middleware, enrolment and recovery codes at `/accounts/security/`,
Vince's own enrolment in production, then enforcement on `/admin/` and a refusal
on `/api/v1/login` in one deploy. **Enrol before enforcing** was the ordering
that mattered, and verifying increment 3 against production rather than taking
it on report is what caught the device landing on the wrong account.

This is a stub. What shipped, the four codebase interactions that shaped it, the
break-glass bound and the four refusals are in
[`roadmap-history.md`](roadmap-history.md) under *A second factor on the admin*.

Eleven comments in `src/` cite this plan by section — `§2.1` on the endpoint
that starts no session, `§2.4` on the lockout that cannot see a six-digit code,
`§2.5` on unfold, `§4` on the ordering, and increments 1 and 4 at the settings,
the templates and the tests. Each states its rule itself and cites this file as
provenance, which is why the file remains.

**Two decisions left the plan open and are `roadmap.md`'s now**: whether
`/api/v1/login` grows a `totp` field once the Android keystore exists (M1), and
where the recovery codes live (M2) — *the decision most likely to be skipped and
most likely to matter*.

Reduced to a stub on August 26, 2026. See [`README.md`](README.md).
