import createClient from "openapi-fetch";

import { getCookie } from "../api";
import type { paths } from "./schema";

/**
 * Typed client for /api/v1/, generated from the Ninja OpenAPI schema (see
 * package.json's generate:api). The legacy hand-rolled endpoints in
 * ../api.ts are untouched -- this only talks to the new contract.
 */
export const apiV1 = createClient<paths>({
  baseUrl: "/",
  credentials: "same-origin",
});

apiV1.use({
  onRequest({ request }) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      request.headers.set("X-CSRFToken", getCookie("csrftoken"));
    }
    return request;
  },
});
