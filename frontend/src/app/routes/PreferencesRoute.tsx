import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";
import { ThemeToggle } from "../ThemeToggle";

export function PreferencesRoute() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [dailyDigest, setDailyDigest] = useState(true);
  const [timeZone, setTimeZone] = useState("");
  const [compassPurpose, setCompassPurpose] = useState("");
  const [compassQuestion, setCompassQuestion] = useState("");
  const [landingSurface, setLandingSurface] = useState<"day" | "agenda">("day");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/me/preferences");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // Seeded once, deliberately, rather than from inside queryFn.
  //
  // staleTime defaults to 0 and refetchOnWindowFocus is on, so this query
  // refetches every time the tab regains focus. Writing form state from the
  // fetch meant an alt-tab silently restored the server's values over
  // whatever was being edited -- and the save that followed then sent the
  // restored value and reported "Saved.", which is worse than failing,
  // because it looks like it worked.
  const seeded = useRef(false);
  useEffect(() => {
    if (!data || seeded.current) return;
    seeded.current = true;
    setUsername(data.username);
    setEmail(data.email);
    setDailyDigest(data.daily_digest);
    setTimeZone(data.time_zone);
    setCompassPurpose(data.compass_purpose);
    setCompassQuestion(data.compass_question);
    setLandingSurface(data.landing_surface);
  }, [data]);

  /** Any edit invalidates a previous "Saved." -- otherwise it sits there
   *  over an unsaved change, which is how someone concludes their change
   *  was stored when it was not. */
  function edit<T>(setter: (value: T) => void, value: T) {
    setSaved(false);
    setter(value);
  }

  // Asked of the server rather than read from Intl.supportedValuesOf: the
  // browser's tzdata and the server's can disagree, and the disagreement
  // would surface as a validation error on an option we had just offered.
  const { data: timeZones } = useQuery({
    queryKey: ["time-zones"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/time-zones");
      if (error) throw error;
      return data.time_zones;
    },
    staleTime: Infinity,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const theme = data?.theme ?? "system";
      const { data: updated, error } = await apiV1.PATCH("/api/v1/me/preferences", {
        body: {
          username,
          email,
          daily_digest: dailyDigest,
          theme,
          time_zone: timeZone,
          compass_purpose: compassPurpose,
          compass_question: compassQuestion,
          landing_surface: landingSurface,
        },
      });
      if (error) throw new Error(typeof error === "string" ? error : "Couldn't save preferences.");
      return updated;
    },
    onSuccess: (updated) => {
      setSaveError(null);
      setSaved(true);
      queryClient.setQueryData(["preferences"], updated);
    },
    onError: (mutationError: Error) => {
      setSaved(false);
      setSaveError(mutationError.message);
    },
  });

  // Theme applies immediately (see ThemeToggle) and is persisted on its
  // own request rather than waiting for "Save settings" -- it's a visual
  // preference, not form data the user needs to review before committing.
  const themeMutation = useMutation({
    mutationFn: async (theme: "system" | "light" | "dark") => {
      const { data: updated, error } = await apiV1.PATCH("/api/v1/me/preferences", {
        body: {
          username: data?.username ?? username,
          email: data?.email ?? email,
          daily_digest: data?.daily_digest ?? dailyDigest,
          theme,
          // This request sends the whole preferences object, so leaving
          // the zone out would silently reset the user's day boundaries
          // as a side effect of clicking a theme button. The compass is
          // here for exactly the same reason -- it is the newest field
          // this trap could have swallowed.
          time_zone: data?.time_zone ?? timeZone,
          compass_purpose: data?.compass_purpose ?? compassPurpose,
          compass_question: data?.compass_question ?? compassQuestion,
          landing_surface: data?.landing_surface ?? landingSurface,
        },
      });
      if (error) throw error;
      return updated;
    },
    onSuccess: (updated) => queryClient.setQueryData(["preferences"], updated),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    saveMutation.mutate();
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;

  return (
    <div className="max-w-lg mx-auto px-4 py-8 space-y-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">Your account</p>
        <h1 className="text-2xl font-bold">Preferences</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-1">
          <label htmlFor="pref-username" className="text-sm font-bold">
            Username
          </label>
          <input
            id="pref-username"
            value={username}
            onChange={(event) => edit(setUsername, event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="pref-email" className="text-sm font-bold">
            Email
          </label>
          <input
            id="pref-email"
            type="email"
            value={email}
            onChange={(event) => edit(setEmail, event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="pref-time-zone" className="text-sm font-bold">
            Time zone
          </label>
          <select
            id="pref-time-zone"
            value={timeZone}
            onChange={(event) => edit(setTimeZone, event.target.value)}
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          >
            {/* Until the list arrives, the saved zone is the only option,
                so the control shows the truth rather than an empty box. */}
            {(timeZones ?? [timeZone]).map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
          <p className="text-sm text-muted-foreground">
            Decides what counts as overdue or due today, and when the daily
            summary arrives.
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="pref-landing-surface" className="text-sm font-bold">
            Start me on
          </label>
          <select
            id="pref-landing-surface"
            value={landingSurface}
            onChange={(event) =>
              edit(setLandingSurface, event.target.value as "day" | "agenda")
            }
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          >
            <option value="day">Today&rsquo;s page</option>
            <option value="agenda">Agenda</option>
          </select>
          <p className="text-sm text-muted-foreground">
            Where Clarice opens when you sign in. Both stay in the navigation
            either way.
          </p>
        </div>

        {/* Grouped and labelled as one thing, because it is: a standing
            note re-read on every Daily Page, not two more settings. */}
        <fieldset className="space-y-3 rounded-lg border border-border px-3 py-3">
          <legend className="px-1 text-sm font-bold">Personal compass</legend>
          <p className="text-sm text-muted-foreground">
            Shown at the top of every day. Editing it changes every day at
            once, including ones you have already written — it is not stored
            in any of them.
          </p>
          <div className="space-y-1">
            <label htmlFor="pref-compass-purpose" className="text-sm font-bold">
              Purpose
            </label>
            <textarea
              id="pref-compass-purpose"
              value={compassPurpose}
              onChange={(event) => edit(setCompassPurpose, event.target.value)}
              rows={2}
              className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="pref-compass-question" className="text-sm font-bold">
              Guiding question
            </label>
            <input
              id="pref-compass-question"
              value={compassQuestion}
              onChange={(event) => edit(setCompassQuestion, event.target.value)}
              className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
            />
          </div>
        </fieldset>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-input px-3 py-2.5">
          <div>
            <p className="text-sm font-bold">Email me a daily summary</p>
            <p className="text-sm text-muted-foreground">
              A morning email listing anything overdue or due today.
            </p>
          </div>
          <Switch
            checked={dailyDigest}
            onCheckedChange={(next) => edit(setDailyDigest, next)}
          />
        </div>

        {saveError && <p className="text-sm text-destructive">{saveError}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saveMutation.isPending}>
            Save settings
          </Button>
          {saved && <span className="text-sm text-muted-foreground">Saved.</span>}
        </div>
      </form>

      <div className="space-y-2">
        <p className="text-sm font-bold">Theme</p>
        <ThemeToggle
          initialChoice={data.theme}
          onChange={(theme) => themeMutation.mutate(theme)}
        />
      </div>

      <div className="flex flex-wrap gap-4">
        <a
          href="/accounts/password/change/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Change password
        </a>
        <a
          href="/accounts/tokens/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Access tokens
        </a>
      </div>

      <LeavingSection />
    </div>
  );
}

/**
 * Taking your data out, and taking yourself out.
 *
 * Both together, and export first, deliberately. Deletion without export is a
 * trap — the only way to leave would be to destroy everything — so the way out
 * has to be visible from the same place as the way off.
 *
 * commercial-blueprint.md calls the pair a legal blocker rather than a feature
 * gap: Sentry and Resend already process other people's data.
 */
function LeavingSection() {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/nav");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });
  const purgeAt = data?.deletion_purge_at ?? null;

  const request = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST("/api/v1/me/delete", {
        body: { password },
      });
      if (error) throw new Error("That password did not match.");
    },
    onSuccess: () => {
      setPassword("");
      setAcknowledged(false);
      setConfirming(false);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
    onError: (caught: Error) => setError(caught.message),
  });

  const cancel = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST("/api/v1/me/delete/cancel", {});
      if (error) throw new Error("Couldn't cancel that. Please try again.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["nav"] }),
    onError: (caught: Error) => setError(caught.message),
  });

  if (purgeAt) {
    return (
      <section className="space-y-3 rounded-lg border border-destructive px-4 py-4">
        <h2 className="text-sm font-bold text-destructive">
          This account is scheduled for permanent deletion
        </h2>
        <p className="text-sm text-muted-foreground">
          Everything you have here is erased on{" "}
          <strong>{new Date(purgeAt).toLocaleDateString()}</strong> and cannot
          be recovered afterwards. Until then nothing has been touched, and you
          can stop this.
        </p>
        <p className="text-sm text-muted-foreground">
          We have emailed you about this. If you did not ask for it, cancel it
          here and then change your password.
        </p>
        {/* Export stays offered right up to the end. The last day before an
            erasure is the most likely moment somebody wants their data. */}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => cancel.mutate()} disabled={cancel.isPending}>
            Keep my account
          </Button>
          <a
            href="/api/v1/me/export"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Download my data
          </a>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </section>
    );
  }

  return (
    <section className="space-y-4 rounded-lg border border-border px-4 py-4">
      <div className="space-y-1">
        <h2 className="text-sm font-bold">Your data</h2>
        <p className="text-sm text-muted-foreground">
          A zip holding everything in this account — your notes and tasks as
          Markdown you can read, and a JSON file with the complete record.
        </p>
      </div>
      {/* A plain anchor, not a fetch. The response is a file; letting the
          browser handle it means the download works the way every other
          download does, and nothing has to hold the whole archive in memory. */}
      <a
        href="/api/v1/me/export"
        className="inline-flex h-9 items-center rounded-lg border border-border px-3 text-sm font-bold hover:bg-input"
      >
        Download my data
      </a>

      <div className="space-y-1 border-t border-border pt-4">
        <h2 className="text-sm font-bold text-destructive">Delete my account</h2>
        <p className="text-sm text-muted-foreground">
          After 30 days everything is{" "}
          <strong>permanently deleted and cannot be recovered</strong> — every
          task, note, routine, review and the record of them. You can stop it at
          any point before then, and we will email you to confirm. Download your
          data first; afterwards there is nothing to download.
        </p>
      </div>

      {!confirming ? (
        <Button variant="secondary" onClick={() => setConfirming(true)}>
          Delete my account…
        </Button>
      ) : (
        <div className="space-y-3">
          {/* Two gates, guarding different mistakes.
              The acknowledgement guards a misunderstanding -- somebody who
              thinks this hides the account or pauses it. The password guards a
              different person entirely: an open session on a shared machine.
              Either alone leaves the other case uncovered. */}
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
              className="mt-0.5"
            />
            <span>
              I understand this permanently deletes everything in my account and
              cannot be undone.
            </span>
          </label>
          <label htmlFor="pref-delete-password" className="text-sm font-bold">
            Confirm your password
          </label>
          <input
            id="pref-delete-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          />
          <div className="flex items-center gap-3">
            <Button
              onClick={() => request.mutate()}
              disabled={
                request.isPending || password.length === 0 || !acknowledged
              }
            >
              Schedule deletion
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setConfirming(false);
                setPassword("");
                setAcknowledged(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  );
}
