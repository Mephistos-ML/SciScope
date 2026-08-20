import type { ReactNode } from "react";

import sciscopeLogo from "../assets/brand/sciscope-logo.svg";
import type { ViewerPayload } from "../types/api";

type AppShellProps = {
  activeView: "explore" | "feed";
  children: ReactNode;
  onNavigate: (view: "explore" | "feed") => void;
  onSignIn: () => void;
  onSignOut: () => void;
  signingIn: boolean;
  signingOut: boolean;
  viewer: ViewerPayload["user"];
};

export function AppShell({
  activeView,
  children,
  onNavigate,
  onSignIn,
  onSignOut,
  signingIn,
  signingOut,
  viewer,
}: AppShellProps) {
  return (
    <div className="app-frame">
      <aside className="app-sidebar">
        <div className="sidebar-brand-block">
          <button
            className="sidebar-brand-button"
            onClick={() => onNavigate("explore")}
            type="button"
          >
            <img alt="SciScope" className="sidebar-brand-logo" src={sciscopeLogo} />
          </button>
        </div>

        <nav aria-label="Primary" className="sidebar-nav">
          <button
            className={
              activeView === "explore"
                ? "sidebar-nav-button sidebar-nav-button-active"
                : "sidebar-nav-button"
            }
            onClick={() => onNavigate("explore")}
            type="button"
          >
            <SearchIcon />
            <span>Explore</span>
          </button>
          <button
            className={
              activeView === "feed"
                ? "sidebar-nav-button sidebar-nav-button-active"
                : "sidebar-nav-button"
            }
            onClick={() => onNavigate("feed")}
            type="button"
          >
            <FeedIcon />
            <span>My Feed</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <p className="sidebar-footer-title">About SciScope</p>
          <p className="sidebar-footer-copy">
            Scientific repository intelligence for researchers and software-focused
            discovery.
          </p>
        </div>
      </aside>

      <div className="app-main-column">
        <header className="top-bar">
          <div className="top-bar-inner">
            {viewer ? (
              <div className="viewer-strip">
                <span>{viewer.displayName}</span>
                <button
                  className="outline-button"
                  disabled={signingOut}
                  onClick={onSignOut}
                  type="button"
                >
                  {signingOut ? "Signing out..." : "Sign out"}
                </button>
              </div>
            ) : (
              <button
                className="solid-button"
                disabled={signingIn}
                onClick={onSignIn}
                type="button"
              >
                {signingIn ? "Connecting..." : "Continue with Google"}
              </button>
            )}
          </div>
        </header>

        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg
      aria-hidden="true"
      className="sidebar-nav-icon"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12.5 12.5L17 17" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function FeedIcon() {
  return (
    <svg
      aria-hidden="true"
      className="sidebar-nav-icon"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="3" y="3" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M6 10H14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <path d="M10 6L10 14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}
