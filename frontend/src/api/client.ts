import createClient from "openapi-fetch";

import type { paths } from "./schema";

/** The CSRF cookie, read at request time.
 *
 * **Moved here from `api.ts` on August 30, 2026** --
 * coherence-audit-2026-08-30.md F2. That file's task writes now go through
 * this client, so leaving its one remaining utility there would have made the
 * two modules import each other. It has always had exactly one caller, in the
 * middleware below.
 */
function getCookie(name: string): string {
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
}

/**
 * Typed client for /api/v1/, generated from the Ninja OpenAPI schema (see
 * package.json's generate:api).
 *
 * ~~The legacy hand-rolled endpoints in ../api.ts are untouched -- this only
 * talks to the new contract.~~ **False since August 30, 2026**:
 * coherence-audit-2026-08-30.md F2 moved task and checklist writes onto
 * /api/v1/, so `../api.ts` is a wrapper layer over *this* client rather than a
 * second one. What is still hand-rolled is `lists/api.py`, which exists now
 * only for the shipped Android build.
 */
export const apiV1 = createClient<paths>({
  // openapi-fetch builds a `Request` internally, which (unlike a plain
  // fetch() call) needs an absolute URL -- there's no implicit document
  // base the way there is for a bare relative fetch.
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // openapi-fetch resolves its `fetch` option once, when the client is
  // created -- since this module is imported (and this client built) at
  // test-collection time, tests that vi.spyOn(globalThis, "fetch") in
  // beforeEach would otherwise be stubbing a reference nothing calls.
  // Wrapping it keeps the lookup live on every request instead.
  fetch: (...args: Parameters<typeof fetch>) => globalThis.fetch(...args),
});

apiV1.use({
  onRequest({ request }) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      request.headers.set("X-CSRFToken", getCookie("csrftoken"));
    }
    return request;
  },
});
