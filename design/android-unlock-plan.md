# Require unlock to open, as a choice rather than the only behaviour

Vince · brief · written August 3, 2026

## 1. Trigger

Stated directly while discussing login persistence: the stored token
already never expires — there is no session concept, only a credential
that lives in Keystore until Disconnect or revocation — and that permanence
is what Vince wants for himself. The ask is to make that a choice rather
than the only behaviour, with a Settings toggle and a way out for someone
who does not want it.

## 2. What "not permanent" means here, decided rather than assumed

Two shapes were on the table: gate opening the app behind the phone's own
screen lock (biometric or PIN/pattern, whatever is already set up), or
clear the token automatically after some idle period. The second means a
capture typed offline could end up queued against a token that auto-expired
before it ever sent — a durability regression `principles.md`'s "capture is
durable before it is clever" argues against introducing quietly. Chosen:
gate opening. The token still never expires on its own; what changes is
whether seeing what's behind it costs a device unlock first.

## 3. What this reuses, and what it costs

**`androidx.biometric:biometric:1.1.0`** (current stable; 1.4.0 exists only
as alpha) — `BiometricPrompt` configured with `BIOMETRIC_STRONG or
DEVICE_CREDENTIAL`, so it falls back to whatever screen-lock method the
phone actually has, not a fingerprint requirement nobody who uses a PIN
could satisfy.

**`MainActivity` becomes a `FragmentActivity`.** `BiometricPrompt` requires
one; `ComponentActivity` is a sibling class, not a supertype. A real but
small change — nothing else in the activity depends on being a
`ComponentActivity` specifically.

**A new permission, `USE_BIOMETRIC`**, auto-merged by the library. The
manifest's own comment currently says "the only permission this app
needs" — no longer true, and the comment gets corrected rather than left
stale.

**`CapturePreferences`** gains `requireUnlock()` / `setRequireUnlock()`,
the same seam `enterSends()` already uses — unencrypted, on-device,
following a phone to a new one like any other setting, because whether to
ask for a PIN is not itself a secret.

## 4. What this does not do

**No idle timeout, no re-lock while the app is already open.** The gate is
cold-start only: unlocked once per process, same as the existing "typed but
not sent" draft already survives a rotation but not a force-stop. Locking
again mid-session on some elapsed timer is a different, heavier feature
with its own trigger, not implied by this one.

**The default stays permanent.** `requireUnlock()` defaults to `false`,
matching the app's behaviour today and what Vince wants for his own use —
this is opt-in hardening, not a new default everyone is pushed into.

## 5. The slice

1. `CapturePreferences.requireUnlock()` / `setRequireUnlock()` — a JVM test
   the same shape as the existing `enterSends()` coverage.
2. A small `UnlockGate` seam (interface, so the decision of *whether* to
   show a lock screen stays testable without a device) plus an Android
   implementation wrapping `BiometricPrompt` — the prompt itself is
   Keystore-shaped: no JVM implementation, verified on the device the same
   way `KeystoreTokenStoreTest` already is, not unit tested.
3. `Root` gains a locked/unlocked gate ahead of the existing
   connected/Connect fork: if `requireUnlock()` is true and this process
   hasn't unlocked yet, a `LockScreen` composable stands in front of
   everything else — Connect, Capture, and Settings alike, since a
   biometric gate that only guards the capture box and not the Connect
   screen's stored-token state would guard the wrong thing.
4. Settings gets the toggle, next to "Enter key sends".

## 6. Verification

JVM: `requireUnlock`/`setRequireUnlock` round-trip, matching
`enterSends()`'s own test. The lock/unlock state transition in `Root` is
UI wiring, not a decision with its own tests — verified on the device.

Device: toggle on, force-stop the app, reopen, confirm the lock screen
appears before anything else and that the phone's own PIN unlocks it;
toggle off, confirm the app opens straight to Capture as it always has.
