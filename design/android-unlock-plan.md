# Require unlock to open, as a choice rather than the only behaviour

**Shipped and deployed August 6, 2026.** Biometric unlock is opt-in, checked once
per process at cold start rather than on a re-lock timer, and it sits ahead of
every other branch — including the share-intent bypass, because a lock that left
a shared draft reachable would be guarding the wrong thing.

`BiometricPrompt` is why `MainActivity` is a `FragmentActivity`.

This is a stub. See [`roadmap-history.md`](roadmap-history.md) under
*After Dunlin*.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
