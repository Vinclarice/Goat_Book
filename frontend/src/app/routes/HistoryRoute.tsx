import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * Twelve months of balances, and six months of arithmetic about them.
 *
 * Vince: *"a table with accounts listed, and balances over say a 12 month
 * period. And I would like to have a prediction for the next six months."*
 *
 * **The projection is arithmetic and the page says so.** The average monthly
 * change, carried forward, with what it was drawn from shown beside it. Nothing
 * learns and nothing is fitted — a straight line a person can check in their
 * head is worth more here than a better curve they cannot, and a forecast is
 * the easiest place in a money tool to say something untrue with a straight
 * face.
 *
 * **The graph is drawn here rather than by a library.** Twelve points on a line
 * need no framework, and a dependency is a permanent cost against a handful of
 * sparklines — the same reasoning that deferred `torch`. See
 * `money-module-plan.md` increment 11.
 */
type Row = {
  account_id: number;
  name: string;
  currency: string;
  owes: boolean;
  balances: (string | null)[];
  projection: {
    months: string[][];
    monthly_change: string;
    readings_used: number;
    clears_on: string | null;
  } | null;
};

function monthLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
  });
}

function longMonth(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

/**
 * A sparkline over the readings, with the projection dashed behind it.
 *
 * **Recorded and projected are drawn differently on purpose.** A single
 * unbroken line would present six months of arithmetic as though they were six
 * months of fact, which is the one thing this graph must not do.
 *
 * Gaps break the line rather than being interpolated: a month nobody recorded
 * is not a point between two others.
 */
function Sparkline({ row }: { row: Row }) {
  const recorded = row.balances
    .map((value, index) => ({ value: value === null ? null : Number(value), index }))
    .filter((point) => point.value !== null) as { value: number; index: number }[];
  const projected = (row.projection?.months ?? []).map((pair, offset) => ({
    value: Number(pair[1]),
    index: row.balances.length + offset,
  }));
  const all = [...recorded, ...projected];
  if (all.length < 2) return null;

  const width = 180;
  const height = 32;
  const span = row.balances.length + projected.length - 1;
  const values = all.map((point) => point.value);
  const top = Math.max(...values);
  const bottom = Math.min(...values);
  // A flat line sits in the middle rather than dividing by zero.
  const range = top - bottom || 1;
  const x = (index: number) => (index / span) * width;
  const y = (value: number) => height - ((value - bottom) / range) * height;

  const path = (points: { value: number; index: number }[]) =>
    points
      .map((point, at) => `${at === 0 ? "M" : "L"}${x(point.index)},${y(point.value)}`)
      .join(" ");

  const last = recorded[recorded.length - 1];
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={`${row.name} over time`}
      className="shrink-0"
    >
      <path d={path(recorded)} fill="none" stroke="currentColor" strokeWidth="1.5" />
      {projected.length > 0 && last && (
        <path
          d={path([last, ...projected])}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeDasharray="3 3"
          opacity="0.5"
        />
      )}
    </svg>
  );
}

export function HistoryRoute() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["balance-history"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/money/history", {
        params: { query: { months: 12 } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-sans text-xl font-bold">Balances over time</h1>
        <Link
          to="/money"
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          ← Money
        </Link>
      </div>

      {data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No accounts yet.{" "}
          <Link to="/money/month" className="underline">
            Add one
          </Link>{" "}
          to start a history.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-3 font-bold">Account</th>
                  {data.months.map((each) => (
                    <th key={each} className="px-2 py-2 text-right font-medium">
                      {monthLabel(each)}
                    </th>
                  ))}
                  <th className="pl-3 py-2 font-medium">Trend</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.account_id} className="border-b border-border">
                    <td className="py-2 pr-3">
                      {row.name}
                      <span className="ml-2 text-xs text-muted-foreground">
                        {row.owes ? "owed" : "held"}
                      </span>
                    </td>
                    {row.balances.map((value, index) => (
                      <td
                        key={data.months[index]}
                        className="px-2 py-2 text-right tabular-nums"
                      >
                        {/* An em dash rather than a zero: nothing recorded and
                            nothing owed are different facts. */}
                        {value === null ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          value
                        )}
                      </td>
                    ))}
                    <td className="pl-3 py-2">
                      <Sparkline row={row as Row} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="space-y-2">
            <h2 className="text-sm font-bold">If things carry on as they have</h2>
            {data.rows.map((row) => (
              <p key={row.account_id} className="text-sm">
                <span className="font-medium">{row.name}</span>{" "}
                {row.projection === null ? (
                  /* The refusal, said rather than hidden. Two points make a
                     line through whatever those two months contained, and it
                     would look exactly as confident as one drawn from twelve. */
                  <span className="text-muted-foreground">
                    — not enough history yet. Three months of readings will do it.
                  </span>
                ) : (
                  <>
                    <span className="text-muted-foreground">
                      {Number(row.projection.monthly_change) < 0 ? "falling" : "rising"}{" "}
                      about {Math.abs(Number(row.projection.monthly_change)).toFixed(2)}{" "}
                      {row.currency} a month, from {row.projection.readings_used}{" "}
                      readings.
                    </span>{" "}
                    <span>
                      {row.projection.months[row.projection.months.length - 1][1]}{" "}
                      {row.currency} by{" "}
                      {longMonth(
                        row.projection.months[row.projection.months.length - 1][0],
                      )}
                      .
                    </span>
                    {row.projection.clears_on && (
                      /* The one output worth more than the six figures behind
                         it. */
                      <strong className="ml-1 text-accent">
                        Clear by {longMonth(row.projection.clears_on)}.
                      </strong>
                    )}
                  </>
                )}
              </p>
            ))}
            <p className="pt-1 text-xs text-muted-foreground">
              {/* Said plainly. A projection presented without this line is a
                  forecast pretending to be a fact. */}
              These are arithmetic, not predictions: the average monthly change
              so far, carried forward. Nothing here knows about interest rates,
              a raise, or a month you decide to pay double.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
