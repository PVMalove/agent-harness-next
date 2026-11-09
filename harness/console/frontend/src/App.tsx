/* Hash routes: the static build needs no server-side fallback (ADR 0029). */
import { useState } from "react";
import type { ReactElement } from "react";
import { createHashRouter, Navigate, Outlet, RouterProvider } from "react-router";
import { AppShell } from "./AppShell";
import { ConnectionBanner, ConnectionChip, ConnectionPage, PAGE_STATUSES } from "./ConnectionViews";
import { HIDDEN_ROUTES, NAV_ITEMS } from "./navigation";
import { AgentActivity } from "./routes/AgentActivity";
import { ContainerRoute } from "./routes/ContainerRoute";
import { Diagnostics } from "./routes/Diagnostics";
import { Harness } from "./routes/Harness";
import { Decisions } from "./routes/Decisions";
import { Home } from "./routes/Home";
import { Orchestration } from "./routes/Orchestration";
import { Placeholder } from "./routes/Placeholder";
import { RepoMap } from "./routes/RepoMap";
import { Recovery } from "./routes/Recovery";
import { Reports } from "./routes/Reports";
import { ConsoleProvider, useConsole } from "./useConsole";
import type { ConsoleClient } from "./ws/client";

function Layout() {
  const { state } = useConsole();
  return (
    <AppShell chip={<ConnectionChip />} banner={<ConnectionBanner />}>
      {PAGE_STATUSES.includes(state.status) ? <ConnectionPage /> : <Outlet />}
    </AppShell>
  );
}

/** The sections the web console shows; the others are placeholders. */
const ROUTES: Readonly<Record<string, ReactElement>> = {
  "repo-map": <RepoMap />,
  diagnostics: <Diagnostics />,
  harness: <Harness />,
  reports: <Reports />,
  recovery: <Recovery />,
  "container-route": <ContainerRoute />,
  "agent-activity": <AgentActivity />,
  orchestration: <Orchestration />,
  publish: <Decisions section="Публикация" />,
};

export function createRouter() {
  return createHashRouter([
    {
      path: "/",
      element: <Layout />,
      children: [
        ...NAV_ITEMS.map((item) =>
          item.route
            ? { path: item.route, element: ROUTES[item.route] ?? <Placeholder section={item.section} /> }
            : { index: true, element: <Home /> },
        ),
        ...Object.keys(HIDDEN_ROUTES).map((route) => ({
          path: route,
          element: ROUTES[route] ?? <Placeholder section="Orchestration" />,
        })),
        { path: "*", element: <Navigate to="/" replace /> },
      ],
    },
  ]);
}

/** The app over the page's own console server, or over `client` in tests. */
export function App({ client }: { client?: ConsoleClient }) {
  const [router] = useState(createRouter);
  return (
    <ConsoleProvider client={client}>
      <RouterProvider router={router} />
    </ConsoleProvider>
  );
}
