import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";

import { Button } from "../../components/ui/button";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "../routes/RouteFailure";

/**
 * One bill, on a page that belongs to Money.
 *
 * **A bill used to borrow the task detail page**, and on August 31, 2026 that
 * page spent a morning being taught to call itself *Bill detail*, hide
 * Priority, Area and Checklist, and link back to Money — every change an
 * admission that a bill was on the wrong screen.
 * `bill-as-a-model-plan.md` makes the borrowing impossible rather than
 * awkward: a bill that is not an `Item` has no `/tasks/{id}` to borrow.
 *
 * **So the surface moves before the model does.** This reads the same
 * `entry/{id}` the edit, pay and delete calls already use, and at the
 * flip only its data source changes — which keeps that commit from having to
 * invent a page in the same breath as it changes what a bill is.
 *
 * **What it deliberately does not show**: tags, priority, area, checklist,
 * project. Not because they are hidden, but because a bill has none of them —
 * which is the whole argument the model split is made of.
 */
function formatDate(iso: string) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function BillDetailRoute() {
  const { billId } = useParams();
  const id = Number(billId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["bill", id],
    queryFn: async () => {
      const { data, response } = await apiV1.GET(
        "/api/v1/money/bills/entry/{bill_id}",
        { params: { path: { bill_id: id } } },
      );
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  /* Every write here moves a figure the month and the landing page are
     showing, so both are invalidated rather than only the one in front of
     you -- the same rule every task write follows about the side nav. */
  const settled = () => {
    queryClient.invalidateQueries({ queryKey: ["bill", id] });
    queryClient.invalidateQueries({ queryKey: ["bills"] });
    queryClient.invalidateQueries({ queryKey: ["money-landing"] });
  };

  const pay = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST(
        "/api/v1/money/bills/entry/{bill_id}/pay",
        { params: { path: { bill_id: id } }, body: {} },
      );
      if (error) throw error;
    },
    onSuccess: settled,
  });

  const remove = useMutation({
    mutationFn: async (wholeSeries: boolean) => {
      const { error } = await apiV1.DELETE(
        "/api/v1/money/bills/entry/{bill_id}",
        {
          params: {
            path: { bill_id: id },
            query: { whole_series: wholeSeries },
          },
        },
      );
      if (error) throw error;
    },
    onSuccess: () => {
      settled();
      navigate("/money");
    },
  });

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
      <Link
        to="/money"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to Money
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {data.category ?? "Uncategorised"}
        </p>
        <h1 className="text-2xl font-bold">{data.payee}</h1>
      </div>

      <dl className="space-y-3 rounded-lg border border-border px-4 py-4 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Due</dt>
          <dd className="font-medium">{formatDate(data.due_date)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Expected</dt>
          {/* Null is "the water bill, whatever it comes to" -- a real state,
              and saying so beats showing a zero somebody would plan against. */}
          <dd className="font-medium">
            {data.amount === null ? (
              <span className="text-muted-foreground">Not priced</span>
            ) : (
              `${data.amount} ${data.currency}`
            )}
          </dd>
        </div>
        {data.paid && (
          /* The one figure this page has that the month row does not, and the
             reason paid_amount is a second column rather than an overwrite:
             they stop being equal the moment somebody pays extra. */
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Actually paid</dt>
            <dd className="font-medium">
              {data.paid_amount === null
                ? "Recorded, amount unknown"
                : `${data.paid_amount} ${data.currency}`}
            </dd>
          </div>
        )}
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Repeats</dt>
          <dd className="font-medium">{data.repeats ? "Yes" : "One-off"}</dd>
        </div>
      </dl>

      {!data.paid && (
        <Button type="button" onClick={() => pay.mutate()} disabled={pay.isPending}>
          {data.direction === "in" ? "Mark received" : "Mark paid"}
        </Button>
      )}

      <div className="space-y-2 border-t border-border pt-4">
        {/* Two verbs when it repeats, and one when it does not -- removing
            August's rent is not the same act as stopping rent, which is the
            distinction delete_bill's whole_series flag exists for. */}
        <p className="text-sm font-bold text-destructive">Remove this bill</p>
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => remove.mutate(false)}
            disabled={remove.isPending}
          >
            {data.repeats ? "Just this one" : "Delete"}
          </Button>
          {data.repeats && (
            <Button
              type="button"
              variant="outline"
              className="text-destructive"
              onClick={() => remove.mutate(true)}
              disabled={remove.isPending}
            >
              Stop this bill entirely
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
