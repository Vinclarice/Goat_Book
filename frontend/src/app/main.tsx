import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";

import { AgendaRoute } from "./routes/AgendaRoute";
import { DevUiGallery } from "./routes/DevUiGallery";

const queryClient = new QueryClient();

const rootElement = document.getElementById("app-root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/app">
          <Routes>
            <Route path="/agenda" element={<AgendaRoute />} />
            {/* Django 404s this path outside DEBUG -- see lists.views.spa_shell */}
            <Route path="/dev/ui" element={<DevUiGallery />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
