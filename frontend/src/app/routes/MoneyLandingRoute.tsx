import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * How the money stands, today.
 *
 * Vince described the module as *"its own sort of landing page for relevant
 * information — if I need to check on financial information, I know exactly
 * where to go"*, and what `/money` showed was one month of bills. Answering
 * *how am I doing* meant reading three lists and doing arithmetic.
 *
 * **Everything here is a read.** No row exists because this page does, which is
 * the Day page's rule and holds for the same reason: a lens over durable
 * records cannot fall out of step with them.
 *
 * **It crosses months.** Every other read in the module is keyed to one, which
 * is why *what is due in the next fortnight* could not be answered at all — a
 * fortnight from the 25th is mostly next month.
 */
type Line = {
  id: number;
  payee: string;
  due_date: string;
  amount: string | null;
  currency: string;
  days: number;
};

/** How a delay reads to a person, rather than as a signed integer. */
function whenLabel(days: number) {
  if (days < 0) return days === -1 ? "1 day late" : `${-days} days late`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `in ${days} days`;
}

function Section({
  title,
  lines,
  tone = "plain",
}: {
  title: string;
  lines: Line[];
  tone?: "plain" | "late";
}) {
  if (lines.length === 0) return null;
  return (
    <section className="space-y-1">
      <h2 className="text-sm font-bold">
        {title}{" "}
        <span className="font-normal text-muted-foreground">({lines.length})</span>
      </h2>
      <ul className="space-y-1">
        {lines.map((line) => (
          <li
            key={line.id}
            className="flex flex-wrap items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
          >
            <span className="min-w-0">
              {/* **`/money/bills/`, not `/tasks/`.** These rows carried task
                  ids until the flip and this link was never moved with them,
                  so a bill's id was being used to open a *task* -- and the two
                  sequences are independent, so it opened an unrelated task or
                  a not-found page. Fixed September 2, 2026. */}
              <Link to={`/money/bills/${line.id}`} className="hover:underline">
                {line.payee}
              </Link>
              <span
                className={`ml-2 text-xs ${
                  tone === "late"
                    ? "font-medium text-destructive"
                    : "text-muted-foreground"
                }`}
              >
                {whenLabel(line.days)}
              </span>
            </span>
            <span className="shrink-0 text-sm">
              {line.amount === null ? (
                <span className="text-muted-foreground">no amount</span>
              ) : (
                `${line.amount} ${line.currency}`
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A change, worded by whether it is good news on this side of the ledger. */
function Change({
  amount,
  currency,
  owed,
}: {
  amount: string;
  currency: string;
  owed: boolean;
}) {
  const value = Number(amount);
  if (value === 0) return <span className="text-muted-foreground">unchanged</span>;
  const down = value < 0;
  /* Down is good for something owed and bad for something held, so the colour
     follows the meaning rather than the sign. A page painting every fall red
     would call paying off a loan a bad month. */
  const good = owed ? down : !down;
  return (
    <span className={good ? "text-accent" : "text-destructive"}>
      {down ? "↓" : "↑"} {Math.abs(value).toFixed(2)} {currency}
    </span>
  );
}

export function MoneyLandingRoute() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["money-landing"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/money");
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  const owed = Object.entries(data.owed_totals);
  const held = Object.entries(data.held_totals);
  const yearly = Object.entries(data.yearly_totals);
  const nothingPressing =
    data.overdue.length === 0 &&
    data.due_soon.length === 0 &&
    data.renewing_soon.length === 0;
  /* **"Nothing needs you" and "you have not started" are different answers**,
     and this page gave the first to both until August 31, 2026 -- telling
     somebody with no bills at all that nothing was overdue, which is a
     tautology rather than information, on the module's front door, with no way
     to create anything from it. Vince walked into exactly that four days after
     the module shipped.

     Two counts rather than one flag, because the useful prompt differs: with
     bills and no accounts you are missing balances, not a start. */
  const nothingRecorded = data.line_count === 0 && data.account_count === 0;

  return (
    <div className="max-w-2xl mx-auto space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-sans text-xl font-bold">Money</h1>
        <span className="flex gap-4 text-sm">
          <Link
            to={`/money/month/${data.today}`}
            className="touch-target text-muted-foreground hover:text-foreground"
          >
            This month →
          </Link>
          <Link
            to="/money/history"
            className="touch-target text-muted-foreground hover:text-foreground"
          >
            History →
          </Link>
          <Link
            to="/money/balances"
            className="touch-target text-muted-foreground hover:text-foreground"
          >
            Update balances →
          </Link>
        </span>
      </div>

      {nothingRecorded ? (
        <section className="space-y-3 rounded-lg border border-border px-4 py-4">
          <h2 className="text-sm font-bold">Nothing recorded yet.</h2>
          <p className="max-w-prose text-sm text-muted-foreground">
            Money answers two questions: what needs paying, and how you stand.
            The first needs a bill; the second needs an account to carry a
            balance. Either is a fine place to start.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to={`/money/month/${data.today}`}
              className="touch-target inline-flex min-h-11 items-center rounded-lg border border-border px-3 text-sm font-semibold hover:border-foreground/30"
            >
              Add a bill
            </Link>
            <Link
              to="/money/balances"
              className="touch-target inline-flex min-h-11 items-center rounded-lg border border-border px-3 text-sm font-semibold hover:border-foreground/30"
            >
              Add an account
            </Link>
          </div>
        </section>
      ) : (
        <>
          {nothingPressing && (
            /* Said out loud rather than left as three absent sections: an
               empty page reads as broken, and "nothing needs you" is the
               answer somebody came here hoping for -- but only once there is
               something to be quiet about. */
            <p className="text-sm text-muted-foreground">
              Nothing is overdue, due soon, or about to renew.
            </p>
          )}
          {data.account_count === 0 && (
            /* The half-started state, and the one Vince was actually in: a
               bill recorded, no account, and three screens that mention
               balances without saying how to have one. */
            <p className="text-sm text-muted-foreground">
              No balances yet.{" "}
              <Link to="/money/balances" className="underline">
                Add an account
              </Link>{" "}
              to track what you owe and hold.
            </p>
          )}
          {data.line_count === 0 && (
            <p className="text-sm text-muted-foreground">
              No bills or income yet.{" "}
              <Link to={`/money/month/${data.today}`} className="underline">
                Add one
              </Link>{" "}
              to see what needs paying.
            </p>
          )}
        </>
      )}

      <Section title="Overdue" lines={data.overdue} tone="late" />
      <Section title="Due soon" lines={data.due_soon} />
      <Section title="Renewing soon" lines={data.renewing_soon} />

      {(owed.length > 0 || held.length > 0 || data.unread_accounts > 0) && (
        <section className="space-y-1">
          <h2 className="text-sm font-bold">Balances</h2>
          {owed.map(([code, total]) => (
            <p key={`owed-${code}`} className="text-sm">
              <span className="font-bold">
                {total} {code}
              </span>{" "}
              owed{" "}
              {data.owed_change[code] !== undefined && (
                <Change amount={data.owed_change[code]} currency={code} owed />
              )}
            </p>
          ))}
          {held.map(([code, total]) => (
            <p key={`held-${code}`} className="text-sm">
              <span className="font-bold">
                {total} {code}
              </span>{" "}
              held{" "}
              {data.held_change[code] !== undefined && (
                <Change
                  amount={data.held_change[code]}
                  currency={code}
                  owed={false}
                />
              )}
            </p>
          ))}
          {data.unread_accounts > 0 && (
            /* Counted, not carried forward: showing last month's figure as
               though it were this month's is the one thing a balance page must
               not do. */
            <p className="text-sm text-muted-foreground">
              {data.unread_accounts === 1
                ? "One account has no balance for this month yet."
                : `${data.unread_accounts} accounts have no balance for this month yet.`}{" "}
              <Link to="/money/balances" className="underline">
                Update them
              </Link>
            </p>
          )}
        </section>
      )}

      {yearly.length > 0 && (
        <section className="space-y-1">
          <h2 className="text-sm font-bold">Recurring, over a year</h2>
          {yearly.map(([code, total]) => (
            <p key={code} className="text-sm">
              <span className="font-bold">
                {total} {code}
              </span>{" "}
              a year in repeating bills
            </p>
          ))}
          {/* One-off bills are deliberately absent: they happen once, and
              counting them would inflate the figure somebody acts on. */}
        </section>
      )}
    </div>
  );
}
