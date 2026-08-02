/**
 * Carries an HTTP status out of a query function and into the error state.
 *
 * openapi-fetch returns `{data, error, response}` and never throws, so
 * routes were written as `if (error) throw error` -- which throws the parsed
 * *body*. The status was discarded right there, which is why every failure
 * arrived at the UI indistinguishable from every other one and could only
 * be rendered as "Something went wrong."
 *
 * See design/bittern-plan.md, B2.1.
 */
export class RequestFailed extends Error {
  constructor(readonly status: number) {
    super(`Request failed with status ${status}`);
    this.name = "RequestFailed";
  }
}

/**
 * The status behind a query error, or undefined when there isn't one.
 *
 * Undefined is a real answer rather than a missing one: a dropped
 * connection produces a TypeError from fetch itself, with no response and
 * no status. Callers must treat that as retryable rather than permanent.
 */
export function statusOf(error: unknown): number | undefined {
  return error instanceof RequestFailed ? error.status : undefined;
}
