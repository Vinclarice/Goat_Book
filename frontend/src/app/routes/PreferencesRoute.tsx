import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import { apiV1 } from "../../api/client";
import { ThemeToggle } from "../ThemeToggle";

export function PreferencesRoute() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [dailyDigest, setDailyDigest] = useState(true);
  const [timeZone, setTimeZone] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, error, isPending } = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/me/preferences");
      if (error) throw error;
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
          // as a side effect of clicking a theme button.
          time_zone: data?.time_zone ?? timeZone,
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
  if (error || !data) return <p className="p-6">Something went wrong.</p>;

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
    </div>
  );
}
