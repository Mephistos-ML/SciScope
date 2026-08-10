import type { AuthMode } from "../lib/config";
import type { ViewerPayload } from "../types/api";

type AppHeaderProps = {
  activeView: "explore" | "feed";
  authMode: AuthMode;
  onNavigate: (view: "explore" | "feed") => void;
  onSignIn: () => void;
  onSignOut: () => void;
  signingIn: boolean;
  signingOut: boolean;
  viewer: ViewerPayload["user"];
};

export function AppHeader({
  activeView,
  authMode,
  onNavigate,
  onSignIn,
  onSignOut,
  signingIn,
  signingOut,
  viewer,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <div>
        <p className="app-kicker">Scientific repository radar</p>
        <h1 className="app-title">SciScope</h1>
      </div>

      <div className="header-actions">
        <nav className="nav-tabs" aria-label="Primary">
          <button
            className={activeView === "explore" ? "nav-tab nav-tab-active" : "nav-tab"}
            onClick={() => onNavigate("explore")}
            type="button"
          >
            Explore
          </button>
          <button
            className={activeView === "feed" ? "nav-tab nav-tab-active" : "nav-tab"}
            onClick={() => onNavigate("feed")}
            type="button"
          >
            My Feed
          </button>
        </nav>

        {viewer ? (
          <div className="viewer-strip">
            <span>{viewer.displayName}</span>
            <button
              className="outline-button"
              onClick={onSignOut}
              disabled={signingOut}
              type="button"
            >
              {signingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        ) : authMode === "dev" ? (
          <button
            className="solid-button"
            onClick={onSignIn}
            disabled={signingIn}
            type="button"
          >
            {signingIn ? "Connecting..." : "Developer sign-in"}
          </button>
        ) : (
          <div className="viewer-strip viewer-strip-muted">
            <span>Authentication not enabled</span>
          </div>
        )}
      </div>
    </header>
  );
}
