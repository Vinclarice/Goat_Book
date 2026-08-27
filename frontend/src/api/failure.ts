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


/**
 * A refusal the server bothered to word, as an Error carrying that sentence.
 *
 * Ninja answers an `HttpError` with `{"detail": "..."}`, and every 409 on the
 * money router is a sentence written for a person -- *"there is already an open
 * bill from Amazon; add a word to tell them apart"*, *"Stocks ISA: that is not a
 * number"*. Routes were catching those and substituting their own generic
 * apology, which threw away the only part that says what to change.
 *
 * **`error` first, `response` second.** openapi-fetch has already parsed the
 * body by the time a route sees it, and reading the stream again is both
 * redundant and fragile -- a `clone()` that a test double implements as
 * `return this` is not a clone, and the second read can find nothing. Falling
 * back to the response covers the case where the body was not JSON.
 *
 * Anything unworded becomes a `RequestFailed`, because a failure with nothing
 * to say should not pretend to be advice.
 */
export async function refusal(
  error: unknown,
  response: Response,
): Promise<Error> {
  const parsed = error as { detail?: unknown } | undefined;
  if (typeof parsed?.detail === "string" && parsed.detail) {
    return new Error(parsed.detail);
  }
  try {
    const body = await response.clone().json();
    if (typeof body?.detail === "string" && body.detail) {
      return new Error(body.detail);
    }
  } catch {
    // Not JSON, or already consumed. The status is what is left to say.
  }
  return new RequestFailed(response.status);
}
