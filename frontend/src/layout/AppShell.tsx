import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { QueryProvider } from "../context/QueryContext";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import "./AppShell.css";

const COLLAPSE_KEY = "wb:sidebar-collapsed";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  return (
    <QueryProvider>
    <div className={`shell${collapsed ? " shell--collapsed" : ""}`}>
      <aside className="shell__sidebar">
        <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((c) => !c)} />
      </aside>

      {drawerOpen ? (
        <div className="shell__drawer" role="dialog" aria-modal="true" aria-label="Меню">
          <div className="shell__drawer-panel">
            <Sidebar
              collapsed={false}
              onToggleCollapsed={() => setDrawerOpen(false)}
              onNavigate={() => setDrawerOpen(false)}
            />
          </div>
          <button
            type="button"
            className="shell__overlay"
            aria-label="Закрыть меню"
            onClick={() => setDrawerOpen(false)}
          />
        </div>
      ) : null}

      <div className="shell__main">
        <Topbar onOpenMenu={() => setDrawerOpen(true)} />
        <main className="shell__content">
          <div className="shell__content-inner">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
    </QueryProvider>
  );
}
