import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

import { apiV1 } from "../../api/client";
import { TaskWorkspace } from "../../TaskWorkspace";

export function ListRoute() {
  const { listId } = useParams();
  const id = Number(listId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

  const { data, error, isPending } = useQuery({
    queryKey: ["list", id],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/lists/{list_id}", {
        params: { path: { list_id: id } },
      });
      if (error) throw error;
      setTitle(data.list.title);
      return data;
    },
  });

  const renameMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/lists/{list_id}", {
        params: { path: { list_id: id } },
        body: { title: newTitle },
      });
      if (error) throw new Error(typeof error === "string" ? error : "Rename failed.");
      return data;
    },
    onSuccess: (updated) => {
      setRenameError(null);
      setTitle(updated.title);
      queryClient.setQueryData(["list", id], (current: typeof data) =>
        current ? { ...current, list: { ...current.list, title: updated.title } } : current,
      );
    },
    onError: (mutationError: Error) => setRenameError(mutationError.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.DELETE("/api/v1/lists/{list_id}", {
        params: { path: { list_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => navigate("/agenda"),
  });

  function handleRename(event: FormEvent) {
    event.preventDefault();
    renameMutation.mutate(title);
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) return <p className="p-6">Something went wrong.</p>;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <Link to="/agenda" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to today
      </Link>

      <div className="flex items-start justify-between gap-4">
        <form onSubmit={handleRename} className="flex-1 flex flex-col gap-2">
          <label htmlFor="list-title" className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            List name
          </label>
          <div className="flex gap-2">
            <input
              id="list-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={100}
              required
              className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5 text-lg font-bold text-foreground"
            />
            <Button type="submit" disabled={renameMutation.isPending}>
              Save name
            </Button>
          </div>
          {renameError && <p className="text-sm text-destructive">{renameError}</p>}
        </form>

        {data.archived_count > 0 && (
          <a
            href={data.archive_url}
            className="text-sm text-muted-foreground hover:text-foreground whitespace-nowrap pt-6"
          >
            {data.archived_count} archived
          </a>
        )}
      </div>

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="destructive" size="sm">
            Delete list
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this list?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{data.list.title}</strong> and all of its tasks will be permanently
              removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep list</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteMutation.mutate()}>
              Delete list permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <TaskWorkspace initialData={data} />
    </div>
  );
}
