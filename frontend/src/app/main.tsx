import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router";

import { AppRoutes } from "./AppRoutes";

// openapi-fetch never throws on a non-2xx response (it returns
// {data, error}), so TanStack Query can't tell a permanent 404/401 apart
// from a transient network failure -- without this, every route's own
// Vitest suite sets retry: false locally, but the real app would retry
// (and hang on "Loading...") for ordinary cases like a deleted area or
// an archived task.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const rootElement = document.getElementById("app-root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/app">
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
