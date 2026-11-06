/* Hash routes: the static build needs no server-side fallback (ADR 0029). */
import { useState } from "react";
import type { ReactElement } from "react";
import { createHashRouter, Navigate, Outlet, RouterProvider } from "react-router";
import { AppShell } from "./AppShell";
import { ConnectionBanner, ConnectionChip, ConnectionPage, PAGE_STATUSES } from "./ConnectionViews";
import { NAV_ITEMS } from "./navigation";
import { AgentActivity } from "./routes/AgentActivity";
import { Harness } from "./routes/Harness";
import { Home } from "./routes/Home";
import { Placeholder } from "./routes/Placeholder";
import { RepoMap } from "./routes/RepoMap";
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
  harness: <Harness />,
  "agent-activity": <AgentActivity />,
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
