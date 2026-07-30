import createClient from "openapi-fetch";

import { getCookie } from "../api";
import type { paths } from "./schema";

/**
 * Typed client for /api/v1/, generated from the Ninja OpenAPI schema (see
 * package.json's generate:api). The legacy hand-rolled endpoints in
 * ../api.ts are untouched -- this only talks to the new contract.
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
