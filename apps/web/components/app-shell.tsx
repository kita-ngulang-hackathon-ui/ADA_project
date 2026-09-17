"use client";

// Top bar + collapsible sidebar. Wraps every console page.
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActions } from "@/components/actions-provider";
import { NavIcon, type NavIconName } from "@/components/icons";

type NavItem = {
  label: string;
  href: string;
  icon: NavIconName;
};

// Old stub pages (allocation, measurement, ...) stay routable but are not listed.
const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "home" },
  { label: "Suggested Actions", href: "/suggested-actions", icon: "sparkle" },
  { label: "Actions Overview", href: "/actions", icon: "checklist" },
];

const STORAGE_KEY = "ada.sidebar.collapsed";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { suggested } = useActions();

  // Restore the last choice after hydration so the server markup stays stable.
  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(STORAGE_KEY) === "true");
    } catch {
      // Storage blocked (private mode) — keep the default.
    }
  }, []);

  function toggle() {
    setCollapsed((previous) => {
      const next = !previous;
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Ignore: the sidebar still works without persistence.
      }
      return next;
    });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          type="button"
          className="topbar-toggle"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-controls="app-sidebar"
        >
          <span />
          <span />
          <span />
        </button>

        <Link href="/dashboard" aria-label="ADA Solutions dashboard">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/ada-logo-short.png"
            alt="ADA Solutions"
            className="topbar-logo"
          />
        </Link>

        <div className="topbar-spacer" />

        <div className="topbar-user">
          <div className="hidden sm:block text-right">
            <div className="topbar-user-name">Mr. Arya</div>
            <div className="topbar-user-role">Ops Reviewer</div>
          </div>
          <div className="avatar" aria-hidden="true">
            A
          </div>
        </div>
      </header>

      <aside
        id="app-sidebar"
        className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}
      >
        {!collapsed && <div className="sidebar-section">Console</div>}

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            const count =
              item.href === "/suggested-actions" ? suggested.length : 0;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link ${active ? "sidebar-link-active" : ""}`}
                title={collapsed ? item.label : undefined}
                aria-current={active ? "page" : undefined}
              >
                <span className="sidebar-icon">
                  <NavIcon name={item.icon} />
                  {collapsed && count > 0 && (
                    <span className="sidebar-dot" aria-hidden="true" />
                  )}
                </span>
                {!collapsed && (
                  <span className="sidebar-label">{item.label}</span>
                )}
                {!collapsed && count > 0 && (
                  <span className="sidebar-count" aria-label={`${count} pending`}>
                    {count}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <Link
            href="/"
            className="sidebar-link"
            title={collapsed ? "Log out" : undefined}
          >
            <span className="sidebar-icon">
              <NavIcon name="logout" />
            </span>
            {!collapsed && <span className="sidebar-label">Log out</span>}
          </Link>
        </div>
      </aside>

      <main className={`app-content ${collapsed ? "app-content-wide" : ""}`}>
        {children}
      </main>
    </div>
  );
}
