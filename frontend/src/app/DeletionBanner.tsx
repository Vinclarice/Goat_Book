import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { apiV1 } from "../api/client";
import { RequestFailed } from "../api/failure";

/**
 * "This account is being deleted", on every page until it isn't.
 *
 * Rendered by AppLayout rather than by Preferences, which is the whole point:
 * a scheduled erasure that is only visible on the page you scheduled it from
 * is one somebody can start and then forget for thirty days. It reads
 * `deletion_purge_at` off the nav payload, which every route already fetches,
 * so this costs no extra request.
 *
 * It carries the stop button itself. Undoing a destructive thing must never be
 * harder than starting it, and "go and find the page where you did it" is
 * harder.
 */
export function DeletionBanner() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/nav");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  const cancel = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST("/api/v1/me/delete/cancel", {});
      if (error) throw new Error("Couldn't cancel that.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["nav"] }),
  });

  const purgeAt = data?.deletion_purge_at ?? null;
  if (!purgeAt) return null;

  const when = new Date(purgeAt);
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-destructive bg-destructive/10 px-4 py-2 text-sm"
    >
      <strong className="text-destructive">
        This account is scheduled for permanent deletion
      </strong>
      <span className="text-muted-foreground">
        Everything is erased on {when.toLocaleDateString()} and cannot be
        recovered.
      </span>
      <button
        type="button"
        onClick={() => cancel.mutate()}
        disabled={cancel.isPending}
        className="font-bold underline underline-offset-2"
      >
        Keep my account
      </button>
      {/* To the page rather than straight to the download: somebody arriving
          from a banner should see the whole picture, including that the export
          exists, before they act. */}
      <Link to="/preferences" className="text-muted-foreground underline">
        Manage
      </Link>
    </div>
  );
}
