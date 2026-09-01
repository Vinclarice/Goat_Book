import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, refusal, statusOf } from "../../api/failure";
import { Button } from "../../components/ui/button";
import { RouteFailure } from "./RouteFailure";

/**
 * The end-of-month pass — every balance, one screen, one save.
 *
 * Vince, August 27, 2026: *"typically at the end of the month I will do a
 * review and update all the balances."* That is a ritual rather than a field,
 * so this is one screen rather than eight edit forms. Six numbers, one button.
 *
 * **Boxes start empty, with last month beside them.** Pre-filling this month
 * from last month would make an untouched box look like a considered answer,
 * and a balance nobody checked is exactly what this screen exists to prevent.
 * What is shown instead is where it stood, so the figure you type has something
 * to be read against.
 */
function monthLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

/** Making the first account, where somebody is already trying to record a
 * balance.
 *
 * **`POST /api/v1/money/accounts` had no caller anywhere in the SPA until
 * August 31, 2026.** It existed, it was tested, and both this screen and the
 * history screen told somebody to "add an account" without either being able
 * to -- one of them linking to a third page that could not either. So
 * `Account` and `BalanceReading` passed `architecture-trajectory.md` §4, got an
 * endpoint, and never got a door, which is `principles.md`'s *a slice is not
 * closed while nothing calls it* in its plainest form.
 *
 * **It also invalidated the evidence against Balances.** `money-module-plan.md`
 * asks "whether balances would actually get typed in", and production had zero
 * accounts after four days -- which read as the input ratio answering the
 * question, and was a missing button.
 *
 * **Name and kind only.** Currency defaults to USD and `owes` is null, which
 * lets the kind decide -- a card and a loan owe, savings and investments hold.
 * The endpoint has always taken two fields for that reason; asking for four
 * here would be a form arguing with its own schema.
 */
function AddAccount() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("card");
  // Sent rather than left to the server default, because the schema marks
  // it required and both bill forms on /money already carry one. A picker
  // here is the same question they answered and is not reopened.
  const [currency, setCurrency] = useState("USD");
  const [failed, setFailed] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await apiV1.POST("/api/v1/money/accounts", {
        body: { name, kind, currency },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setName("");
      setFailed(null);
      // The list this page renders, and the landing page's own balances
      // section, both move the moment an account exists. Keyed exactly as
      // their own queries are -- ["accounts", day] and ["money-landing"] --
      // because an invalidation that names a key nothing uses is silent.
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["money-landing"] });
    },
    onError: (error: { detail?: string }) => {
      setFailed(error?.detail ?? "Couldn't add that account.");
    },
  });

  return (
    <form
      className="space-y-2 rounded-lg border border-border px-3 py-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!name.trim()) return;
        create.mutate();
      }}
    >
      <div className="flex flex-wrap items-end gap-2">
        <span className="space-y-1">
          <label htmlFor="new-account-name" className="block text-xs font-bold">
            Account name
          </label>
          <input
            id="new-account-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Dell Community"
            className="min-h-11 rounded-lg border border-border bg-input px-2.5 text-sm"
          />
        </span>
        <span className="space-y-1">
          <label htmlFor="new-account-kind" className="block text-xs font-bold">
            Kind
          </label>
          <select
            id="new-account-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
            className="min-h-11 rounded-lg border border-border bg-input px-2.5 text-sm"
          >
            <option value="card">Credit card</option>
            <option value="loan">Loan</option>
            <option value="savings">Savings</option>
            <option value="investment">Investment</option>
          </select>
        </span>
        <span className="space-y-1">
          <label htmlFor="new-account-currency" className="block text-xs font-bold">
            Currency
          </label>
          <input
            id="new-account-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            maxLength={3}
            className="min-h-11 w-20 rounded-lg border border-border bg-input px-2.5 text-sm"
          />
        </span>
        <Button type="submit" size="sm" className="h-11" disabled={create.isPending}>
          Add account
        </Button>
      </div>
      {failed && <p className="text-sm text-destructive">{failed}</p>}
    </form>
  );
}

