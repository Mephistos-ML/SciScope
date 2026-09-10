import { useState, type ReactNode } from "react";

import sciscopeLogo from "../assets/brand/sciscope-logo.svg";
import accountSettingsIcon from "../assets/buttons/sciscope-account-settings.svg";
import dropdownIcon from "../assets/buttons/sciscope-dropdown.svg";
import exploreIcon from "../assets/buttons/sciscope-explore.svg";
import feedIcon from "../assets/buttons/sciscope-feed.svg";
import loginIcon from "../assets/buttons/sciscope-login.svg";
import logoutIcon from "../assets/buttons/sciscope-logout.svg";
import subscriptionsIcon from "../assets/buttons/sciscope-subscriptions.svg";
import type { ViewerPayload } from "../types/api";

type AppShellProps = {
  activeView: "explore" | "feed" | "subscriptions" | "about" | "account" | "privacy" | "terms";
  authLoading: boolean;
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
  authLoading,
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
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

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
            {authLoading ? (
              <div aria-label="Loading account" className="header-account-loading" role="status" />
            ) : viewer ? (
              <div
                className="viewer-menu"
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget)) {
                    setAccountMenuOpen(false);
                  }
                }}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setAccountMenuOpen(false);
                    event.currentTarget.querySelector<HTMLButtonElement>(".viewer-menu-trigger")?.focus();
                  }
                }}
              >
                <div className="viewer-strip">
                  {viewer.avatarUrl ? (
                    <img alt="" className="viewer-avatar" src={viewer.avatarUrl} />
                  ) : (
                    <span aria-hidden="true" className="viewer-avatar viewer-avatar-fallback">
                      {viewer.displayName.slice(0, 1)}
                    </span>
                  )}
                  <span className="viewer-name">{viewer.displayName}</span>
                  <button
                    aria-expanded={accountMenuOpen}
                    aria-haspopup="menu"
                    aria-label="Open account menu"
                  className="viewer-menu-trigger"
                    onClick={() => setAccountMenuOpen((open) => !open)}
                  type="button"
                >
                    <img alt="" className="viewer-dropdown-icon" src={dropdownIcon} />
                  </button>
                </div>
                {accountMenuOpen ? (
                  <div aria-label="Account menu" className="viewer-menu-popover" role="menu">
                    <button
                      className="viewer-menu-item"
                      onClick={() => {
                        setAccountMenuOpen(false);
                        onOpenAccount();
                      }}
                      role="menuitem"
                      type="button"
                    >
                      <img alt="" className="viewer-menu-item-icon" src={accountSettingsIcon} />
                      Account settings
                    </button>
                    <button
                      className="viewer-menu-item viewer-menu-sign-out"
                      disabled={signingOut}
                      onClick={() => {
                        setAccountMenuOpen(false);
                        onSignOut();
                      }}
                      role="menuitem"
                      type="button"
                    >
                      <img alt="" className="viewer-menu-item-icon" src={logoutIcon} />
                      {signingOut ? "Logging out..." : "Log out"}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : (
              <button
                className="solid-button"
                disabled={signingIn}
                onClick={onSignIn}
                type="button"
              >
                <img alt="" className="sign-in-icon" src={loginIcon} />
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
            <img alt="" className="sidebar-nav-icon" src={exploreIcon} />
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
            <img alt="" className="sidebar-nav-icon" src={feedIcon} />
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
            <img alt="" className="sidebar-nav-icon" src={subscriptionsIcon} />
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
