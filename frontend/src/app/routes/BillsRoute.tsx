import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router";

import { Button } from "../../components/ui/button";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * What is due this month, and what it comes to.
 *
 * A bill is a task with a sidecar — `architecture-trajectory.md` §4 said no
 * to a primitive, and the vision document's own canonical recurring task is
 * "pay rent every month" — so this page is a read over rows that already
 * exist rather than a second kind of thing.
 */
function monthLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

/** Adding a bill, and never saying "task".
 *
 * The name is derived from the payee on the server -- `Landlord` becomes
 * *Pay Landlord* -- so there is no title box here and nobody has to know that
 * a bill is a task with a sidecar underneath. `bills-page-plan.md` has why.
 */
function AddBill({ month }: { month: string }) {
  const queryClient = useQueryClient();
  const [payee, setPayee] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [dueDate, setDueDate] = useState(month);
  const [repeats, setRepeats] = useState(true);
  const [failed, setFailed] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: async () => {
      const { error, response } = await apiV1.POST("/api/v1/bills", {
        body: {
          payee,
          // Empty is not zero: "the water bill, whatever it comes to" is a
          // real bill, and the month counts unpriced ones rather than
          // totalling them.
          amount: amount.trim() === "" ? null : amount.trim(),
          currency,
          due_date: dueDate,
          repeats,
        },
      });
      if (error || !response.ok) {
        throw new RequestFailed(response.status);
      }
    },
    onSuccess: () => {
      setPayee("");
      setAmount("");
      setFailed(null);
      queryClient.invalidateQueries({ queryKey: ["bills"] });
    },
    onError: () =>
      setFailed("That bill could not be added. Check the payee and the amount."),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-border p-3">
      <h2 className="text-sm font-bold">Add a bill</h2>
      <div className="flex flex-wrap gap-3">
        <span className="min-w-40 flex-1 space-y-1">
          <label htmlFor="bill-payee" className="text-sm">
            Who it goes to
          </label>
          <input
            id="bill-payee"
            value={payee}
            onChange={(event) => setPayee(event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
        <span className="w-32 space-y-1">
          <label htmlFor="bill-amount" className="text-sm">
            Amount
          </label>
          <input
            id="bill-amount"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            placeholder="optional"
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
        <span className="w-24 space-y-1">
          <label htmlFor="bill-currency" className="text-sm">
            Currency
          </label>
          <input
            id="bill-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            maxLength={3}
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
        <span className="w-40 space-y-1">
          <label htmlFor="bill-due" className="text-sm">
            Due
          </label>
          <input
            id="bill-due"
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            required
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={repeats}
          onChange={(event) => setRepeats(event.target.checked)}
        />
        {/* On by default: the canonical bill is rent. */}
        Repeats every month
      </label>
      {failed && <p className="text-sm text-destructive">{failed}</p>}
      <Button type="submit" disabled={add.isPending}>
        Add bill
      </Button>
    </form>
  );
}

export function BillsRoute() {
  const { month } = useParams();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["bills", month ?? "today"],
    queryFn: async () => {
      const day = month ?? new Date().toISOString().slice(0, 10);
      const { data, response } = await apiV1.GET("/api/v1/bills/{day}", {
        params: { path: { day } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  const due = Object.entries(data.due_totals);
  const paid = Object.entries(data.paid_totals);

  return (
    <div className="max-w-2xl mx-auto space-y-4 px-4 py-8">
      <nav className="flex items-baseline justify-between gap-3">
        <Link
          to={`/bills/${data.previous_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          ← {monthLabel(data.previous_month)}
        </Link>
        <h1 className="font-sans text-xl font-bold">
          {monthLabel(data.month_start)}
        </h1>
        <Link
          to={`/bills/${data.next_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          {monthLabel(data.next_month)} →
        </Link>
      </nav>

      {/* Above the month, not below it. The page used to end at "No bills due
          this month." with two links, both to other empty months -- a page
          named after a thing you could not make on it. */}
      <AddBill month={data.month_start} />

      {data.bills.length === 0 ? (
        // "Nothing is due" rather than "0.00 is due" — different facts, and
        // only one of them deserves a total.
        <p className="text-sm text-muted-foreground">
          Nothing in this month yet. Add one above.
        </p>
      ) : (
        <>
          <ul className="space-y-1">
            {data.bills.map((bill) => (
              <li
                key={bill.task_id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
              >
                <span className="min-w-0">
                  <Link
                    to={`/tasks/${bill.task_id}`}
                    className={
                      bill.paid ? "text-muted-foreground hover:underline" : "hover:underline"
                    }
                  >
                    {bill.text}
                  </Link>
                  {/* A word, not a strikethrough: paid is a good outcome and
                      the month's record of it should not read as cancelled. */}
                  {bill.paid && (
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      paid
                    </span>
                  )}
                  {bill.payee && (
                    <span className="ml-2 text-sm text-muted-foreground">
                      {bill.payee}
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 items-baseline gap-3">
                  <span className="text-sm text-muted-foreground">
                    {dayLabel(bill.due_date)}
                  </span>
                  <span className="text-sm">
                    {bill.amount === null ? (
                      // Not "0.00", which would read as free.
                      <span className="text-muted-foreground">no amount</span>
                    ) : (
                      `${bill.amount} ${bill.currency}`
                    )}
                  </span>
                </span>
              </li>
            ))}
          </ul>

          {/* One line per currency, never one number: adding 500 USD to 40 GBP
              produces 540 of nothing.

              And two figures rather than one. A single "total" held what was
              outstanding, so a month that cost 1264.99 reported 64.99 -- see
              bills-page-plan.md. What you owe and what the month cost are
              different questions and the page now answers both out loud. */}
          <div className="space-y-1 border-t border-border pt-2">
            {due.map(([code, total]) => (
              <p key={`due-${code}`} className="text-sm">
                <span className="font-bold">
                  {total} {code}
                </span>{" "}
                still to pay
              </p>
            ))}
            {paid.map(([code, total]) => (
              <p key={`paid-${code}`} className="text-sm text-muted-foreground">
                <span className="font-bold">
                  {total} {code}
                </span>{" "}
                already paid
              </p>
            ))}
            {due.length === 0 && paid.length > 0 && (
              <p className="text-sm">Everything this month is paid.</p>
            )}
            {data.unpriced > 0 && (
              <p className="text-sm text-muted-foreground">
                {data.unpriced === 1
                  ? "One bill has no amount, so it is not counted above."
                  : `${data.unpriced} bills have no amount, so they are not counted above.`}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
