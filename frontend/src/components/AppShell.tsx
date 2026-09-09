import type { ReactNode } from "react";

import sciscopeLogo from "../assets/brand/sciscope-logo.svg";
import type { ViewerPayload } from "../types/api";

type AppShellProps = {
  activeView: "explore" | "feed" | "subscriptions" | "about" | "account" | "privacy" | "terms";
  children: ReactNode;
  onNavigate: (view: "explore" | "feed" | "subscriptions" | "about") => void;
  onOpenAccount: () => void;
  onSignIn: () => void;
  onSignOut: () => void;
  unreadFeedCount: number;
  signingIn: boolean;
  signingOut: boolean;
  viewer: ViewerPayload["user"];
};

export function AppShell({
  activeView,
  children,
  onNavigate,
  onOpenAccount,
  onSignIn,
  onSignOut,
  unreadFeedCount,
  signingIn,
  signingOut,
  viewer,
}: AppShellProps) {
  return (
    <div className="app-frame">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="sidebar-brand-block header-brand-block">
            <button
              className="sidebar-brand-button"
              onClick={() => onNavigate("explore")}
              type="button"
            >
              <img alt="SciScope" className="sidebar-brand-logo" src={sciscopeLogo} />
            </button>
          </div>

          <div className="header-actions">
            {viewer ? (
              <div className="viewer-strip">
                <button className="viewer-account-button" onClick={onOpenAccount} type="button">{viewer.displayName}</button>
                <button
                  className="outline-button"
                  disabled={signingOut}
                  onClick={onSignOut}
                  type="button"
                >
                  {signingOut ? "Signing Out..." : "Sign Out"}
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
        </div>
      </header>

      <aside className="app-sidebar">
        <nav aria-label="Primary" className="sidebar-nav">
          <button
            className={
              activeView === "explore"
                ? "sidebar-nav-button sidebar-nav-button-active"
                : "sidebar-nav-button"
            }
            aria-current={activeView === "explore" ? "page" : undefined}
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
            aria-current={activeView === "feed" ? "page" : undefined}
            onClick={() => onNavigate("feed")}
            type="button"
          >
            <FeedIcon />
            <span>Feed</span>
            {unreadFeedCount > 0 ? (
              <span aria-label={`${unreadFeedCount} unread feed events`} className="sidebar-nav-badge">
                {unreadFeedCount > 99 ? "99+" : unreadFeedCount}
              </span>
            ) : null}
          </button>
          <button
            className={
              activeView === "subscriptions"
                ? "sidebar-nav-button sidebar-nav-button-active"
                : "sidebar-nav-button"
            }
            aria-current={activeView === "subscriptions" ? "page" : undefined}
            onClick={() => onNavigate("subscriptions")}
            type="button"
          >
            <LibraryIcon />
            <span>Subscriptions</span>
          </button>
        </nav>
      </aside>

      <div className="app-main-column">
        <div className="app-content">
          <div className="app-content-frame">
            {children}
            <footer className="legal-footer">
              <span>© 2026 SciScope</span>
              <button
                aria-current={activeView === "about" ? "page" : undefined}
                className="legal-footer-link"
                onClick={() => onNavigate("about")}
                type="button"
              >
                About
              </button>
              <a href="/privacy">Privacy Policy</a>
              <a href="/terms">Terms of Use</a>
            </footer>
          </div>
        </div>
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

function LibraryIcon() {
  return (
    <svg
      aria-hidden="true"
      className="sidebar-nav-icon"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M4.5 4.5H15.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <path d="M4.5 10H15.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <path d="M4.5 15.5H15.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <path d="M6 3.5V16.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}
