import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router";

import { AppBoundary } from "./AppBoundary";
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
    // Outermost, so it catches the providers and the router too and not only
    // route content. A boundary nested inside them would be unable to catch
    // the thing that took them down, which is the case where a white screen
    // is hardest to diagnose.
    <StrictMode>
      <AppBoundary>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter basename="/app">
            <AppRoutes />
          </BrowserRouter>
        </QueryClientProvider>
      </AppBoundary>
    </StrictMode>,
  );
}
