/* Hash routes: the static build needs no server-side fallback (ADR 0029). */
import { useState } from "react";
import { createHashRouter, Navigate, Outlet, RouterProvider } from "react-router";
import { AppShell } from "./AppShell";
import { NAV_ITEMS } from "./navigation";
import { Placeholder } from "./routes/Placeholder";

function Layout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export function createRouter() {
  return createHashRouter([
    {
      path: "/",
      element: <Layout />,
      children: [
        ...NAV_ITEMS.map((item) =>
          item.route
            ? { path: item.route, element: <Placeholder section={item.section} /> }
            : { index: true, element: <Placeholder section={item.section} /> },
        ),
        { path: "*", element: <Navigate to="/" replace /> },
      ],
    },
  ]);
}

export function App() {
  const [router] = useState(createRouter);
  return <RouterProvider router={router} />;
}
