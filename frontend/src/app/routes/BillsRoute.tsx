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
  const [recurrence, setRecurrence] = useState("monthly");
  const [leadDays, setLeadDays] = useState("");
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
          recurrence,
          repeats: recurrence !== "none",
          lead_days: leadDays.trim() === "" ? 0 : Number(leadDays),
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
      <div className="flex flex-wrap gap-3">
        <span className="w-44 space-y-1">
          <label htmlFor="bill-cadence" className="text-sm">
            How often
          </label>
          {/* The model has had all four of these since Crane; the form used to
              offer a checkbox, which is why an annual subscription could not
              be written down at all. */}
          <select
            id="bill-cadence"
            value={recurrence}
            onChange={(event) => setRecurrence(event.target.value)}
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          >
            {CADENCES.map((each) => (
              <option key={each.value} value={each.value}>
                {each.label}
              </option>
            ))}
          </select>
        </span>
        <span className="w-52 space-y-1">
          <label htmlFor="bill-lead" className="text-sm">
            Warn me this many days early
          </label>
          {/* The reason this module exists. An annual subscription that speaks
              on the day it renews has already charged you. */}
          <input
            id="bill-lead"
            value={leadDays}
            onChange={(event) => setLeadDays(event.target.value)}
            inputMode="numeric"
            placeholder={recurrence === "annual" ? "30 is usual" : "optional"}
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </span>
      </div>
      {failed && <p className="text-sm text-destructive">{failed}</p>}
      <Button type="submit" disabled={add.isPending}>
        Add bill
      </Button>
    </form>
  );
}

type BillRow = {
  task_id: number;
  text: string;
  due_date: string;
  amount: string | null;
  currency: string;
  payee: string;
  paid: boolean;
  repeats: boolean;
  recurrence: string;
  lead_days: number;
  overdue: boolean;
  paid_amount: string | null;
};

/** How often, in words a person uses. */
const CADENCES = [
  { value: "none", label: "Once" },
  { value: "weekly", label: "Every week" },
  { value: "monthly", label: "Every month" },
  { value: "quarterly", label: "Every quarter" },
  { value: "annual", label: "Every year" },
];

function cadenceLabel(value: string) {
  return CADENCES.find((each) => each.value === value)?.label ?? "";
}

/** Days until a date, in the browser — for display only.
 *
 * Deliberately not used to decide anything: whether a bill is *late* is
 * answered on the server against the owner's own clock, because a date worked
 * out in a browser is a second opinion on whose day it is. This only phrases a
 * number the server already stands behind.
 */
function daysUntil(iso: string) {
  const due = new Date(`${iso}T00:00:00`);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - now.getTime()) / 86400000);
}

/** Correcting a bill without leaving the page it is shown on.
 *
 * The four fields do not live in one record -- amount, payee and currency are
 * the sidecar's and the due date is the task's -- and the server's `update_bill`
 * hides that, which is the point. This form does not know either.
 */
function EditBill({ bill, onDone }: { bill: BillRow; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [payee, setPayee] = useState(bill.payee);
  const [amount, setAmount] = useState(bill.amount ?? "");
  const [currency, setCurrency] = useState(bill.currency);
  const [dueDate, setDueDate] = useState(bill.due_date);
  const [failed, setFailed] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await apiV1.PATCH(
        "/api/v1/bills/entry/{task_id}",
        {
          params: { path: { task_id: bill.task_id } },
          body: {
            payee,
            currency,
            due_date: dueDate,
            // Absent is not empty, so clearing an amount has to say so out
            // loud: "whatever it comes to" is a state somebody chooses.
            amount: amount.trim() === "" ? null : amount.trim(),
            clear_amount: amount.trim() === "",
          },
        },
      );
      if (error || !response.ok) throw new RequestFailed(response.status);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bills"] });
      onDone();
    },
    onError: () => setFailed("That change could not be saved."),
  });

  return (
    <li className="space-y-2 rounded-lg border border-border px-3 py-2">
      <div className="flex flex-wrap gap-2">
        <span className="min-w-32 flex-1 space-y-1">
          <label htmlFor={`edit-payee-${bill.task_id}`} className="text-xs">
            Who it goes to
          </label>
          <input
            id={`edit-payee-${bill.task_id}`}
            value={payee}
            onChange={(event) => setPayee(event.target.value)}
            className="w-full rounded-lg border border-border bg-input px-2 py-1"
          />
        </span>
        <span className="w-28 space-y-1">
          <label htmlFor={`edit-amount-${bill.task_id}`} className="text-xs">
            Amount
          </label>
          <input
            id={`edit-amount-${bill.task_id}`}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            className="w-full rounded-lg border border-border bg-input px-2 py-1"
          />
        </span>
        <span className="w-20 space-y-1">
          <label htmlFor={`edit-currency-${bill.task_id}`} className="text-xs">
            Currency
          </label>
          <input
            id={`edit-currency-${bill.task_id}`}
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            maxLength={3}
            className="w-full rounded-lg border border-border bg-input px-2 py-1"
          />
        </span>
        <span className="w-36 space-y-1">
          <label htmlFor={`edit-due-${bill.task_id}`} className="text-xs">
            Due
          </label>
          <input
            id={`edit-due-${bill.task_id}`}
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            className="w-full rounded-lg border border-border bg-input px-2 py-1"
          />
        </span>
      </div>
      {failed && <p className="text-sm text-destructive">{failed}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </li>
  );
}

