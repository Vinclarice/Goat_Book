import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, refusal, statusOf } from "../../api/failure";
import { Button } from "../../components/ui/button";
import { RouteFailure } from "../routes/RouteFailure";

/**
 * The category list, which belongs to the person rather than to the code.
 *
 * Vince asked for a fixed list *"however add a setting that lets the user
 * manually edit the list"* — and that clause is why `MoneyCategory` is a table
 * rather than a `TextChoices`. This is the setting.
 *
 * **On the Money module rather than in Preferences**, because these are money
 * vocabulary rather than an app-wide setting, and the place you notice a
 * category is wrong is while looking at your bills.
 */
type Category = { id: number; name: string; line_count: number };

export function CategoriesRoute() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [failed, setFailed] = useState<string | null>(null);

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["money-categories"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/money/categories");
      if (!data) throw new RequestFailed(response.status);
      return data as Category[];
    },
  });

  const done = () => {
    setFailed(null);
    setEditing(null);
    queryClient.invalidateQueries({ queryKey: ["money-categories"] });
    // The month view groups on these, so a rename has to reach it too.
    queryClient.invalidateQueries({ queryKey: ["bills"] });
  };
  const failedWith = (caught: Error) => setFailed(caught.message);

  const add = useMutation({
    mutationFn: async () => {
      const { error, response } = await apiV1.POST("/api/v1/money/categories", {
        body: { name: adding },
      });
      if (error || !response.ok) throw await refusal(error, response);
    },
    onSuccess: () => {
      setAdding("");
      done();
    },
    onError: failedWith,
  });

  const rename = useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await apiV1.PATCH(
        "/api/v1/money/categories/{category_id}",
        { params: { path: { category_id: id } }, body: { name: draft } },
      );
      if (error || !response.ok) throw await refusal(error, response);
    },
    onSuccess: done,
    onError: failedWith,
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await apiV1.DELETE(
        "/api/v1/money/categories/{category_id}",
        { params: { path: { category_id: id } } },
      );
      if (error || !response.ok) throw await refusal(error, response);
    },
    onSuccess: done,
    onError: failedWith,
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <div className="max-w-xl mx-auto space-y-4 px-4 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-sans text-xl font-bold">Categories</h1>
        <Link
          to="/money"
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          ← Money
        </Link>
      </div>

      <p className="text-sm text-muted-foreground">
        {/* Said plainly, because it is the thing that makes deleting safe and
            people assume otherwise. */}
        Bills are grouped by these on the month view. Deleting one leaves its
        bills alone — they become uncategorised.
      </p>

      <ul className="space-y-1">
        {data.map((category) => (
          <li
            key={category.id}
            className="flex flex-wrap items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
          >
            {editing === category.id ? (
              <>
                <label htmlFor={`name-${category.id}`} className="sr-only">
                  Name
                </label>
                <input
                  id={`name-${category.id}`}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  className="min-w-32 flex-1 rounded-lg border border-border bg-input px-2 py-1"
                />
                <span className="flex shrink-0 gap-2">
                  <Button size="sm" onClick={() => rename.mutate(category.id)}>
                    Save
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                    Cancel
                  </Button>
                </span>
              </>
            ) : (
              <>
                <span className="min-w-0">
                  {category.name}
                  {category.line_count > 0 && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {category.line_count === 1
                        ? "1 bill"
                        : `${category.line_count} bills`}
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 gap-3 text-sm">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(category.id);
                      setDraft(category.name);
                    }}
                    className="touch-target text-muted-foreground hover:text-foreground"
                    aria-label={`Rename ${category.name}`}
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => remove.mutate(category.id)}
                    className="touch-target text-muted-foreground hover:text-foreground"
                    aria-label={`Delete ${category.name}`}
                  >
                    Delete
                  </button>
                </span>
              </>
            )}
          </li>
        ))}
      </ul>

      {failed && <p className="text-sm text-destructive">{failed}</p>}

      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <span className="min-w-40 flex-1 space-y-1">
          <label htmlFor="new-category" className="text-sm">
            Add a category
          </label>
          <input
            id="new-category"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
        <Button type="submit" disabled={add.isPending}>
          Add
        </Button>
      </form>
    </div>
  );
}