export function BalancesRoute() {
  const { month } = useParams();
  const queryClient = useQueryClient();
  const [figures, setFigures] = useState<Record<number, string>>({});
  const [failed, setFailed] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const day = month ?? new Date().toISOString().slice(0, 10);
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["accounts", day],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/money/accounts/{day}", {
        params: { path: { day } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // Seeded from what is already recorded for *this* month, so reopening the
  // screen shows what you entered rather than blanks. Different from
  // pre-filling from last month: this shows your own answer, that would invent
  // one for you.
  useEffect(() => {
    if (!data) return;
    const existing: Record<number, string> = {};
    for (const account of data.accounts) {
      if (account.balance !== null) existing[account.id] = account.balance;
    }
    setFigures(existing);
  }, [data]);

  const save = useMutation({
    mutationFn: async () => {
      if (!data) return;
      const { error, response } = await apiV1.POST("/api/v1/money/balances", {
        body: {
          on_date: data.month_start,
          readings: data.accounts.map((account) => ({
            account_id: account.id,
            // Untouched means leave it alone, which is what the server reads
            // null as. Sending "" would be asking to blank it.
            amount: (figures[account.id] ?? "").trim() || null,
          })),
        },
      });
      if (error || !response.ok) throw await refusal(error, response);
    },
    onSuccess: () => {
      setSaved(true);
      setFailed(null);
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["bills"] });
    },
    onError: (caught: Error) => {
      setSaved(false);
      setFailed(caught.message);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  const owed = Object.entries(data.owed_totals);
  const held = Object.entries(data.held_totals);

  return (
    <div className="max-w-2xl mx-auto space-y-4 px-4 py-8">
      <h1 className="font-sans text-xl font-bold">
        Balances — {monthLabel(data.month_start)}
      </h1>

      {data.accounts.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No accounts yet. Add the first one below.
        </p>
      )}

      <AddAccount />

      {data.accounts.length === 0 ? null : (
        <form onSubmit={submit} className="space-y-4">
          <ul className="space-y-1">
            {data.accounts.map((account) => (
              <li
                key={account.id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
              >
                <span className="min-w-0">
                  <label htmlFor={`balance-${account.id}`} className="font-medium">
                    {account.name}
                  </label>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {account.owes ? "owed" : "held"}
                  </span>
                  {account.previous !== null && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      last month {account.previous} {account.currency}
                    </span>
                  )}
                  {/* **The disconnect, closed.** Vince, August 31, 2026:
                      *"I've added Dell Commenity and its showing up but now
                      there's a disconnect. Like it should be tied to the
                      payments."* This screen showed a card, a figure, and
                      nothing about how it gets paid --
                      bill-as-a-model-plan.md increment 7.

                      **Absent rather than empty when nothing is filed**, which
                      is most accounts: a blank slot where a figure should be
                      reads as something that failed to load.

                      *Fed*, not *paid*, for something held. An ISA is not paid
                      down, and the wording follows the direction the way the
                      pay button already does. */}
                  {account.next_payment !== null && (
                    <span className="block text-xs text-muted-foreground">
                      {account.owes ? "Paid by" : "Fed by"}{" "}
                      <Link
                        to={`/money/bills/${account.next_payment.task_id}`}
                        className="hover:underline"
                      >
                        {account.next_payment.payee}
                      </Link>
                      {account.next_payment.amount !== null && (
                        <>
                          {" — "}
                          {account.next_payment.amount}{" "}
                          {account.next_payment.currency}
                        </>
                      )}
                      {" due "}
                      {account.next_payment.due_date}
                    </span>
                  )}
                </span>
                <input
                  id={`balance-${account.id}`}
                  value={figures[account.id] ?? ""}
                  onChange={(event) => {
                    setSaved(false);
                    setFigures((current) => ({
                      ...current,
                      [account.id]: event.target.value,
                    }));
                  }}
                  inputMode="decimal"
                  placeholder={account.currency}
                  className="w-32 shrink-0 rounded-lg border border-border bg-input px-2 py-1"
                />
              </li>
            ))}
          </ul>

          {(owed.length > 0 || held.length > 0) && (
            <div className="space-y-1 border-t border-border pt-2">
              {owed.map(([code, total]) => (
                <p key={`owed-${code}`} className="text-sm">
                  <span className="font-bold">
                    {total} {code}
                  </span>{" "}
                  owed
                </p>
              ))}
              {held.map(([code, total]) => (
                <p key={`held-${code}`} className="text-sm">
                  <span className="font-bold">
                    {total} {code}
                  </span>{" "}
                  held
                </p>
              ))}
              {/* Deliberately not subtracted. A net worth is a different claim
                  from either figure, and not one six typed numbers entitle this
                  page to make on somebody's behalf. */}
            </div>
          )}

          {failed && <p className="text-sm text-destructive">{failed}</p>}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending}>
              Save balances
            </Button>
            {saved && <span className="text-sm text-muted-foreground">Saved.</span>}
          </div>
        </form>
      )}
    </div>
  );
}
