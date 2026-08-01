import { FormEvent, useState } from "react";
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
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, error, isPending } = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/me/preferences");
      if (error) throw error;
      setUsername(data.username);
      setEmail(data.email);
      setDailyDigest(data.daily_digest);
      return data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const theme = data?.theme ?? "system";
      const { data: updated, error } = await apiV1.PATCH("/api/v1/me/preferences", {
        body: { username, email, daily_digest: dailyDigest, theme },
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
            onChange={(event) => setUsername(event.target.value)}
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
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-input px-3 py-2.5">
          <div>
            <p className="text-sm font-bold">Email me a daily summary</p>
            <p className="text-sm text-muted-foreground">
              A morning email listing anything overdue or due today.
            </p>
          </div>
          <Switch checked={dailyDigest} onCheckedChange={setDailyDigest} />
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
