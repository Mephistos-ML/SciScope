import type { ReactNode } from "react";

import { AppLink } from "../lib/router";

type SiteChromeProps = {
  children: ReactNode;
  currentPath: string;
  navigate: (href: string) => void;
};

const NAV_ITEMS = [
  { href: "/", label: "Landing" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/sources", label: "Sources" },
  { href: "/about", label: "About" },
];

export function SiteChrome({ children, currentPath, navigate }: SiteChromeProps) {
  return (
    <div className="site-shell">
      <header className="site-header">
        <AppLink className="site-brand" href="/" onNavigate={navigate}>
          SciScope
        </AppLink>
        <nav className="site-nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <AppLink
              key={item.href}
              className={currentPath === item.href ? "site-nav-link active" : "site-nav-link"}
              href={item.href}
              onNavigate={navigate}
            >
              {item.label}
            </AppLink>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