/** Paying a bill, and saying what actually went out.
 *
 * The action the page was missing entirely: it could add and delete and not
 * pay. One click uses the expected figure, which is the ordinary case; the box
 * is for the month the bill came to something else.
 */
function PayBill({ bill }: { bill: BillRow }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(bill.amount ?? "");

  const pay = useMutation({
    mutationFn: async () => {
      const { error, response } = await apiV1.POST(
        "/api/v1/bills/entry/{task_id}/pay",
        {
          params: { path: { task_id: bill.task_id } },
          body: { amount: amount.trim() === "" ? null : amount.trim() },
        },
      );
      if (error || !response.ok) throw new RequestFailed(response.status);
    },
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["bills"] });
    },
  });

  if (bill.paid) return null;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="touch-target text-sm font-medium hover:underline"
        aria-label={`Pay ${bill.payee || bill.text}`}
      >
        Pay
      </button>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <label htmlFor={`pay-amount-${bill.task_id}`} className="text-xs">
        Paid
      </label>
      <input
        id={`pay-amount-${bill.task_id}`}
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        inputMode="decimal"
        placeholder="amount"
        className="w-24 rounded-lg border border-border bg-input px-2 py-1"
      />
      <Button size="sm" onClick={() => pay.mutate()} disabled={pay.isPending}>
        Mark paid
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
        Cancel
      </Button>
    </span>
  );
}

/** Removing a bill, and asking which bill is meant when it repeats.
 *
 * The narrow act is the default and the wide one has to be chosen: deleting
 * August's rent means *not this one*, and somebody who meant *stop paying rent*
 * can say so. The wide answer is the one adding a bill back cannot undo, since
 * it ends a series that has history behind it.
 */
function DeleteBill({ bill }: { bill: BillRow }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);

  const remove = useMutation({
    mutationFn: async (wholeSeries: boolean) => {
      const { error, response } = await apiV1.DELETE(
        "/api/v1/bills/entry/{task_id}",
        {
          params: {
            path: { task_id: bill.task_id },
            query: { whole_series: wholeSeries },
          },
        },
      );
      if (error || !response.ok) throw new RequestFailed(response.status);
    },
    onSuccess: () => {
      setAsking(false);
      queryClient.invalidateQueries({ queryKey: ["bills"] });
    },
  });

  if (!bill.repeats) {
    return (
      <button
        type="button"
        onClick={() => remove.mutate(false)}
        disabled={remove.isPending}
        className="touch-target text-sm text-muted-foreground hover:text-foreground"
        aria-label={`Delete ${bill.payee || bill.text}`}
      >
        Delete
      </button>
    );
  }

  if (!asking) {
    return (
      <button
        type="button"
        onClick={() => setAsking(true)}
        className="touch-target text-sm text-muted-foreground hover:text-foreground"
        aria-label={`Delete ${bill.payee || bill.text}`}
      >
        Delete
      </button>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted-foreground">Delete</span>
      <Button size="sm" variant="secondary" onClick={() => remove.mutate(false)}>
        just this month
      </Button>
      <Button size="sm" variant="secondary" onClick={() => remove.mutate(true)}>
        the standing bill
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </span>
  );
}

export function BillsRoute() {
  const { month } = useParams();
  // Which row is open for editing, by task id. One at a time: two half-edited
  // rows on screen is a way to lose one of them.
  const [editing, setEditing] = useState<number | null>(null);
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
            {data.bills.map((bill) =>
              editing === bill.task_id ? (
                <EditBill
                  key={bill.task_id}
                  bill={bill}
                  onDone={() => setEditing(null)}
                />
              ) : (
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
                  {/* Late, decided on the server against the owner's clock --
                      see BillRow.overdue_on. The browser only renders it. */}
                  {bill.overdue && (
                    <span className="ml-2 rounded bg-destructive/15 px-1.5 py-0.5 text-xs font-medium text-destructive">
                      overdue
                    </span>
                  )}
                  {/* The warning this module exists for. Shown only inside the
                      lead time, so an annual subscription is quiet for eleven
                      months and speaks in the twelfth. */}
                  {!bill.paid &&
                    !bill.overdue &&
                    bill.lead_days > 0 &&
                    daysUntil(bill.due_date) <= bill.lead_days && (
                      <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-xs text-accent">
                        {daysUntil(bill.due_date) <= 0
                          ? "due today"
                          : `in ${daysUntil(bill.due_date)} days`}
                      </span>
                    )}
                  {bill.recurrence !== "none" && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {cadenceLabel(bill.recurrence).toLowerCase()}
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
                    {bill.paid && bill.paid_amount !== null ? (
                      <>
                        {`${bill.paid_amount} ${bill.currency}`}
                        {/* Only when they differ: saying "paid 64.99, expected
                            64.99" on every settled bill is noise. */}
                        {bill.amount !== null &&
                          bill.amount !== bill.paid_amount && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              (expected {bill.amount})
                            </span>
                          )}
                      </>
                    ) : bill.amount === null ? (
                      // Not "0.00", which would read as free.
                      <span className="text-muted-foreground">no amount</span>
                    ) : (
                      `${bill.amount} ${bill.currency}`
                    )}
                  </span>
                  <PayBill bill={bill} />
                  <button
                    type="button"
                    onClick={() => setEditing(bill.task_id)}
                    className="touch-target text-sm text-muted-foreground hover:text-foreground"
                    aria-label={`Edit ${bill.payee || bill.text}`}
                  >
                    Edit
                  </button>
                  <DeleteBill bill={bill} />
                </span>
              </li>
              ),
            )}
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
